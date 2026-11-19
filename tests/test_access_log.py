"""访问日志层：这一行能不能回答「是谁在打我们」（#56）

为什么不只测中间件：`client` 字段的来源有两条路径 ——
  ① 普通请求 → `request.client.host`
  ② 经代理 → uvicorn 的 ProxyHeadersMiddleware 用 X-Forwarded-For 改写
第 ② 条 `TestClient` 走 ASGI 直连，**根本不在栈里**，必须真起 uvicorn。
"""

import logging
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.app import _client_label, app

_ACCESS_LOGGER = "app.api.app"


def test_access_log_line_has_client_and_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """回归：每行访问日志都要能回答「谁 + 哪次请求」"""
    caplog.set_level(logging.INFO, logger=_ACCESS_LOGGER)
    client.get("/health")
    line = next(r.getMessage() for r in caplog.records if r.name == _ACCESS_LOGGER)
    assert "client=" in line, f"访问日志缺客户端 IP：{line}"
    assert "request_id=" in line


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        (None, "-"),
        ("", "-"),
        # 【注意】：换行能凭空造出一行假日志；空格与中文保留（它们不破坏行结构）
        ("1.2.3.4\n2026-01-01 ERROR fake", "1.2.3.42026-01-01 ERROR fake"),
        ("1.2.3.4\r\tX", "1.2.3.4X"),
        ("9" * 200, "9" * 64),
    ],
)
def test_client_label_neutralizes_external_input(raw: str | None, expected: str) -> None:
    """回归：客户端地址是外部输入，换行会让它伪造出一行假日志（CWE-117）"""
    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (raw, 1234) if raw is not None else None,
    }
    assert _client_label(Request(scope)) == expected


@pytest.fixture
def forged_xff_server() -> Iterator[tuple[str, list[str]]]:
    """真 uvicorn：信任名单里【没有】127.0.0.1，于是伪造的 XFF 必须被忽略

    【注意】：不能用 TestClient —— 它走 ASGI 直连，ProxyHeadersMiddleware 不在栈里，
        这条用例会在「守卫其实没生效」的情况下依然通过
    """
    lines: list[str] = []

    class _Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    handler = _Grab()
    logger = logging.getLogger(_ACCESS_LOGGER)
    logger.addHandler(handler)
    # 【注意】：pytest 默认把 root 设成 WARNING，访问日志是 INFO —— 不显式放开就会被静默丢掉
    #   （📎 实测：不设这一步，捕获到的是空列表，看起来像"中间件没执行"）
    original_level = logger.level
    logger.setLevel(logging.INFO)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=0,
            log_level="critical",
            lifespan="on",
            proxy_headers=True,
            # 【注意】：故意只信一个用不到的地址 → 127.0.0.1 变成「不可信对端」
            forwarded_allow_ips="10.9.9.9",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("uvicorn 10 秒内没起来")
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", lines
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        logger.removeHandler(handler)
        logger.setLevel(original_level)


def test_forged_xff_is_ignored_when_peer_is_not_the_trusted_proxy(
    forged_xff_server: tuple[str, list[str]],
) -> None:
    """回归：「只信自己那层」—— 不可信对端带的 X-Forwarded-For 一律不算数"""
    base, lines = forged_xff_server
    httpx.get(f"{base}/health", headers={"X-Forwarded-For": "1.2.3.4"})
    assert any("client=127.0.0.1" in line for line in lines), (
        f"伪造的 X-Forwarded-For 被采信了：{lines}"
    )
    assert not any("client=1.2.3.4" in line for line in lines)
