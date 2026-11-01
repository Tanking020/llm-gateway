"""假的上游 LLM：通过 dependency_overrides 替换 get_llm_client，测试绝不真调网络"""

from collections.abc import AsyncIterator
from typing import Any

from app.errors import AppError
from app.llm_client import LlmChatStream, LlmClient
from app.schemas import ModelItem


class FakeChatStream(LlmChatStream):
    """冒充 LlmChatStream：只覆盖路由真正会调的两个方法"""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks
        self.closed = False

    async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class FakeLlm(LlmClient):
    """冒充 LlmClient：只覆盖路由真正会调的两个方法"""

    def __init__(
        self,
        models: list[ModelItem] | None = None,
        chunks: list[dict[str, Any]] | None = None,
        models_error: AppError | None = None,
        stream_error: AppError | None = None,
    ) -> None:
        # 这样写是了避免传入可变默认对象，默认参数只创建一次，所有实例共享
        # 但要注意这样无法区分传了空列表和没传，只不过现有场景这俩没区别所以没事
        self._models = models or []
        self._chunks = chunks or []
        self._models_error = models_error
        self._stream_error = stream_error
        self.last_body: dict[str, object] | None = None

    async def list_models(self) -> list[ModelItem]:
        if self._models_error is not None:
            raise self._models_error
        return self._models

    async def open_chat_stream(self, body: dict[str, object]) -> LlmChatStream:
        self.last_body = body
        if self._stream_error is not None:
            raise self._stream_error
        return FakeChatStream(self._chunks)
