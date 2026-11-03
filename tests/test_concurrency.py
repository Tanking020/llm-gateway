"""并发流的真实进程测试：TestClient 没有 TCP 背压，测不出连接被整条流占住（#59 / #73）"""

import asyncio
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import uvicorn

from app.api.app import app
from app.api.deps import get_llm_client
from app.llm_client import LlmChatStream
from fakes import FakeChatStream, FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}
STREAM_SECONDS = 0.6
CHUNKS = 3
USAGE = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

# 【注意】：这两条断言钉的是待办 #73 —— SQLite 只允许一个写者，而记账的写事务横跨整条流，
#   于是并发流被串行化（第 N 个用户的 TTFB = (N-1) x 单流时长）。修好后 XPASS 会变红，提醒删掉标记
SERIALIZED = pytest.mark.xfail(strict=True, reason="待办 #73：记账事务横跨整条流，并发流被串行化")


class _SlowStream(FakeChatStream):
    """每 0.2s 吐一帧，总共约 0.6s —— 模拟真实的 LLM 流，让并发窗口足够宽"""

    async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(CHUNKS):
            await asyncio.sleep(STREAM_SECONDS / CHUNKS)
            yield {"choices": [{"index": 0, "delta": {"content": str(i)}}]}
        yield {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": USAGE,
        }


class _SlowLlm(FakeLlm):
    async def open_chat_stream(self, body: dict[str, object]) -> LlmChatStream:
        return _SlowStream([])


@pytest.fixture
def live_server() -> Iterator[str]:
    """起一个真实的 uvicorn（随机端口），返回 base_url

    【注意】：必须真起进程内的 uvicorn —— TestClient 走 ASGI 直连，
    客户端一帧不读也不会产生背压，连接池占用测不出来
    """
    app.dependency_overrides[get_llm_client] = lambda: _SlowLlm()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="critical", lifespan="on")
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
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()


def _concurrent(base: str, count: int) -> list[tuple[float, float, int]]:
    """并发发 count 条流式请求，返回 [(总耗时, 首字节耗时, 帧数), ...]"""

    async def one(client: httpx.AsyncClient, out: list[Any]) -> None:
        start = time.perf_counter()
        first = None
        body = ""
        async with client.stream("POST", f"{base}/v1/chat/stream", json=REQ) as response:
            assert response.status_code == 200
            async for piece in response.aiter_text():
                if first is None and piece.strip():
                    first = time.perf_counter() - start
                body += piece
        frames = len([block for block in body.split("\n\n") if block])
        out.append((time.perf_counter() - start, first or 0.0, frames))

    async def run() -> list[Any]:
        out: list[Any] = []
        async with httpx.AsyncClient(timeout=60) as client:
            await asyncio.gather(*[one(client, out) for _ in range(count)])
        return out

    return asyncio.run(run())


def test_single_stream_has_all_frames(live_server: str) -> None:
    """基线：一条流正常跑完，帧数完整"""
    results = _concurrent(live_server, 1)
    assert results[0][2] == 7  # thinking + 3 delta + finish + usage + [DONE]


@SERIALIZED
def test_two_concurrent_streams_do_not_serialize(live_server: str) -> None:
    """两条流应该同时跑：总耗时约等于单流，而不是两倍"""
    results = _concurrent(live_server, 2)
    assert max(elapsed for elapsed, _, _ in results) < STREAM_SECONDS * 1.6


@SERIALIZED
def test_four_concurrent_streams_all_start_immediately(live_server: str) -> None:
    """四个用户同时进来，每个人都不该等前面的人说完才看到第一个字"""
    results = _concurrent(live_server, 4)
    assert max(ttfb for _, ttfb, _ in results) < STREAM_SECONDS / 2
