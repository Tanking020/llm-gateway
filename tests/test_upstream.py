"""上游适配器接线测试：用假 LLM 证明路由真的走了依赖注入，且上游故障都变 502"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import RealUpstreamForbidden
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client
from app.config import settings
from app.errors import AppError
from app.schemas import ModelItem
from fakes import FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}


# @pytest.fixture 是用来定义"测试前置/后置条件"的装饰器——
# 它让函数变成可复用的"测试环境搭建器"，自动管理创建、清理，还能在多个测试之间共享
@pytest.fixture(autouse=True)
def _clean_overrides() -> Iterator[None]:
    """每个测试结束后清掉依赖覆盖，避免假客户端漏到下一个测试"""
    yield
    app.dependency_overrides.clear()


def test_upstream_models_uses_fake(client: TestClient) -> None:
    fake = FakeLlm(models=[ModelItem(id="m1"), ModelItem(id="m2")])
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.get("/v1/upstream/models")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == ["m1", "m2"]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("UPSTREAM_UNREACHABLE", id="unreachable"),
        pytest.param("UPSTREAM_BAD_STATUS", id="bad_status"),
        pytest.param("UPSTREAM_MALFORMED", id="malformed"),
    ],
)
def test_upstream_failure_becomes_502(client: TestClient, code: str) -> None:
    fake = FakeLlm(models_error=AppError(code=code, message="上游出错"))
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.get("/v1/upstream/models")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == code


def test_rate_limited_reaches_client_with_retry_after(client: TestClient) -> None:
    """路由层端到端：429 的状态码 + Retry-After + X-Request-ID 三者同时正确

    【注意】：最后那条断言防的是「合并写成覆盖」—— 加了 Retry-After 之后
        X-Request-ID 不能丢，且必须和 body 里的 request_id 一致
    """
    fake = FakeLlm(
        models_error=AppError(
            code="UPSTREAM_RATE_LIMITED",
            message="上游限流，请稍后重试",
            headers={"Retry-After": "7"},
        )
    )
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.get("/v1/upstream/models")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    assert response.json()["error"]["code"] == "UPSTREAM_RATE_LIMITED"
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]


def test_stream_preflight_failure_changes_status_code(client: TestClient) -> None:
    fake = FakeLlm(stream_error=AppError(code="UPSTREAM_UNREACHABLE", message="上游连不上"))
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post(
        "/v1/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_UNREACHABLE"


def test_stream_consumes_fake_chunks(client: TestClient) -> None:
    fake = FakeLlm(chunks=[{"choices": [{"index": 0, "delta": {"content": "你"}}]}])
    app.dependency_overrides[get_llm_client] = lambda: fake

    # 用 with 是因为流式响应是"长连接"——连接会一直开着，直到服务器把所有数据吐完。
    #    with 保证无论测试成功还是失败，连接都会被关闭，不会泄漏
    with client.stream(
        "POST", "/v1/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert 'data: {"delta": "你"}' in body
    assert body.endswith("data: [DONE]\n\n")
    assert fake.last_body is not None
    assert fake.last_body["stream"] is True


# ============ 非流式 /v1/chat 接真上游（#8/#46 / 决策 53）============


def _llm_calls(db: Path) -> list[tuple[object, ...]]:
    """绕过 API 直接查 llm_calls：每行 (model, status, prompt, completion, total)"""
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT model, status, prompt_tokens, completion_tokens, total_tokens "
            "FROM llm_calls ORDER BY id"
        ).fetchall()
        return [tuple(row) for row in rows]
    finally:
        conn.close()


def test_chat_returns_upstream_content_and_records_tokens(
    client: TestClient, db_path: Path
) -> None:
    """回归：/v1/chat 必须回上游正文 + usage_tokens，并落一行 completed 账单"""
    fake = FakeLlm()  # 默认 completion: content="fake answer", usage 5/3/8
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post("/v1/chat", json=REQ)

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "fake answer"
    # 【注意】：这条是「还是 echo 吗」的判据 —— 少了它，把实现改回占位也能全绿
    assert "[echo]" not in body["content"]
    assert body["usage_tokens"] == 8

    rows = _llm_calls(db_path)
    assert len(rows) == 1, f"应当恰好落一行账单，实际 {rows}"
    _, status, prompt, completion, total = rows[0]
    assert (status, prompt, completion, total) == ("completed", 5, 3, 8)


def test_chat_requests_non_stream_explicitly(client: TestClient) -> None:
    """回归：发给上游的 body 必须【显式】带 stream=False，且带 max_tokens 兜底"""
    fake = FakeLlm()
    app.dependency_overrides[get_llm_client] = lambda: fake

    client.post("/v1/chat", json=REQ)

    body = fake.last_complete_body
    assert body is not None
    # 【注意】：先断言"键存在"—— 否则省略了这个键时 `is False` 的断言根本不会执行到（假绿）
    assert "stream" in body, "必须显式带上 stream 键（省略时由上游默认值决定）"
    assert body["stream"] is False
    # 客户端没给 max_tokens 时必须落到服务端上限，不能"不传 = 不限制"
    assert body["max_tokens"] == settings.max_tokens_ceiling


def test_chat_upstream_error_becomes_502(client: TestClient) -> None:
    """回归：上游挂了必须透传成 502，不是 200 + 空正文"""
    fake = FakeLlm(complete_error=AppError(code="UPSTREAM_UNREACHABLE", message="上游挂了"))
    app.dependency_overrides[get_llm_client] = lambda: fake

    response = client.post("/v1/chat", json=REQ)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_UNREACHABLE"


def test_tests_cannot_reach_real_upstream(client: TestClient) -> None:
    """哨兵自检：没有 override 的用例一旦真调上游就【报错】（不是静默替换成假数据）

    【注意】：如果哨兵改成"静默返回 FakeLlm"，这条会绿 —— 那正是我们要防的假绿
    """
    app.dependency_overrides.pop(get_llm_client, None)

    with pytest.raises(RealUpstreamForbidden, match="真调上游"):
        client.get("/v1/upstream/models")
