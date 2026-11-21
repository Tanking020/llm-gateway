"""错误响应契约测试：任何错误都必须是同一种形状"""

import logging
from typing import Any, cast
from unittest.mock import patch

import pytest
from conftest import AUTH_HEADERS
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import app
from app.api.deps import get_settings
from app.config import Settings
from app.errors import AppError, register_exception_handlers


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
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            response = raw.post("/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        error = _assert_error_envelope(response, 500, "INTERNAL_ERROR")
    finally:
        app.dependency_overrides.clear()

    assert error["message"] == "服务内部错误"
    assert "RuntimeError" not in response.text
    assert "内部细节" not in response.text


def test_500_carries_the_same_cors_headers_as_other_errors() -> None:
    """回归 #57：500 由最外层 ServerErrorMiddleware 产出，不经过 CORSMiddleware ——
    浏览器里前端会只看到「网络错误」，连 request_id 都读不到"""

    def boom() -> Any:
        raise RuntimeError("boom")

    app.dependency_overrides[get_settings] = boom
    try:
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            origin = {"Origin": "http://localhost:5173"}
            r500 = raw.post(
                "/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers=origin
            )
            r404 = raw.get("/v1/conversations/999999", headers=origin)
    finally:
        app.dependency_overrides.clear()

    def cors(response: Any) -> dict[str, str]:
        return {
            k.lower(): v
            for k, v in response.headers.items()
            if k.lower().startswith(("access-control", "vary"))
        }

    assert r500.status_code == 500
    assert cors(r500) == cors(r404), "500 的 CORS 头必须与普通错误响应一致"
    assert cors(r500)["access-control-allow-origin"] == "http://localhost:5173"


def test_500_does_not_echo_a_foreign_origin() -> None:
    def boom() -> Any:
        raise RuntimeError("boom")

    app.dependency_overrides[get_settings] = boom
    try:
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            r = raw.post(
                "/v1/chat",
                json={"messages": [{"role": "user", "content": "hi"}]},
                headers={"Origin": "http://evil.example"},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 500
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_db_unavailable_returns_503(client: TestClient) -> None:
    """回归 #83：连不上库是【依赖不可用】→ 503 + Retry-After，不是 500"""

    async def no_connection(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError(
            "PRAGMA foreign_keys=ON", {}, Exception("unable to open database file")
        )

    with patch.object(AsyncSession, "connection", no_connection):
        response = client.post(
            "/v1/conversations",
            json={"title": "x"},
            headers={"Origin": "http://localhost:5173"},
        )

    error = _assert_error_envelope(response, 503, "DB_UNAVAILABLE")
    assert response.headers["Retry-After"] == "1"
    # 503 走的是 AppError 处理器（在 CORSMiddleware 里面），所以 CORS 头必须在
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert error["message"] == "数据库不可用"


def test_sql_level_failure_stays_500() -> None:
    """反向守卫：SQL/表结构错了（同样是 OperationalError）不能被误判成「依赖不可用」

    📎 判据就是【抛出阶段】：connection() 抛 = 连不上（503）；execute() 抛 = 我们的代码有问题（500）
    不用 client fixture：要拿 500 的响应体必须 raise_server_exceptions=False
    """

    async def broken_sql(*args: Any, **kwargs: Any) -> Any:
        raise OperationalError("INSERT INTO conversations ...", {}, Exception("no such table"))

    with patch.object(AsyncSession, "execute", broken_sql):
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            response = raw.post("/v1/conversations", json={"title": "x"})

    _assert_error_envelope(response, 500, "INTERNAL_ERROR")


# ============ 封板前修复（#95 / #21 / #48 / #18）============


def _bare_app() -> FastAPI:
    """只有异常处理器的空 app：测「处理器本身」时不该依赖真实路由"""
    bare = FastAPI()
    register_exception_handlers(bare)
    return bare


def test_http_exception_keeps_its_headers() -> None:
    """回归 #95：HTTPException 自带的头必须活到响应里

    📎 401 的 WWW-Authenticate、429 的 Retry-After 都在这里；吞掉它 = 契约缺一块
    """
    bare = _bare_app()

    @bare.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=401, detail="nope", headers={"WWW-Authenticate": "ApiKey"})

    @bare.get("/hijack")
    async def hijack() -> None:
        raise HTTPException(status_code=400, detail="x", headers={"X-Request-ID": "evil"})

    with TestClient(bare) as c:
        response = c.get("/boom")
        hijacked = c.get("/hijack")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    # 反面：别人的头可以补，但 X-Request-ID 必须还是我们的
    assert hijacked.headers["x-request-id"] != "evil"


def test_unregistered_error_code_becomes_a_500(caplog: pytest.LogCaptureFixture) -> None:
    """回归 #21：未登记的业务码是【我们的 bug】→ 500 + error 日志，不能伪装成 400（客户端的错）"""
    bare = _bare_app()

    @bare.get("/boom")
    async def boom() -> None:
        raise AppError(code="NOT_REGISTERED_YET", message="x")

    with caplog.at_level(logging.ERROR, logger="app.errors"):
        with TestClient(bare) as c:
            response = c.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "NOT_REGISTERED_YET"
    assert "NOT_REGISTERED_YET" in caplog.text, "未登记必须是【喊出来】的，不是静默降级"


@pytest.mark.parametrize("path", ["/v1/chat", "/v1/chat/stream"])
def test_unknown_model_returns_404(client: TestClient, path: str) -> None:
    """回归 #48：model 必须在白名单内 —— 否则等于把上游 400 和「点单更贵的模型」漏给客户端"""
    response = client.post(
        path,
        json={"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o"},
    )

    error = _assert_error_envelope(response, 404, "MODEL_NOT_FOUND")
    assert "gpt-4o" in error["message"]


@pytest.mark.parametrize("path", ["/v1/chat", "/v1/chat/stream"])
def test_missing_upstream_key_returns_503(client: TestClient, path: str) -> None:
    """回归 #18：没配 key 时不能发 `Bearer None`（上游只会回 401，被误读成「密钥错」）"""
    app.dependency_overrides[get_settings] = lambda: Settings(llm_api_key=None)
    try:
        response = client.post(path, json={"messages": [{"role": "user", "content": "hi"}]})
    finally:
        app.dependency_overrides.pop(get_settings, None)

    _assert_error_envelope(response, 503, "LLM_NOT_CONFIGURED")
