"""假上游：OpenAI 兼容协议的 `/models` 与 `/chat/completions`(SSE)，用来【压测不花钱】

为什么必须有它：压测要打几百上千次请求，打真上游 = 真花钱 + 触发真实限流 + 结果不可重复。
所以把 `LLM_BASE_URL` 指向它，测的就只是【我们自己的容量】。

用法：
    $env:FAKE_PORT = "18099"; uv run python scripts/fake_upstream.py
    $env:LLM_BASE_URL = "http://127.0.0.1:18099"     # 再启动 app
    uv run python scripts/loadtest_chat_stream.py --key sk_xxx --concurrency 1,4,16

【注意】：它只实现压测用到的那两条路径与帧形状，不是协议全集 ——
    要覆盖更多上游行为请改 `tests/fakes.py`（那是一层的假对象）
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

# 【注意】：这两个数决定「单请求服务时长」= frames × delay（默认 12 × 0.02 ≈ 0.24s + 开销）
#   它直接决定闸门的吞吐上限（见 docs/notes 里的排队推导）
FRAME_DELAY = float(os.environ.get("FAKE_FRAME_DELAY", "0.02"))
FRAMES = int(os.environ.get("FAKE_FRAMES", "12"))


@app.get("/models")
async def models() -> JSONResponse:
    """上游模型清单：只在 `/v1/upstream/models` 里用到"""
    return JSONResponse({"object": "list", "data": [{"id": "fake-model", "object": "model"}]})


@app.post("/chat/completions", response_model=None)
async def chat_completions(request: Request) -> StreamingResponse | JSONResponse:
    body = await request.json()
    if not body.get("stream", False):
        return JSONResponse(
            {
                "id": "cmpl-fake",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            }
        )

    async def gen() -> AsyncIterator[str]:
        for i in range(FRAMES):
            frame = {"id": "cmpl-fake", "choices": [{"index": 0, "delta": {"content": f"t{i}"}}]}
            yield f"data: {json.dumps(frame)}\n\n"
            await asyncio.sleep(FRAME_DELAY)
        # 【注意】：最后一帧必须带 finish_reason + usage 同帧 —— 与真上游一致，
        #   否则我们这边会落成「没有 usage」，压测出来的账单数据就不是真的
        final = {
            "id": "cmpl-fake",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": FRAMES, "total_tokens": 5 + FRAMES},
        }
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("FAKE_PORT", "18099")),
        log_level="warning",
    )
