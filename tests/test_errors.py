"""错误响应契约测试：任何错误都必须是同一种形状"""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_settings


def _assert_error_envelope(
    response: Any, expected_status: int, expected_code: str
) -> dict[str, Any]:
    """统一断言：状态码 + 顶层只有 error + 三键齐全 + 头与 body 的 request_id 一致"""
    assert response.status_code == expected_status

    body = response.json()
    assert set(body) == {"error"}, f"顶层只能有一个 error 键，实际是 {set(body)}"

    error = body["error"]
    assert set(error) == {"code", "message", "request_id"} or set(error) == {
        "code",
        "message",
        "request_id",
        "details",
    }, f"error 里只能是三键（422 多一个 details），实际是 {set(error)}"
    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert error["message"]
    assert isinstance(error["request_id"], str)
    assert error["request_id"]
    assert response.headers["x-request-id"] == error["request_id"]

    return cast(dict[str, Any], error)


@pytest.mark.parametrize(
    ("method", "url", "payload", "status", "code"),
    [
        pytest.param(
            "PUT", "/v1/conversations", {"title": "x"}, 405, "METHOD_NOT_ALLOWED", id="method"
        ),
        pytest.param(
            "POST",
            "/v1/chat",
            {"messages": [{"role": "assistant", "content": "hi"}]},
            400,
            "LAST_MESSAGE_NOT_USER",
            id="business_400",
        ),
        pytest.param("GET", "/v1/models/nope", None, 404, "MODEL_NOT_FOUND", id="model"),
        pytest.param("GET", "/v1/nope", None, 404, "NOT_FOUND", id="route"),
        pytest.param(
            "GET", "/v1/conversations/999", None, 404, "CONVERSATION_NOT_FOUND", id="conversation"
        ),
    ],
)
def test_error_envelope(
    client: TestClient,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    status: int,
    code: str,
) -> None:
    response = client.request(method, url, json=payload)
    _assert_error_envelope(response, status, code)


def test_422_details_do_not_echo_input(client: TestClient) -> None:
    response = client.post("/v1/chat", json={"messages": []})
    error = _assert_error_envelope(response, 422, "VALIDATION_ERROR")

    details = error["details"]
    assert isinstance(details, list)
    assert details

    first = details[0]
    assert set(first) == {"loc", "msg", "type"}, "details 只允许 loc/msg/type，不回显用户原值"
    assert first["loc"] == ["body", "messages"]
    assert first["type"] == "too_short"


def test_500_hides_internals() -> None:
    """500 只回一句人话 + request_id，堆栈只进日志

    不用 client fixture：要拿 500 的响应体必须 raise_server_exceptions=False，
    而共享 fixture 用的是默认 True（真实 bug 直接抛栈，定位更快）
    """

    def boom() -> Any:
        raise RuntimeError("内部细节不该出现在响应里")

    app.dependency_overrides[get_settings] = boom
    try:
        with TestClient(app, raise_server_exceptions=False) as raw:
            response = raw.post("/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        error = _assert_error_envelope(response, 500, "INTERNAL_ERROR")
    finally:
        app.dependency_overrides.clear()

    assert error["message"] == "服务内部错误"
    assert "RuntimeError" not in response.text
    assert "内部细节" not in response.text
