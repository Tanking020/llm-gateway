"""并发流的真实进程测试：TestClient 没有 TCP 背压，测不出连接被整条流占住（#59 / #73）"""

import asyncio
import sqlite3
import threading
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from conftest import AUTH_HEADERS, reset_db

from app.api.app import app
from app.api.deps import get_llm_client
from app.llm_client import LlmChatStream
from fakes import FakeChatStream, FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}
STREAM_SECONDS = 1.0
CHUNKS = 3
USAGE = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}


class _SlowStream(FakeChatStream):
    """每 ~0.33s 吐一帧，总共约 1s —— 模拟真实的 LLM 流，让并发窗口足够宽"""

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
    # 【注意】：把闸门放大 —— 本文件测的是"流会不会串行"，不是闸门容量。
    #   不放大的话：把 MAX_CONCURRENT_UPSTREAM_CALLS 调小（比如 2），4 并发用例会收到 503
    #   而变红，报错方向完全跑偏
    app.state.upstream_semaphore = asyncio.Semaphore(32)
    # 本文件不经过 client fixture（它要真 TCP），所以身份与清库得自己做
    reset_db()
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
        async with client.stream(
            "POST", f"{base}/v1/chat/stream", json=REQ, headers=AUTH_HEADERS
        ) as response:
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


def test_two_concurrent_streams_do_not_serialize(live_server: str) -> None:
    """两条流同时跑：总耗时约等于单流，而不是两倍

    【注意】：断言的是「首字节耗时」而不是总耗时 —— 串行时第二个请求的 TTFB
        约等于整条流的时长（1s），并发时只有几十毫秒，差一个数量级，阈值取中间才不会抖

    """
    results = _concurrent(live_server, 2)
    assert max(ttfb for _, ttfb, _ in results) < STREAM_SECONDS / 2


def test_four_concurrent_streams_all_start_immediately(live_server: str) -> None:
    """四个用户同时进来，每个人都不该等前面的人说完才看到第一个字"""
    results = _concurrent(live_server, 4)
    assert max(ttfb for _, ttfb, _ in results) < STREAM_SECONDS / 2
    assert all(frames == 7 for _, _, frames in results)


def test_pending_row_is_visible_while_stream_is_running(live_server: str, db_path: Path) -> None:
    """流跑到一半时，库里必须已经有这一行 pending —— 说明它被 commit 过，不是 flush

    【注意】：这条只能在真 uvicorn 下测 —— TestClient 会先攒齐整个响应体再交给我们，
        看到第一块时流早已结束，永远观察不到中间态
    """

    def latest() -> tuple[object, ...] | None:
        conn = sqlite3.connect(str(db_path))
        try:
            found = conn.execute(
                "SELECT status, prompt_tokens FROM llm_calls ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return tuple(found) if found else None
        finally:
            conn.close()

    async def probe() -> tuple[object, ...] | None:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST", f"{live_server}/v1/chat/stream", json=REQ, headers=AUTH_HEADERS
            ) as r:
                pieces = r.aiter_text()
                await pieces.__anext__()  # 推进到第一帧
                snapshot = latest()  # 此刻流还在跑
                async for _ in pieces:
                    pass
        return snapshot

    assert asyncio.run(probe()) == ("pending", 0)
