"""客户端中途断开时的收尾：上游必须被关、账单必须落 aborted

覆盖 `app.py` 的 `except BaseException` 分支（2026-11-26 补：此前该分支零覆盖）。

【注意】：必须起真 uvicorn —— TestClient 走 ASGI 直连，httpx 的 stream 上下文退出
    只影响本地缓冲区，服务端收不到取消信号，也就不会往生成器里抛 GeneratorExit。
    这条正是「并发是网络层行为，不是应用层行为」那个教训的延续。
"""

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

# 每帧 0.1s、共 20 帧 —— 窗口足够宽，客户端读一帧就断不会撞上"流已自然结束"
FRAME_COUNT = 20
FRAME_INTERVAL = 0.1


class _SlowStream(FakeChatStream):
    """慢慢吐帧，留出断开的窗口"""

    async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(FRAME_COUNT):
            await asyncio.sleep(FRAME_INTERVAL)
            yield {"choices": [{"index": 0, "delta": {"content": str(i)}}]}


class _TrackingLlm(FakeLlm):
    """记下最后返回的那条流，便于断言它被 aclose 过

    【注意】：不重写 `aclose`，直接用 `FakeChatStream.closed` —— 断言的是
        「路由真的调了 aclose」，不是「假对象自己改了标志位」
    """

    def __init__(self) -> None:
        super().__init__()
        self.last_stream: _SlowStream | None = None

    async def open_chat_stream(self, body: dict[str, object]) -> LlmChatStream:
        self.last_body = body
        self.last_stream = _SlowStream([])
        return self.last_stream


@pytest.fixture
def live_server() -> Iterator[tuple[str, _TrackingLlm]]:
    """起真实 uvicorn（随机端口），返回 (base_url, 假上游)"""
    llm = _TrackingLlm()
    app.dependency_overrides[get_llm_client] = lambda: llm
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
    # 放大闸门：本用例测的是断开收尾，不是闸门容量
    app.state.upstream_semaphore = asyncio.Semaphore(32)
    # 不经过 client fixture（要真 TCP），身份与清库自己来
    reset_db()
    try:
        yield f"http://127.0.0.1:{port}", llm
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()


def _statuses(db: Path) -> list[str]:
    """绕过 API 直接查库：每行账单的状态，按 id 升序"""
    conn = sqlite3.connect(str(db))
    try:
        cursor = conn.execute("SELECT status FROM llm_calls ORDER BY id")
        return [str(row[0]) for row in cursor]
    finally:
        conn.close()


def _wait_until(predicate: Any, timeout: float = 5.0) -> bool:
    """轮询等待异步发生的条件（取消 → aclose → 事务提交都不在同一拍）"""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_client_disconnect_closes_upstream_and_marks_aborted(
    live_server: tuple[str, _TrackingLlm], db_path: Path
) -> None:
    """客户端读一帧就断开 → 上游被 aclose，账单落 aborted（不是 pending 也不是 completed）"""
    base, llm = live_server

    with httpx.Client(timeout=30) as client:
        with client.stream(
            "POST", f"{base}/v1/chat/stream", json=REQ, headers=AUTH_HEADERS
        ) as response:
            assert response.status_code == 200
            # 只读一帧就退出 with —— 连接关闭，服务端开始走取消路径
            for piece in response.iter_text():
                if piece.strip():
                    break

    assert llm.last_stream is not None, "上游流没被创建，用例前提不成立"

    # ① 上游必须被关 —— 不关就是连接泄漏（池里的连接要等超时才回收）
    closed = _wait_until(lambda: llm.last_stream is not None and llm.last_stream.closed)
    assert closed, "客户端断开后上游没有被 aclose"

    # ② 账单必须落 aborted（断开时上游已产出的 token 照样计费，不能删行也不能留 pending）
    aborted = _wait_until(lambda: _statuses(db_path) == ["aborted"])
    assert aborted, f"断开后账单应为 ['aborted']，实际：{_statuses(db_path)}"
