"""适配器的【真实 HTTP 路径】：从下面喂数据，把 L1 / L2 / L3 三档翻译钉住

【注意】：这个文件必须 import httpx —— 它要造 MockTransport。这是 TID251 的例外，
    判据同 test_stream_adapter.py：它不绕过适配器调上游，而是往适配器【里面】喂数据
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from app import llm_client
from app.config import Settings
from app.errors import AppError
from app.llm_client import MAX_ERROR_BODY_CHARS, LlmClient, LlmCompletion

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


@pytest.mark.parametrize(
    ("http_status", "body", "want"),
    [
        pytest.param(429, b'{"error":"slow down"}', "UPSTREAM_RATE_LIMITED", id="429"),
        pytest.param(413, b'{"error":"too big"}', "UPSTREAM_PAYLOAD_TOO_LARGE", id="413"),
        pytest.param(401, b'{"error":"bad key"}', "UPSTREAM_AUTH_FAILED", id="401"),
        pytest.param(403, b'{"error":"forbidden"}', "UPSTREAM_AUTH_FAILED", id="403"),
        pytest.param(400, b'{"error":"bad model"}', "UPSTREAM_REJECTED", id="400"),
        pytest.param(404, b'{"error":"no route"}', "UPSTREAM_REJECTED", id="404"),
    ],
)
def test_status_code_is_translated_for_the_client(http_status: int, body: bytes, want: str) -> None:
    """L2 细分：按「客户端能不能靠自己修好」分档

    能修（429 等一等 / 413 缩短）-> 业务码直接对应 4xx
    修不了（我们的密钥 / 我们发的 body）-> 502 + 细分码
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(http_status, content=body)

    assert _raise_from(handler).code == want


def test_rate_limited_keeps_retry_after_header() -> None:
    """上游给了 Retry-After 就必须带给客户端 —— 否则它不知道该等几秒"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b"{}", headers={"retry-after": "7"})

    assert _raise_from(handler).headers == {"Retry-After": "7"}


def test_non_429_does_not_carry_retry_after() -> None:
    """只有 429 才带 —— 别的错误带这个头会让客户端误以为「等一会儿就好」"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"{}", headers={"retry-after": "7"})

    assert _raise_from(handler).headers == {}


@pytest.mark.parametrize(
    ("body", "why"),
    [
        pytest.param(
            b'{"error":{"code":"context_length_exceeded"}}', "写在 error.code 里", id="code"
        ),
        pytest.param(
            b'{"error":{"message":"maximum context length is 65536 tokens"}}',
            "只写在 message 里",
            id="message",
        ),
    ],
)
def test_context_too_long_is_told_as_413(body: bytes, why: str) -> None:
    """上游 400 里「上下文超长」这一档其实是客户端能修的（缩短消息）-> 翻成 413"""
    assert why

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=body)

    assert _raise_from(handler).code == "UPSTREAM_PAYLOAD_TOO_LARGE"


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


async def _slow_models(request: httpx.Request) -> httpx.Response:
    """上游「太慢」：连得上、也在回包，但超出我们的总预算"""
    await asyncio.sleep(0.3)
    return httpx.Response(200, json={"data": []})


def test_list_models_is_cut_by_total_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归 #55：总时长超预算 → UPSTREAM_TIMEOUT（504），不是无限期挂着

    【注意】：预算读的是适配器里的【模块级 settings】（与 request_timeout 同一来源）
    """
    monkeypatch.setattr(llm_client, "settings", Settings(upstream_total_timeout=0.05))

    async def scenario() -> AppError:
        transport = httpx.MockTransport(_slow_models)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            with pytest.raises(AppError) as exc_info:
                await LlmClient(http).list_models()
        return exc_info.value

    assert asyncio.run(scenario()).code == "UPSTREAM_TIMEOUT"


# ============ 非流式补全 complete()（#8/#46）============


def test_complete_returns_content_and_usage() -> None:
    """适配器：200 且结构正常 -> 正文与 usage 原样取出"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "你好"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )

    async def scenario() -> LlmCompletion:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            return await LlmClient(http).complete({"stream": False})

    result = asyncio.run(scenario())
    assert result.content == "你好"
    assert result.usage == {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    # 反向证据：usage 不能是空 dict —— 否则「永远返回 {}」的实现也能让上面那条变绿
    assert result.usage


def test_complete_usage_stays_a_plain_dict() -> None:
    """决策守卫（决策 54）：usage 必须是真 dict，不许换成 MappingProxyType

    为什么必须有这条：换容器类型是【源码重构】，全程没有运行时赋值 —— frozen 拦不到，
    上一个用例的 `==` 也拦不到（mappingproxy == dict 为 True），而下游 `isinstance(x, dict)`
    的收窄守卫会把非 dict 【静默】归一成 {}：记账变 0、接口照常 200、日志无异常。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"content": "hi"}}],
                "usage": {"total_tokens": 1},
            },
        )

    async def scenario() -> LlmCompletion:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            return await LlmClient(http).complete({"stream": False})

    assert isinstance(asyncio.run(scenario()).usage, dict)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"choices": []}, id="empty_choices"),
        pytest.param({"choices": [{"message": {"content": None}}]}, id="content_null"),
        pytest.param({"choices": [{"message": {"content": 123}}]}, id="content_int"),
        pytest.param({"error": "boom"}, id="error_body"),
    ],
)
def test_complete_malformed_becomes_malformed(payload: dict[str, Any]) -> None:
    """适配器 L3：200 但结构不对 -> UPSTREAM_MALFORMED（不是 500）"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async def scenario() -> AppError:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            with pytest.raises(AppError) as exc_info:
                await LlmClient(http).complete({})
        return exc_info.value

    assert asyncio.run(scenario()).code == "UPSTREAM_MALFORMED"


def test_complete_is_cut_by_total_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归 #55 同款：非流式也必须有【总预算】，否则滴答式慢响应会一直挂着"""

    async def _slow_complete(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, json={"choices": [{"message": {"content": "太慢了"}}]})

    monkeypatch.setattr(llm_client, "settings", Settings(upstream_total_timeout=0.05))

    async def scenario() -> AppError:
        transport = httpx.MockTransport(_slow_complete)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as http:
            with pytest.raises(AppError) as exc_info:
                await LlmClient(http).complete({})
        return exc_info.value

    assert asyncio.run(scenario()).code == "UPSTREAM_TIMEOUT"


def test_client_factory_splits_connect_timeout_and_omits_empty_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """回归 #18：建连超时单独收紧；没有 key 时不能拼出 `Bearer None`

    【注意】：直接调工厂 —— 「拼头」发生在工厂里，而测试哨兵只替换了 `app.api.app` 里那一份引用
    """
    monkeypatch.setattr(llm_client, "settings", Settings(llm_api_key=None))

    http = llm_client.create_llm_client()._http

    assert "authorization" not in http.headers
    assert http.timeout.connect == pytest.approx(3.0)
    assert http.timeout.read == pytest.approx(30.0)
