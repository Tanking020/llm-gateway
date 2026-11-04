"""适配器的【真实 HTTP 路径】：从下面喂数据，把 L1 / L2 / L3 三档翻译钉住

【注意】：这个文件必须 import httpx —— 它要造 MockTransport。这是 TID251 的例外，
    判据同 test_stream_adapter.py：它不绕过适配器调上游，而是往适配器【里面】喂数据
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from app.errors import AppError
from app.llm_client import MAX_ERROR_BODY_CHARS, LlmClient

BASE = "http://upstream.test"
Handler = Callable[[httpx.Request], httpx.Response]

SSE = b'data: {"choices":[{"index":0,"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'


def _raise_from(handler: Handler, *, stream: bool = False) -> AppError:
    """用给定的 MockTransport 打一次上游，返回它抛出的 AppError（没抛出来就算失败）"""

    async def scenario() -> AppError:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            client = LlmClient(http)
            with pytest.raises(AppError) as exc_info:
                if stream:
                    await client.open_chat_stream({})
                else:
                    await client.list_models()
            return exc_info.value

    return asyncio.run(scenario())


def test_connect_failure_raises_upstream_unreachable() -> None:
    """L1：上游根本没回应（DNS / TCP / TLS 失败 / 超时）-> UPSTREAM_UNREACHABLE"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns 解析不了")

    assert _raise_from(handler).code == "UPSTREAM_UNREACHABLE"


def test_server_error_raises_upstream_bad_status() -> None:
    """L2：上游 5xx -> UPSTREAM_BAD_STATUS（不是 500，是 502）"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b'{"error":"boom"}')

    assert _raise_from(handler).code == "UPSTREAM_BAD_STATUS"


def test_redirect_is_also_bad_status() -> None:
    """L2 的边界：3xx 也算「状态码不对」

    【注意】：用 is_success(200~299) 才不会放过 3xx。若改成 `>= 400`，
    302 会溜进 list_models，然后在 response.json() 上炸成 UPSTREAM_MALFORMED —— 报错方向全错
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/elsewhere"})

    assert _raise_from(handler).code == "UPSTREAM_BAD_STATUS"


def test_malformed_json_raises_upstream_malformed() -> None:
    """L3 之一：200 但 body 不是 JSON（网关 HTML 错误页）-> UPSTREAM_MALFORMED"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>502 Bad Gateway</html>")

    assert _raise_from(handler).code == "UPSTREAM_MALFORMED"


def test_renamed_field_raises_upstream_malformed() -> None:
    """L3 之二：字段改名（data -> models）-> KeyError -> UPSTREAM_MALFORMED"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    assert _raise_from(handler).code == "UPSTREAM_MALFORMED"


def test_null_data_raises_upstream_malformed() -> None:
    """L3 之三：`{"data": null}` 不可迭代 -> TypeError -> UPSTREAM_MALFORMED"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": None})

    assert _raise_from(handler).code == "UPSTREAM_MALFORMED"


def test_list_models_drops_unknown_keys() -> None:
    """L3 正常路径：上游给 4 个键，我们只留白名单里的 3 个"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "m1", "object": "model", "owned_by": "x", "extra": "丢掉"}]},
        )

    async def scenario() -> list[str]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            return [item.id for item in await LlmClient(http).list_models()]

    assert asyncio.run(scenario()) == ["m1"]


def test_open_chat_stream_parses_chunks() -> None:
    """pre-flight 成功后返回的流：原始 SSE 字节能被解析成 dict"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SSE)

    async def scenario() -> list[object]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            stream = await LlmClient(http).open_chat_stream({"model": "m1"})
            try:
                return [chunk async for chunk in stream.aiter_chunks()]
            finally:
                await stream.aclose()

    assert asyncio.run(scenario()) == [{"choices": [{"index": 0, "delta": {"content": "hi"}}]}]


def test_error_body_is_logged_from_unread_stream(caplog: pytest.LogCaptureFixture) -> None:
    """流式失败响应：body 还没读，`.text` 会抛 ResponseNotRead -> 必须走 aread() 那条路

    【注意】：content 必须给【异步生成器】才能造出"还没读"的响应 ——
        给 bytes 时 MockTransport 已经把 body 灌进内存了，`.text` 不会抛（📎 实测）
    """
    caplog.set_level(logging.ERROR, logger="app.llm_client")

    async def body() -> AsyncIterator[bytes]:
        yield b'{"error":"stream-boom"}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=body())

    assert _raise_from(handler, stream=True).code == "UPSTREAM_BAD_STATUS"
    assert "stream-boom" in caplog.text


def test_error_body_is_truncated(caplog: pytest.LogCaptureFixture) -> None:
    """上游回一整页 HTML 时只留 MAX_ERROR_BODY_CHARS，防止日志被刷爆"""
    caplog.set_level(logging.ERROR, logger="app.llm_client")
    huge = "x" * (MAX_ERROR_BODY_CHARS * 2)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=huge.encode())

    _raise_from(handler)
    assert "x" * MAX_ERROR_BODY_CHARS in caplog.text
    assert "x" * (MAX_ERROR_BODY_CHARS + 1) not in caplog.text
