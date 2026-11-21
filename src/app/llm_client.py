"""
上游 LLM 适配器：全项目【唯一】直接接触 httpx 的地方，也是【唯一】翻译上游故障的地方

为什么要有这一层（而不是让每个路由自己 catch）：
    上游可能挂、可能超时、可能返回 200 但结构变了 —— 这些是每个调用点都会遇到的同一件事。
    如果每个路由各写一遍 try/except，就会出现三种问题：
      ① 漏写：新加的路由忘了翻译某类错误，静默落 500
      ② 抄错：像 UPSTREAM_MALFORMEAD 这种拼写错，抄的人发现不了
      ③ 写歪：有人用 if resp.status_code >= 400，有人用 raise_for_status()，
              对 3xx 的处理不一致（前者放过，后者抛）
    收进这一层后，路由只需要调用 list_models() / open_chat_stream()，
    永远拿不到 httpx 的对象，也就永远不会漏翻译。

它能保证的契约（调用方可以完全信任）：
    成功 -> 返回正常值
    失败 -> 抛 AppError（code 一定是 UPSTREAM_* 之一，由 errors.py 映射成 502）
    绝不会把 httpx 的异常泄漏给路由层

【注意】：唯一的例外是流【已经开始之后】才出的错：那时我们的响应头早已发出，
   AppError 会由路由层接住、编码成 event: error 帧。

为什么 create_llm_client 返回这个类而不是 httpx.AsyncClient：
    仍要回答"怎么造"，但现在造出来的东西自带"怎么翻译错误"。
    关闭责任不变：CLI 与 lifespan 都用 async with 自己管。
"""

import asyncio
import json
import logging

# AsyncIterator：异步生成器的返回类型
from collections.abc import AsyncIterator

# dataclass：给「一次补全的结果」定义一个不可变的小容器（见 LlmCompletion）
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.errors import AppError
from app.schemas import ModelItem

logger = logging.getLogger(__name__)

# 上游错误正文最多记这么多字符，防止上游返回一整页 HTML 把日志刷爆
MAX_ERROR_BODY_CHARS = 500

# 【上下文超长】在上游 400 里的两种常见表达：
#   OpenAI 兼容实现通常在 error.code 里给 context_length_exceeded，有的只写在 message 里
# 【注意】：这只是尽量认出；认不出来就退回 UPSTREAM_REJECTED（502），不会比现在更糟
_CONTEXT_TOO_LONG_MARKERS = ("context_length_exceeded", "maximum context length")


def _looks_like_context_too_long(detail: str) -> bool:
    """上游 400 里是不是「上下文超长」—— 认不出来一律当 False（退回 502，不会更糟）"""
    low = detail.lower()
    return any(marker in low for marker in _CONTEXT_TOO_LONG_MARKERS)


def _code_for_status(http_status: int, detail: str) -> str:
    """
    把上游的 4xx/5xx 翻成【客户端能据此行动】的业务码

    判据：客户端能不能靠自己修好？
        能（等一等 / 缩短）-> 业务码直接对应 4xx，客户端知道该干什么
        不能（我们的密钥 / 我们发的 body）-> 502，客户端改请求也没用
    """
    if http_status == 429:
        return "UPSTREAM_RATE_LIMITED"
    if http_status == 413:
        return "UPSTREAM_PAYLOAD_TOO_LARGE"
    if http_status in (401, 403):
        return "UPSTREAM_AUTH_FAILED"
    if 400 <= http_status < 500:
        if _looks_like_context_too_long(detail):
            return "UPSTREAM_PAYLOAD_TOO_LARGE"
        return "UPSTREAM_REJECTED"
    return "UPSTREAM_BAD_STATUS"


def _message_for_status(code: str, http_status: int) -> str:
    """回给客户端的一句话：说清【能做什么】，绝不回显上游原文（可能含内部信息）"""
    if code == "UPSTREAM_RATE_LIMITED":
        return "上游限流，请稍后重试"
    if code == "UPSTREAM_PAYLOAD_TOO_LARGE":
        return "请求内容过长，请缩短后重试"
    if code == "UPSTREAM_AUTH_FAILED":
        return "上游鉴权失败，请联系服务提供方"
    if code == "UPSTREAM_REJECTED":
        return f"上游拒绝了本次请求（HTTP {http_status}）"
    return f"上游返回状态码 {http_status}"


class LlmChatStream:
    """
    一条已经建好、状态码已校验通过的上游流式响应

    为什么需要这个类（而不是把 httpx.Response 直接返给路由）：
        httpx.Response 上有 aiter_lines / aclose / aread 一大堆东西，
        路由拿到它就会开始自己写协议细节 —— 那正是我们要消灭的泄漏。
        这里只暴露两个方法，路由不可能用错。

    生命周期：由调用方负责 aclose()，且【一定要放在 finally 里】
        读完再关 -> 连接归还池可复用（省掉下次 19~45ms 握手 + 43~70ms TLS）
        没读完就关 -> httpx 直接销毁这条连接
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
        """逐帧给出【已解析成 dict】的上游 chunk，自动跳过非数据行与 [DONE]"""
        seen_done = False
        # aiter_lines(): 按换行切行且去掉行尾 \n，一行到就交一行
        #   【注意】：它把 SSE 的空行也作为 '' 返回，所以下面要过滤
        async for line in self._response.aiter_lines():
            # 【注意】：SSE 规范允许 `data:{...}`（冒号后没有空格），空格是可选的
            if not line.startswith("data:"):
                continue
            # 剥掉 "data:" 前缀；再 lstrip() 让 raw 只留真正的数据部分
            #   json.loads 本身容忍前导空格，所以 lstrip 不是功能必需，
            #   但它让 raw 的语义干净（将来打日志不会带上一串空格）
            raw = line[len("data:") :].lstrip()
            if not raw:
                continue
            # [DONE] 是【传输层】的收尾标记，不属于业务数据，适配器负责消化掉
            # .strip() 是字符串方法，去掉字符串两端的空白字符（空格、换行、制表符等）
            if raw.strip() == "[DONE]":
                seen_done = True
                # 不能 break! 中途 break 会让 body 没读完，httpx 会销毁连接
                # continue 让循环自然读到 EOF，连接才能回收复用
                continue
            if seen_done:
                continue
            # json.loads 返回 Any —— 它可能是 dict，也可能是 null / 数组 / 数字 / 字符串
            #   （实测 json.loads("null") -> None，json.loads("[]") -> []）
            # 而本方法的契约是「只吐 dict」，所以校验必须做在【这里】：
            #   如果放到调用方，调用方就得怀疑每一次返回，而类型标注又让我方没法怀疑
            #   （mypy 会报 Statement is unreachable —— 这正是 2026-10-22 踩到的）
            parsed: Any = json.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning("上游 chunk 不是 JSON 对象，已丢弃: type=%s", type(parsed).__name__)
                continue
            yield parsed

    async def aclose(self) -> None:
        """关掉这条流（放 finally 里）"""
        await self._response.aclose()


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    """一次【非流式】补全的结果：正文 + 原始 usage

    【注意】：usage 保证是 dict（上游给 null / 字符串时归一成 {}），
        但【不保证】字段齐全 —— 缺字段由路由层 `_as_int` 记 0
    【注意】：usage 是【只读约定】—— 要加工先 `dict(usage)` 复制。
        故意不换 MappingProxyType：frozen 只管事后替换，管不到「字段被声明成
        什么类型」，换了会让下游 `isinstance(x, dict)` 静默失配（决策 54）
    """

    content: str
    usage: dict[str, Any]


class LlmClient:
    """上游 LLM 服务的适配器。业务代码只认它，不认 httpx"""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def __aenter__(self) -> "LlmClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._http.aclose()

    async def list_models(self) -> list[ModelItem]:
        """
        查上游可用的模型列表

        上游返回 10 个键，我们只用 3 个 —— model_validate 把原始 dict 转成
        ModelItem: 多余的键被忽略（白名单），缺 id 会立刻报错
        """
        # 【注意】：request_timeout 只管【读取间隔】，管不到总时长（上游滴答式慢响应会一直挂着）
        #   所以这里给整次调用一个总预算；超时翻译成本项目自己的错误码（封层：路由里看不到 httpx）
        try:
            async with asyncio.timeout(settings.upstream_total_timeout):
                response = await self._request("GET", "/models")
        except TimeoutError as exc:
            raise AppError(code="UPSTREAM_TIMEOUT", message="上游响应超时") from exc

        # L3：状态码 2xx，但 body 不一定是我们以为的结构
        #   ValueError -> body 不是 JSON（网关 HTML 错误页 / 空 body）
        #                【注意】：pydantic 的 ValidationError 也继承自 ValueError（实测 MRO），
        #                   所以"元素缺 id / id 不是字符串 / 元素不是对象"也落在这
        #   KeyError   -> 字段改名了（data 变 models），或 200 里塞了 {"error": ...}
        #   TypeError  -> 类型变了（{"data": null}，null 不可迭代）
        try:
            payload: dict[str, list[dict[str, object]]] = response.json()
            return [ModelItem.model_validate(item) for item in payload["data"]]
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("上游 /models 返回结构不合规: %s", exc)
            raise AppError(code="UPSTREAM_MALFORMED", message="上游返回结构不合规") from exc

    async def open_chat_stream(self, body: dict[str, object]) -> LlmChatStream:
        """
        发流式请求：只等【响应头】就返回（body 一行都还没读）

        这一步就是 pre-flight: 状态码不对会在这里抛 AppError，
        此时我们的响应头还没发出去，所以还来得及回 502
        """
        response = await self._request("POST", "/chat/completions", json_body=body, stream=True)
        return LlmChatStream(response)

    async def complete(self, body: dict[str, object]) -> LlmCompletion:
        """非流式补全：一次拿全正文与用量

        L1 / L2 由 `_request` 统一翻译（与 open_chat_stream 同一条路）；
        这里只负责 L3 —— 状态码 2xx，但 body 结构不对
        """
        # 【注意】：与 list_models 一样给整次调用一个【总预算】——
        #   request_timeout 只管"两次读取之间的间隔"，管不到总时长（滴答式慢响应会一直挂着）
        try:
            async with asyncio.timeout(settings.upstream_total_timeout):
                response = await self._request("POST", "/chat/completions", json_body=body)
        except TimeoutError as exc:
            raise AppError(code="UPSTREAM_TIMEOUT", message="上游响应超时") from exc

        # L3：四类"结构不对"都落这里
        #   ValueError -> body 不是 JSON（网关 HTML / 空 body）；ValidationError 也在此列
        #   KeyError   -> 字段改名（choices 变 data）或 200 里塞了 {"error": ...}
        #   IndexError -> choices 是【空数组】（上游说成功，但一个候选都没有）
        #   TypeError  -> 类型变了（choices 是 null / message.content 不是字符串）
        try:
            payload = response.json()
            choice = payload["choices"][0]
            content = choice["message"]["content"]
            # 【注意】：必须显式判 —— json 的 null 会变成 None，
            #   直接用会让 ChatResponse 的校验炸在很远的地方（栈里看不出是上游的问题）
            if not isinstance(content, str):
                raise TypeError(f"content 不是字符串：{type(content).__name__}")
            raw_usage = payload.get("usage")
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            logger.error("上游 /chat/completions 返回结构不合规: %s", exc)
            raise AppError(code="UPSTREAM_MALFORMED", message="上游返回结构不合规") from exc

        # usage 归一：null / 字符串 / 缺失 一律变 {}（字段级缺失交给路由记 0）
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        return LlmCompletion(content=content, usage=usage)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
        # 【默认必须 False】: 走 send(stream=True) 时 body 一个字都没读
        #   后面 response.json() 会抛 ResponseNotRead（它既不是 RequestError
        #   也不在 L3 那三类里），直接落 500 兜底
        # 只有 open_chat_stream 需要 True，且它每次都显式传
        stream: bool = False,
    ) -> httpx.Response:
        """发请求并翻译 L1 / L2。成功则返回状态码 2xx 的 Response"""
        # L1：上游根本没回应（DNS / TCP / TLS 失败 / 超时）
        #   RequestError 是 httpx 里"网络层失败"的基类，
        #   ConnectError / ReadTimeout / RemoteProtocolError / PoolTimeout 都是它的子类
        try:
            if stream:
                # build_request 只组装不发送，send(stream=True) 拿到响应头就停
                request = self._http.build_request(method, path, json=json_body)
                response = await self._http.send(request, stream=True)
            else:
                response = await self._http.request(method, path, json=json_body)
        except httpx.RequestError as exc:
            logger.error("上游不可达 %s %s: %s", method, path, exc)
            raise AppError(code="UPSTREAM_UNREACHABLE", message="无法连接上游模型服务") from exc

        # ===== L2：上游有回应，但不是 2xx =====
        # 用 is_success（200~299）而不是 >= 400：
        #   实测 raise_for_status 对 1xx/3xx 也抛，而 302 说明接口地址搬家了，
        #   这是"状态码不对"，不是"结构不对"，两者混起来会误导排查
        if not response.is_success:
            # 先读 Retry-After（头在拿到响应时就有了：_read_error_body 之后响应会被关掉）
            retry_after = response.headers.get("retry-after")
            detail = await self._read_error_body(response)
            logger.error("上游返回 %s %s: %s", response.status_code, path, detail)
            code = _code_for_status(response.status_code, detail)
            raise AppError(
                code=code,
                message=_message_for_status(code, response.status_code),
                headers=(
                    {"Retry-After": retry_after}
                    if code == "UPSTREAM_RATE_LIMITED" and retry_after
                    else None
                ),
            )
        return response

    async def _read_error_body(self, response: httpx.Response) -> str:
        """
        读出上游在失败响应里写的错误正文，并关掉这个响应

        为什么不能直接 response.text（2026-10-21 真网络实测）：
            非流式（await client.request）：body 已读进内存 -> .text 可用
            流式（send(stream=True)）：body 还没读 -> .text 抛 httpx.ResponseNotRead
        所以先试 .text，失败再 await aread()。两条路都实测过。

        为什么要 aclose()：失败响应不会有人再读了，不关就白占一条池内连接
            （在非流式响应上 aclose() 实测安全，不抛异常）
        """
        try:
            text = response.text
        except httpx.ResponseNotRead:
            # 先异步读响应字节，再手动 decode 转字符串，以控制编码规则和坏字节处理
            text = (await response.aread()).decode("utf-8", errors="replace")
        await response.aclose()
        return text[:MAX_ERROR_BODY_CHARS]


def create_llm_client() -> LlmClient:
    """
    按配置造一个上游 LLM 适配器

    【关闭由调用方负责】：这也是为什么这里用 return 而不是 yield
    """
    return LlmClient(
        httpx.AsyncClient(
            base_url=settings.llm_base_url,
            # 【注意】：read/write/pool 用 request_timeout，只有建连单独收紧（#18）
            timeout=httpx.Timeout(settings.request_timeout, connect=settings.llm_connect_timeout),
            # 【注意】：key 为空时不要拼出 "Bearer None" —— 上游回 401 会被误读成「密钥错」（#18）
            #   正常路径上 pre-flight 已经拦住了，这里是第二道
            headers=(
                {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
            ),
        )
    )
