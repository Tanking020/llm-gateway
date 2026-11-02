"""账单层的契约：一次流式调用必须留下一行【能对账】的记录"""

import sqlite3
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client
from fakes import FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}

# 上游给的一份完整用量（真实形状：DeepSeek 把它和 finish_reason 挤在同一帧）
USAGE = {"prompt_tokens": 31, "completion_tokens": 7, "total_tokens": 38}


def _stream(client: TestClient, chunks: list[dict[str, Any]]) -> None:
    """注入假上游 → 发一次流式请求 → 把流读干净（读干净 app 才会提交账单）"""
    app.dependency_overrides[get_llm_client] = lambda: FakeLlm(chunks=chunks)
    try:
        with client.stream("POST", "/v1/chat/stream", json=REQ) as response:
            assert response.status_code == 200
            _ = "".join(response.iter_text())
    finally:
        app.dependency_overrides.clear()


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
    """choices 结构坏了，但同一帧的 usage 是好的 -> 金额必须落库

    【注意】：这是待办 #70 —— 记账块排在 choices 守卫之后，坏结构会把 usage 一起丢掉
    """
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
