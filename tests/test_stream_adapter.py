"""上游适配器的协议层：原始 SSE 文本进来，必须是「只吐 dict」且坏帧不打断"""

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.llm_client import LlmChatStream


def _collect(raw: str) -> list[dict[str, Any]]:
    """把一段原始 SSE 文本喂给适配器，拿回它吐出的 chunk 列表

    【注意】：用 asyncio.run 驱动协程 —— 这里不需要 TestClient，
    也就不需要 pytest-asyncio 的 async 测试模式
    """

    async def run() -> list[dict[str, Any]]:
        response = httpx.Response(200, content=raw.encode("utf-8"))
        return [chunk async for chunk in LlmChatStream(response).aiter_chunks()]

    return asyncio.run(run())


def test_data_without_space_is_parsed() -> None:
    """`data:{…}`（冒号后没空格）是【合法 SSE】，必须能解析

    【注意】：旧写法 `line.startswith("data: ")` 会把整条流静默丢弃
    """
    assert _collect('data:{"n": 1}\n\n') == [{"n": 1}]


def test_extra_spaces_after_colon() -> None:
    """冒号后多几个空格也合法：lstrip 之后才是真正的数据"""
    assert _collect('data:    {"n": 1}\n\n') == [{"n": 1}]


def test_empty_data_line_is_skipped() -> None:
    """`data: ` 空行是【合法空事件】，跳过且【不打断后续帧】

    【注意】：旧写法直接 json.loads("") 会抛 JSONDecodeError，打断整条流
    """
    assert _collect('data: \n\ndata: {"n": 1}\n\n') == [{"n": 1}]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("null", id="null"),
        pytest.param("[1,2,3]", id="list"),
        pytest.param("123", id="number"),
        pytest.param('"abc"', id="string"),
    ],
)
def test_non_dict_payload_is_dropped_but_stream_continues(payload: str) -> None:
    """解析成功但不是 dict → 丢弃并继续（适配器的契约是「只吐 dict」）"""
    assert _collect(f'data: {payload}\n\ndata: {{"n": 1}}\n\n') == [{"n": 1}]


def test_non_data_lines_are_ignored() -> None:
    """注释行 `: xxx` 和 `event: ping` 都不以 `data:` 开头 → 跳过"""
    assert _collect(': 这是注释\nevent: ping\ndata: {"n": 1}\n\n') == [{"n": 1}]


def test_frames_after_done_are_ignored() -> None:
    """`[DONE]` 是传输层收尾标记，它之后的帧必须丢掉

    【注意】：不能 break —— 中途 break 会让 body 没读完，
    httpx 会销毁连接而不是归还连接池
    """
    assert _collect('data: {"i": 1}\n\ndata: [DONE]\n\ndata: {"i": 2}\n\n') == [{"i": 1}]


def test_multiple_frames_keep_order() -> None:
    """多帧按上游给的顺序吐出，不重排不合并"""
    raw = 'data: {"i": 1}\n\ndata: {"i": 2}\n\ndata: {"i": 3}\n\n'
    assert _collect(raw) == [{"i": 1}, {"i": 2}, {"i": 3}]


def test_broken_json_raises() -> None:
    """坏 JSON 不在这里兜 —— 它冒到路由层，被编码成流内 STREAM_FAILED

    【注意】：这条钉住「适配器不吞异常」这个设计，改动它会让
    「坏帧 → 中止 → STREAM_FAILED」整条链路失去意义
    """
    with pytest.raises(json.JSONDecodeError):
        _collect("data: {这不是 JSON}\n\n")
