"""SSE流式的【帧】契约：上游给什么，客户端就必须拿到什么（或不拿到什么）"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client
from fakes import FakeLlm

REQ = {"messages": [{"role": "user", "content": "hi"}]}


def _frames(body: str) -> list[Any]:
    """把 SSE body 拆成帧：`data: <json>` 或 `data: [DONE]`，帧之间是两个换行"""
    out: list[Any] = []
    for block in body.split("\n\n"):
        if not block:
            continue
        assert block.startswith("data: "), f"非法帧（缺 data: 前缀或空格）：{block!r}"
        raw = block[len("data: ") :]
        out.append("[DONE]" if raw == "[DONE]" else json.loads(raw))
    return out


def _stream(client: TestClient, chunks: list[dict[str, Any]]) -> list[Any]:
    """
    把 FakeLlm 注入到应用里，发一个流式请求，收集所有帧并返回。
    让每个测试用例不用重复写"注入依赖 + 发请求 + 解析响应"这三步
    """
    app.dependency_overrides[get_llm_client] = lambda: FakeLlm(chunks=chunks)
    try:
        with client.stream("POST", "/v1/chat/stream", json=REQ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            # .iter_text() 每次吐出的块，不保证正好是一帧。可能是半帧、一帧半、多帧
            # 所以我们把流式响应的所有文本拼成一个完整字符串，再交给 _frames 拆成帧列表
            return _frames("".join(response.iter_text()))
    finally:
        app.dependency_overrides.clear()


def _has_key(frames: list[Any], key: str) -> bool:
    """检查帧列表里面有没有哪一帧带某个字段 key"""
    return any(isinstance(f, dict) and key in f for f in frames)


def _error_codes(frames: list[Any]) -> list[str]:
    return [f["error"]["code"] for f in frames if isinstance(f, dict) and "error" in f]


def test_first_frame_is_thinking(client: TestClient) -> None:
    """首帧必须是状态帧：前端靠它立刻显示「思考中」，不等上游"""
    frames = _stream(client, [{"choices": [{"index": 0, "delta": {"content": "你"}}]}])
    assert frames[0] == {"status": "thinking"}


def test_normal_stream_frame_order(client: TestClient) -> None:
    """正常流的帧序：内容 / 结束原因 / 用量都按上游给的顺序翻译，末尾一定有 [DONE]

    【注意】：usage 出现在最后一个 delta 【之前】—— 前端不能假设
    「收到 finish_reason 就代表内容结束」（见 §12.5c）
    """
    frames = _stream(
        client,
        [
            {"choices": [{"index": 0, "delta": {"content": "你"}}]},
            {
                "choices": [{"index": 0, "delta": {"content": "好"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        ],
    )
    assert frames == [
        {"status": "thinking"},
        {"delta": "你"},
        {"finish_reason": "stop"},
        {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
        {"delta": "好"},
        "[DONE]",
    ]


@pytest.mark.parametrize(
    "chunks",
    [
        pytest.param(
            [{"choices": [{"index": 0, "delta": {"content": ["数组"]}}]}], id="content_not_str"
        ),
        pytest.param([{"choices": {"index": 0}}], id="choices_not_list"),
        pytest.param([{"choices": ["x"]}], id="choice_not_dict"),
        pytest.param(
            [{"choices": [{"index": 1, "delta": {"content": "XX"}}]}], id="index_not_zero"
        ),
        pytest.param([{"choices": [{"index": 0, "delta": "x"}]}], id="delta_not_dict"),
        pytest.param(
            [{"choices": [{"index": 0, "delta": {"reasoning_content": "想"}}]}], id="reasoning_only"
        ),
        pytest.param([], id="no_chunks"),
    ],
)
def test_unusable_upstream_content_becomes_no_content_error(
    client: TestClient, chunks: list[dict[str, Any]]
) -> None:
    """上游给了东西，但没有一个能用 → 必须显式说「这次没拿到内容」

    【注意】：200 + 空内容和「模型真的说了空」在前端长得一模一样，
    所以必须发一条 STREAM_NO_CONTENT，不能让前端以为回答就是空的
    """
    frames = _stream(client, chunks)

    assert _error_codes(frames) == ["STREAM_NO_CONTENT"]
    assert not _has_key(frames, "delta")
    assert frames[-1] == "[DONE]"


def test_finish_reason_must_be_string(client: TestClient) -> None:
    """finish_reason 不是字符串 → 不转发（前端的 === "stop" 会静默失效），但内容照常"""
    frames = _stream(
        client,
        [{"choices": [{"index": 0, "delta": {"content": "A"}, "finish_reason": {"x": 1}}]}],
    )

    assert {"delta": "A"} in frames
    assert not _has_key(frames, "finish_reason")
    assert _error_codes(frames) == []


def test_empty_choices_with_usage(client: TestClient) -> None:
    """choices 为空列表的帧是「纯用量帧」：记用量并转发，但没有内容 → 仍然报零内容

    【注意】：这条同时钉住两件互不冲突的事 —— 用量拿到了、内容没有
    """
    frames = _stream(
        client,
        [{"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}],
    )

    assert _has_key(frames, "usage")
    assert not _has_key(frames, "delta")
    assert _error_codes(frames) == ["STREAM_NO_CONTENT"]


def test_frames_after_finish_reason_are_still_processed(client: TestClient) -> None:
    """`finish_reason` 只表示"这一路说完了"，**不是流结束** —— 后面还可能有帧

    【注意】：这是最容易写错的一处。若代码在转发 finish_reason 后 `break`：
      ① 漏掉同一帧里的最后一个 content（本帧 delta 在 finish 之后才处理）
      ② 漏掉 OpenAI `stream_options.include_usage` 那种【finish 之后才来】的纯用量帧 → 账单丢账
    终止条件只能是【上游 EOF】，见 §12.5c
    """
    frames = _stream(
        client,
        [
            {"choices": [{"index": 0, "delta": {"content": "第一段"}, "finish_reason": "stop"}]},
            {"choices": [{"index": 0, "delta": {"content": "第二段"}}]},
            {
                "choices": [],
                "usage": {"prompt_tokens": 7, "completion_tokens": 8, "total_tokens": 15},
            },
        ],
    )

    assert {"delta": "第一段"} in frames
    assert {"delta": "第二段"} in frames
    assert {"usage": {"prompt_tokens": 7, "completion_tokens": 8, "total_tokens": 15}} in frames
    assert _error_codes(frames) == []
    assert frames[-1] == "[DONE]"
