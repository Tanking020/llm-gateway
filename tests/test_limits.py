"""护栏上限：并发闸门 / max_tokens / 输入长度 —— 全部是「拒绝得早、拒绝得清楚」的边界"""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client, get_settings
from app.config import settings
from app.errors import AppError
from app.schemas import MAX_CONTENT_CHARS, MAX_MESSAGES, MAX_TOTAL_CHARS
from fakes import FakeLlm

CHUNKS: list[dict[str, Any]] = [
    {"choices": [{"index": 0, "delta": {"content": "hi"}}]},
    {
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    },
]
REQ = {"messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _clean(client: TestClient) -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _slots() -> int:
    sem: asyncio.Semaphore = app.state.upstream_semaphore
    return sem._value


def _set_slots(value: int) -> None:
    app.state.upstream_semaphore = asyncio.Semaphore(value)


def _use(fake: FakeLlm, *, queue_timeout: float | None = None) -> None:
    app.dependency_overrides[get_llm_client] = lambda: fake
    if queue_timeout is not None:
        app.dependency_overrides[get_settings] = lambda: settings.model_copy(
            update={"upstream_queue_timeout": queue_timeout}
        )


def test_gate_returns_503_when_no_slot_available(client: TestClient) -> None:
    _use(FakeLlm(chunks=CHUNKS), queue_timeout=0.05)
    _set_slots(0)

    response = client.post("/v1/chat/stream", json=REQ)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    error = response.json()["error"]
    assert error["code"] == "SERVER_BUSY"


def test_gate_slot_released_after_success(client: TestClient) -> None:
    _use(FakeLlm(chunks=CHUNKS))
    _set_slots(1)

    assert client.post("/v1/chat/stream", json=REQ).status_code == 200
    assert _slots() == 1


def test_gate_slot_released_after_upstream_error(client: TestClient) -> None:
    _use(FakeLlm(stream_error=AppError("UPSTREAM_UNREACHABLE", "上游连不上")))
    _set_slots(1)

    assert client.post("/v1/chat/stream", json=REQ).status_code == 502
    assert _slots() == 1


@pytest.mark.parametrize("path", ["/v1/chat", "/v1/chat/stream"])
def test_max_tokens_over_ceiling_returns_400(client: TestClient, path: str) -> None:
    _use(FakeLlm(chunks=CHUNKS))

    response = client.post(path, json={**REQ, "max_tokens": settings.max_tokens_ceiling + 1})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MAX_TOKENS"


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (None, settings.max_tokens_ceiling),
        (1, 1),
        (settings.max_tokens_ceiling, settings.max_tokens_ceiling),
    ],
    ids=["未指定", "指定小值", "正好等于上限"],
)
def test_max_tokens_sent_upstream(client: TestClient, given: int | None, expected: int) -> None:
    fake = FakeLlm(chunks=CHUNKS)
    _use(fake)

    payload = dict(REQ) if given is None else {**REQ, "max_tokens": given}
    assert client.post("/v1/chat/stream", json=payload).status_code == 200
    assert fake.last_body is not None
    assert fake.last_body["max_tokens"] == expected


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        (
            "单条正文超长",
            {"messages": [{"role": "user", "content": "x" * (MAX_CONTENT_CHARS + 1)}]},
        ),
        (
            "消息条数超限",
            {"messages": [{"role": "user", "content": "hi"}] * (MAX_MESSAGES + 1)},
        ),
        (
            "合计超限（每条都合法）",
            # 每条都 <= MAX_CONTENT_CHARS，只有【合计】超 —— 否则会被单条上限先拦下
            {"messages": [{"role": "user", "content": "x" * (MAX_TOTAL_CHARS // 4 + 1)}] * 4},
        ),
    ],
    ids=["content", "count", "total"],
)
def test_input_limits_return_422(client: TestClient, label: str, payload: dict[str, Any]) -> None:
    response = client.post("/v1/chat", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
