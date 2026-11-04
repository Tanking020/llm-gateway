"""上游适配器接线测试：用假 LLM 证明路由真的走了依赖注入，且上游故障都变 502"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client
from app.errors import AppError
from app.schemas import ModelItem
from fakes import FakeLlm


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
