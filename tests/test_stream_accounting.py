"""账单层的契约：一次流式调用必须留下一行【能对账】的记录"""

import json
import logging
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.app import _as_int, app
from app.api.deps import get_llm_client
from app.llm_client import LlmChatStream
from app.models import LlmCallStatus
from fakes import FakeChatStream, FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}

# 上游给的一份完整用量（真实形状：DeepSeek 把它和 finish_reason 挤在同一帧）
USAGE = {"prompt_tokens": 31, "completion_tokens": 7, "total_tokens": 38}


class _BrokenStream(FakeChatStream):
    """吐一帧之后再抛异常：模拟「流已经开始之后上游才断」"""

    async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
        yield {"choices": [{"index": 0, "delta": {"content": "大"}}]}
        raise RuntimeError("上游连接断了")


class _BrokenLlm(FakeLlm):
    """不管请求体长什么样，都交给 _BrokenStream"""

    async def open_chat_stream(self, body: dict[str, object]) -> LlmChatStream:
        return _BrokenStream([])


def _run(client: TestClient, llm: FakeLlm) -> None:
    """注入给定的假上游 → 发一次流式请求 → 把流读干净（读干净 app 才会提交账单）"""
    app.dependency_overrides[get_llm_client] = lambda: llm
    try:
        with client.stream("POST", "/v1/chat/stream", json=REQ) as response:
            assert response.status_code == 200
            _ = "".join(response.iter_text())
    finally:
        app.dependency_overrides.clear()


def _stream(client: TestClient, chunks: list[dict[str, Any]]) -> None:
    """按一段 chunk 列表造一个假上游"""
    _run(client, FakeLlm(chunks=chunks))


def _frames(client: TestClient, chunks: list[dict[str, Any]]) -> list[Any]:
    """发一次流式请求并返回解析后的帧列表（`data: <json>` 或 `[DONE]`）

    【注意】：与 `_stream` 的区别是它保留响应体 —— 要断言「客户端到底看到了什么」时用它
    """
    app.dependency_overrides[get_llm_client] = lambda: FakeLlm(chunks=chunks)
    try:
        with client.stream("POST", "/v1/chat/stream", json=REQ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
    finally:
        app.dependency_overrides.clear()

    frames: list[Any] = []
    for block in body.split("\n\n"):
        if not block:
            continue
        raw = block[len("data: ") :]
        frames.append("[DONE]" if raw == "[DONE]" else json.loads(raw))
    return frames


def _rows(db: Path) -> list[tuple[Any, ...]]:
    """绕过 API 直接查库：每行是 (status, prompt, completion, total)，按 id 升序"""
    conn = sqlite3.connect(str(db))
    try:
        cursor = conn.execute(
            "SELECT status, prompt_tokens, completion_tokens, total_tokens "
            "FROM llm_calls ORDER BY id"
        )
        return [tuple(row) for row in cursor]
    finally:
        conn.close()


def test_normal_stream_records_completed_with_tokens(client: TestClient, db_path: Path) -> None:
    """正常路径：拿到 usage -> status=completed，三个 token 数都落库"""
    _stream(
        client,
        [
            {"choices": [{"index": 0, "delta": {"content": "好"}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": USAGE},
        ],
    )
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_usage_survives_when_choices_is_not_a_list(client: TestClient, db_path: Path) -> None:
    """choices 结构坏了，但同一帧的 usage 是好的 -> 金额必须落库"""
    _stream(client, [{"choices": {"a": 1}, "usage": USAGE}])
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_usage_survives_when_choice_is_not_an_object(client: TestClient, db_path: Path) -> None:
    """choices[0] 不是对象（如字符串），同一帧的 usage 仍必须落库"""
    _stream(client, [{"choices": ["x"], "usage": USAGE}])
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_usage_survives_when_index_is_not_zero(client: TestClient, db_path: Path) -> None:
    """候选 index 不是 0（多候选上游），同一帧的 usage 仍必须落库"""
    _stream(client, [{"choices": [{"index": 1, "delta": {"content": "别"}}], "usage": USAGE}])
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_as_int_rejects_bool() -> None:
    """回归：bool 是 int 的子类 —— `_as_int(True)` 必须记 0，不能记成 1 token（#53）"""
    assert _as_int(True) == 0
    assert _as_int(False) == 0
    # 反向证据：真的整数照样通过，否则上面两条可能只是因为函数恒返回 0
    assert _as_int(7) == 7


def test_index_not_zero_is_logged(client: TestClient) -> None:
    """回归：丢弃非 0 候选时必须留一行 warning —— 目的是【服务端取证】（#72）

    【注意】：不是「客户端缺字」—— 📎 实测 index=0 的帧本身构成完整答案；
        只有当【全部】帧都是 index≠0 时客户端才拿不到内容，而那时它会收到
        STREAM_NO_CONTENT 错误帧（下面第二条反向证据钉住这个既有行为）
    """

    class _Collect(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.messages.append(record.getMessage())

    handler = _Collect()
    # 【注意】：直接挂在 app 模块的 logger 上 —— dictConfig 之后应用 logger 可能不向 root 传播，
    #   caplog 会捕不到
    target = logging.getLogger("app.api.app")
    target.addHandler(handler)
    try:
        _stream(client, [{"choices": [{"index": 1, "delta": {"content": "别"}}]}])
    finally:
        target.removeHandler(handler)

    assert any("index" in m for m in handler.messages), (
        f"丢弃非 0 候选时没有 warning，日志：{handler.messages}"
    )

    # 反向证据 1：交错 0/1 时主答案必须【完整】—— 丢的是备选候选，不是主答案里的字
    frames = _frames(
        client,
        [
            {"choices": [{"index": 0, "delta": {"content": "客"}}]},
            {"choices": [{"index": 1, "delta": {"content": "别"}}]},
            {"choices": [{"index": 0, "delta": {"content": "户"}}]},
        ],
    )
    text = "".join(f["delta"] for f in frames if "delta" in f)
    assert text == "客户", f"主答案被破坏：{text!r}（完整帧：{frames}）"

    # 反向证据 2：全部是 index≠0 时，客户端拿到的是 STREAM_NO_CONTENT，不是静默空答复
    frames = _frames(client, [{"choices": [{"index": 1, "delta": {"content": "别"}}]}])
    assert {"error": {"code": "STREAM_NO_CONTENT", "message": "上游未返回任何内容"}} in frames, (
        f"帧全被丢弃时应当明确告知客户端，实际帧：{frames}"
    )


def test_duplicate_usage_is_recorded_only_once(client: TestClient, db_path: Path) -> None:
    """上游在好几帧里重复给 usage：只认第一份，绝不重复扣费"""
    _stream(
        client,
        [
            {"choices": [{"index": 0, "delta": {"content": "好"}}], "usage": USAGE},
            {"choices": [], "usage": {"prompt_tokens": 999, "completion_tokens": 999}},
        ],
    )
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_empty_upstream_is_recorded_as_no_content(client: TestClient, db_path: Path) -> None:
    """上游一帧都没给（空 body / HTML）-> 金额不确定，记 no_content"""
    _stream(client, [])
    assert _rows(db_path) == [("no_content", 0, 0, 0)]


def test_pure_thinking_stream_is_recorded_as_no_content(client: TestClient, db_path: Path) -> None:
    """只拿到思维链、没内容也没 usage -> 同样记 no_content"""
    _stream(client, [{"choices": [{"index": 0, "delta": {"reasoning_content": "想"}}]}])
    assert _rows(db_path) == [("no_content", 0, 0, 0)]


def test_zero_content_with_usage_stays_completed(client: TestClient, db_path: Path) -> None:
    """零内容但拿到了 usage：钱准了 -> 仍是 completed（内容空不空归日志管，不归账单管）"""
    _stream(
        client,
        [{"choices": [{"index": 0, "delta": {"role": "assistant"}}], "usage": USAGE}],
    )
    assert _rows(db_path) == [("completed", 31, 7, 38)]


def test_status_enum_values_are_pinned() -> None:
    """状态值就是数据库里的字面量：拼错一个字母，对账查询就永远查不到那一行

    【注意】：StrEnum 只防【成员名】拼错（mypy 抓），不防【值】拼错 —— 值必须靠断言钉住
    """
    assert {member.value for member in LlmCallStatus} == {
        "pending",
        "completed",
        "aborted",
        "no_content",
    }


def test_stream_broken_after_first_frame_is_recorded_as_aborted(
    client: TestClient, db_path: Path
) -> None:
    """流开始后抛异常 -> aborted（上游可能已计费，但数字拿不到）"""
    _run(client, _BrokenLlm())
    assert _rows(db_path) == [("aborted", 0, 0, 0)]
