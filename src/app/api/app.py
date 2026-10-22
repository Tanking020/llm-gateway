"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

import json

# logging：标准库日志模块，用来记"每个请求做了什么、花了多久"
import logging
import time
import uuid

# AsyncIterator 是异步迭代器，lifespan 的返回注解要用
# Awaitable 类型表示可以被 await 的东西，Callable 类型代表可以被调用的东西
from collections.abc import AsyncIterator, Awaitable, Callable

# 把"异步生成器函数"变成 lifespan（可用的上下文管理器）
from contextlib import asynccontextmanager

# Annotated：用于给函数签名中参数的 "类型位" 扩容
from typing import Annotated

# Query: 用于在上面勾选"这个查询参数要被怎么对待"，FastAPI 读它去约束和写文档
# status：是一个装了一堆 HTTP 状态码的模块
# HTTPException：是一个普通异常类，负责把异常抛给框架，再由框架翻译成 HTTP 响应
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.api.deps import LlmClientDep, SettingsDep
from app.constants import HEADER_REQUEST_ID
from app.errors import AppError, register_exception_handlers
from app.llm_client import create_llm_client
from app.schemas import ChatRequest, ChatResponse, ModelListResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用启动时建一个共享的【上游适配器】，关闭时关掉它（整个进程各一次，不是每请求）

    为什么用 async with 包住 yield：
        退出 async with 时会自动 await client.aclose()（LlmClient 的 __aexit__）
        写成 yield 之后的普通语句，异常时那行会被跳过 → 连接池泄漏
    """
    # 启动段：整个进程只跑一次
    async with create_llm_client() as client:
        # 点号！把 client 挂到 app.state 的 llm_client 属性上（逗号是解包赋值，会炸）
        app.state.llm_client = client
        yield  # 服务运行期间停在这里；关闭时从这行继续
    # 关闭段：退出 async with 自动 aclose()


# 日志配置：默认 root 级别是 WARNING 且没有 handler, info 会被静默丢弃
#   format 四段：时间 | 级别（左对齐 7 位）| 模块名 | 消息
# ⚠️ basicConfig 只在 root 还没有 handler 时生效；Step 11 会换成 dictConfig(force=True) 做正式配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")

logger = logging.getLogger(__name__)


# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-app-engineering",
    description="LLM 应用后端（学习项目，阶段 1）",
    version="0.1.0",
    lifespan=lifespan,
)


# 允许跨域的前端来源（浏览器里的"源" = 协议 + 域名 + 端口，三者全同才算同源）
# ⚠️ 必须写完整 origin，末尾不带斜杠；"http://localhost:5173/" 与 "http://localhost:5173" 不算同一个
# ⚠️ 这里故意【不写 "*"】：配 allow_credentials=True 时写 "*" 等于对任何网站开放凭证访问
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


# CORS 中间件：给响应补 Access-Control-Allow-* 头，并直接答复浏览器的预检 OPTIONS
# 它注册在【路由之前】，所以预检请求即使打的是不存在的路径也会直接被它答掉
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 只有这些来源的响应才带 CORS 头
    allow_credentials=True,  # 允许浏览器带 Cookie / Authorization
    allow_methods=["GET", "POST"],  # 只放行实际用到的方法（不要写 "*"）
    # 请求头全部放行（含 Content-Type / Authorization），若后续进生产环境要考虑收紧
    # 注意：允许所有请求头 ≠ 后端会处理所有请求头，只是不拦截而已
    allow_headers=["*"],
)


register_exception_handlers(app)


# 中间件：包在【所有路由】外面的一层管道，每个请求都会经过
#   请求方向：中间件前半段 -> 路由
#   响应方向：路由 -> 中间件后半段
# 注册顺序 = 后注册的在最外层（多个中间件时才有区别，目前是第一个中间件）
#
# 这里装饰器厂挂的 "http" 不是路径，是【中间件类型】
# 意思是"这个中间件处理 HTTP 请求"
@app.middleware("http")
async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """给每个请求分配 request_id：优先沿用上游传来的，没有就新生成，并且记录耗时"""
    request_id = request.headers.get(HEADER_REQUEST_ID) or uuid.uuid4().hex[:12]
    # 存进 request.state —— 这一次请求的"口袋"，异常处理器里也能读到
    request.state.request_id = request_id
    # 先声明为 None: 里层抛异常时 response 永远不会被赋值，
    #   不先给值的话，finally 里访问它会抛 UnboundLocalError，把真正的异常盖掉
    response: Response | None = None
    start = time.perf_counter()
    try:
        # 把请求交给里面内层继续处理；等状态码和响应头就绪后，把响应对象取回来
        response = await call_next(request)
    # 这里用 finally 确保成功和失败两条路径都写日志，而不是失败才写
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        # 访问日志属于 INFO（正常发生的事）：请求失败也是这一行，失败详情由异常处理器的 ERROR 记
        logger.info(
            "%s %s -> %s %.1fms request_id=%s",
            request.method,
            request.url.path,
            # getattr 是 Python 内置函数，作用是根据名字获取对象的属性
            # 异常路径上没有 response 时，用 ERR 占位
            getattr(response, "status_code", "ERR"),
            duration_ms,
            request_id,
        )

    # 走到这里说明没有异常（异常路径根本到不了这行）:断言同时帮 mypy 收窄类型
    assert response is not None

    # 回写响应头：客户端/前端报错时可以把它贴给我方，我方据此搜日志
    response.headers[HEADER_REQUEST_ID] = request_id
    return response


# @ 开头的是 Python 【装饰器】（Decorator）语法
# 装饰器本质上是一个函数，它接收一个函数作为参数，并返回一个新的函数或者原函数
# 用来在不修改原函数代码的情况下，给函数增强或者注册功能
#
# 具体地，@app.get("/health") 把下面的函数【注册】为一条路由
# 本处含义：把下面的函数【注册】成"当有人用 GET 请求 /health 时就调用它"
# 装饰器在这里起的作用：往路由表里登记一行
@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查：最轻的接口，用来确认【服务活着】"""
    # 部署后 Docker / 负载均衡 会定期打这个接口来判断实例是否可用
    return {"status": "ok"}


# ===== 1.3 三段参数：路径 / 查询 / 请求体 =====

# 演示用的模型清单（真实项目里会从 config 或上游 API 拿）
KNOWN_MODELS = ["deepseek-flash", "deepseek-v4-pro"]


@app.get("/v1/models")
async def list_models(
    prefix: Annotated[str | None, Query(description="只返回名字以此开头的模型")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="最多返回几条")] = 20,
) -> dict[str, object]:
    """列出模型。prefix / limit 是【查询参数】—— 来自 ?prefix=...&limit=..."""
    # 前缀过滤设计：prefix = 前缀，m.startswith(prefix) 查询 "m 是否以 prefix 开头"
    # prefix 可选（不传 = 不过滤）
    matched = [m for m in KNOWN_MODELS if prefix is None or m.startswith(prefix)]
    return {"total": len(matched), "items": matched[:limit]}


@app.get("/v1/models/latest")
async def latest_model() -> dict[str, str]:
    """固定路径。⚠️ 必须写在下面 /v1/models/{model_name} 的【前面】"""
    return {"model_name": KNOWN_MODELS[0]}


@app.get("/v1/models/{model_name}")
async def get_model(model_name: str) -> dict[str, str]:
    """model_name 是【路径参数】—— 来自 URL 路径那一小段"""
    # 更新：未知模型返回 404
    # raise 会立即中止函数，后面的 return 不执行；异常由框架统一转成响应
    if model_name not in KNOWN_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型不存在: {model_name}",
        )
    return {"model_name": model_name}


def ensure_last_message_is_user(request: ChatRequest) -> None:
    """
    语义检查：形状合法 ≠ 能回答。最后一条不是 user，就没有【要回答的问题】

    规则分工：形状归 pydantic（schemas.py），语义归业务代码（本函数）

    ⚠️ 为什么抽成函数，而不是在每条路由里各写一遍：
        /v1/chat 与 /v1/chat/stream 共用同一个 ChatRequest 契约，
        同一条业务规则就必须只有一份实现 —— 否则新加路由时一定会漏
        （本项目已经漏过一次：/v1/chat/stream 曾放过 assistant 收尾的请求，
          还真的把那段话发给上游、拿回一整段回答，且白花一次 token）

    ⚠️ 这条规则【对当前这个问答接口正确】，但不是绝对正确：
        有些场景允许以 assistant 收尾（例如"续写/补全上一句"），后续需要时可以放开
    """
    last = request.messages[-1]
    if last.role != "user":
        raise AppError(
            code="LAST_MESSAGE_NOT_USER",
            message=f"最后一条消息必须是 user，当前是 {last.role}",
        )


@app.post("/v1/chat")
async def chat(request: ChatRequest, config: SettingsDep) -> ChatResponse:
    """
    request 是【请求体】—— 类型是 pydantic 模型，所以 FastAPI 从 JSON body 里面取；
    config 是【依赖】—— FastAPI 调 get_settings() 后注入
    """
    ensure_last_message_is_user(request)
    last = request.messages[-1]
    return ChatResponse(content=f"[echo] {last.content}", model=request.model or config.llm_model)


# FastAPI 构建路由时会检查：有显式 response_model 就用它，没有就用【返回注解】
# 两者相同时只需写返回注解 —— 这里故意不写 response_model=，避免同一件事写两遍
@app.get("/v1/upstream/models")
async def upstream_models(client: LlmClientDep) -> ModelListResponse:
    """
    真实调用上游 /models。与 /v1/models（硬编码）对照用。

    client 是【依赖】：从 app.state 取出由 lifespan 创建的【应用级共享】上游适配器，
    请求结束不会被关闭（连接池要复用），进程关闭时由 lifespan 统一释放

    更新：这里只有两行：调用 + 组响应。
        上游三类失败全部由 LlmClient.list_models 翻译成 AppError，
        再由 errors.py 的处理器映射成 502。
        路由层【不 import httpx、不写 try/except】—— 这是本项目对上游调用的统一姿势。
    """
    models = await client.list_models()

    # total 由【我们】算：过滤后的条数，不是上游返回的条数
    #   现在还没加过滤，所以暂时等于 len(上游列表)；加了 prefix 过滤后两者就不相等了
    return ModelListResponse(total=len(models), items=models)


# 【时序验证】流式必须起真服务；但 curl -w 的 ttfb 量的是"响应头"不是"首帧"
#   （2026-10-20 实测订正）要证明"内容在流"，必须用带时间戳的客户端量首个数据帧
@app.post("/v1/chat/stream")
async def chat_stream(
    # 客户端请求体：与 /v1/chat 复用同一份契约
    # （messages / model / temperature / max_tokens 四个字段都已在那里校验过）
    request: ChatRequest,
    client: LlmClientDep,
    config: SettingsDep,
) -> StreamingResponse:
    """真模型流式：逐帧解析上游，转发回答文字 + 结束原因 + token 用量（思维链按产品要求丢弃）"""

    # 与 /v1/chat 完全同一条业务规则，所以调同一个函数
    # ⚠️ 必须放在 pre-flight 之前：否则会白花一次上游调用（真金白银）
    ensure_last_message_is_user(request)

    # 上游请求体的字段名由 OpenAI 兼容协议规定
    body: dict[str, object] = {
        "model": request.model or config.llm_model,
        # Message 是 pydantic 模型，必须先 model_dump() 转成纯 dict 才能序列化
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
        # 这个开关是"逐块发"的开关：不开就是等全部生成完一次性返回
        "stream": True,
    }
    # max_tokens 为 None 时【不放进请求体】（而不是放一个 null）
    #   实测 DeepSeek 接受显式 null（返回 200），但省略更保险：
    #   有些 OpenAI 兼容实现会拒绝 null；而且"这个键不存在"在语义上就是"不限制"
    if request.max_tokens is not None:
        body["max_tokens"] = request.max_tokens

    # ===== pre-flight：先确认上游通不通、状态码对不对，再决定我们回什么 =====
    # 为什么【必须在 return StreamingResponse 之前】：
    #   StreamingResponse 一旦被框架返回，200 响应头 + transfer-encoding: chunked 就发出去了，
    #   之后再出错也改不了状态码（9b-2 实测：日志先写 200，157ms 后才报 422）
    # 这一行会抛 AppError（L1 连不上 / L2 状态码不对），由 errors.py 的处理器回 502
    #   实测上游响应头到达耗时 181~266ms
    upstream = await client.open_chat_stream(body)

    # 内层异步生成器：真正"一段一段往外吐"的地方
    # 推进它的是 StreamingResponse 里的 async for（starlette/responses.py:253），不是本文件
    async def event_source() -> AsyncIterator[str]:
        """异步生成器：每 yield 一次 = 一帧 SSE，框架收一帧发一帧"""
        # 先发一帧状态，前端可以立刻显示"模型思考中"
        #   注意：加了 pre-flight 之后，这一帧要等上游响应头回来才发得出去
        #   实测 TTFB 从 60.0ms 变成约 181~266ms，仍远小于首个内容帧的 845.8ms
        yield f"data: {json.dumps({'status': 'thinking'}, ensure_ascii=False)}\n\n"

        #   raw_chunks=0 -> 上游根本没按 SSE 回（HTML / 空 body）
        #   raw_chunks>0 而 content_frames=0 -> 回了帧但没有内容帧（忽略 stream=True / 只有思维链）
        raw_chunks = 0  # 收到的原始 SSE 帧数量
        content_frames = 0  # 其中包含回答文字的帧数量

        try:
            # aiter_chunks 已经帮我们做完了：切行、跳空行、剥 data: 前缀、
            # 消化 [DONE]、json.loads —— 这里拿到的就是干净的 dict
            async for chunk in upstream.aiter_chunks():
                raw_chunks += 1

                # 这里不用再检查 chunk 的类型：aiter_chunks 的契约就是「只吐 dict」，
                # 非 dict 的已在适配器里被丢弃并记了 warning（协议细节归适配器，业务归这里）

                # usage（本次请求消耗资源量的统计信息）可能出现在两种位置，先单独处理：
                #   a) 和结束原因挤在同一帧
                #   b) 单独一帧且 choices 为空列表
                # 所以不能假设"每帧都有 choices"，先取值再判断
                usage = chunk.get("usage")
                choices = chunk.get("choices") or []  # .get() 的默认值只能处理键不存在的情况
                if not isinstance(choices, list):
                    logger.warning("上游 choices 不是列表，已丢弃: type=%s", type(choices).__name__)
                    continue
                if not choices:
                    # 这种帧只可能是"纯用量帧"（OpenAI 开 stream_options.include_usage 时会出现）
                    # 它没有内容也没有结束原因，所以处理完就可以跳过
                    if usage:
                        details = usage.get("completion_tokens_details") or {}
                        logger.info(
                            "流式用量(纯用量帧): prompt=%s completion=%s total=%s reasoning=%s "
                            "cache_hit=%s cache_miss=%s",
                            usage.get("prompt_tokens"),
                            usage.get("completion_tokens"),
                            usage.get("total_tokens"),
                            details.get("reasoning_tokens"),
                            usage.get("prompt_cache_hit_tokens"),
                            usage.get("prompt_cache_miss_tokens"),
                        )
                        yield f"data: {json.dumps({'usage': usage}, ensure_ascii=False)}\n\n"
                    continue

                # 回答文字藏在 choices[0].delta.content
                # 逐层拆：列表取第 0 个 → 那个 dict → 再取 delta 键，得到"本帧新增"的字段
                choice = choices[0]
                # 注意：choices[0] 是"本帧数组第一个元素"，不等于"index 为 0 的候选"
                # 当前两者相同，只处理 index=0 这一个候选：我们不传 n，DeepSeek 也只支持 n=1
                # 但是万一将来上游返回多个候选（每帧只含一个、index 交替），
                # 不加这行会把两路文字搅成乱码（如 "答另案一A段"），而不是"只丢一路"
                if not isinstance(choice, dict):
                    logger.warning(
                        "上游 choices[0] 不是对象，已丢弃: type=%s", type(choice).__name__
                    )
                    continue
                if choice.get("index", 0) != 0:  # index = 0 防御性编程
                    continue
                # DeepSeek 每帧都有 delta，但换上游可能变，这里同样是防御性编程
                delta = choice.get("delta") or {}

                # 结束原因：只在最后一帧有值（"stop" = 模型自己说完 / "length" = 被截断）
                #   必须放在下面 content 的判断【之前】，否则会被 continue 跳过
                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    logger.info("流式结束: reason=%s", finish_reason)
                    payload = json.dumps({"finish_reason": finish_reason}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

                # 用量：实测 DeepSeek 把它和 finish_reason 挤在最后一帧；
                #   OpenAI 则是单独一帧（choices 为空，已在上面处理）。
                #   两种位置都要覆盖，所以这里再判断一次，且必须在 content 判断之前
                if usage:
                    # 写进服务端日志 = 记账：转发给前端 = 让用户看到花了多少
                    details = usage.get("completion_tokens_details") or {}
                    logger.info(
                        "流式用量: prompt=%s completion=%s total=%s reasoning=%s "
                        "cache_hit=%s cache_miss=%s",
                        usage.get("prompt_tokens"),
                        usage.get("completion_tokens"),
                        usage.get("total_tokens"),
                        details.get("reasoning_tokens"),
                        usage.get("prompt_cache_hit_tokens"),
                        usage.get("prompt_cache_miss_tokens"),
                    )
                    yield f"data: {json.dumps({'usage': usage}, ensure_ascii=False)}\n\n"

                # 内容帧：content 可能是 None / "" / 字符串三种取值，必须是【字符串】才允许转发
                text = delta.get("content")
                if not isinstance(text, str):
                    # None 是最常见的（首帧 role / 结束帧 / 思维链帧），静默跳过
                    # 但"非 None 且非字符串"说明上游改了结构（多模态风格）
                    # if not text 会放它过去（非空 list 是真值），把数组塞给前端
                    if text is not None:
                        logger.warning(
                            "上游 delta.content 不是字符串，已丢弃：type=%s value=%s",
                            type(text).__name__,
                            text,
                        )
                    continue
                if not text:
                    continue

                content_frames += 1

                # 重组成【我们自己】的帧格式再交出去（白名单：上游 7 个顶层键只留 1 个信息）
                yield f"data: {json.dumps({'delta': text}, ensure_ascii=False)}\n\n"

            # ===== 零内容保护 =====
            # 上游回了 200，但我们一帧内容都没转发出去
            # 三种真实场景：200 + HTML / 200 + 空 body / 上游忽略 stream:true
            # 状态码是 200 -> pre-flight 拦不住；头已发出 -> 改不了状态码
            # 唯一做法：在流里明确说"这次没拿到内容"，别让前端以为"回答就是空的"
            if content_frames == 0:
                logger.error(
                    "流式零内容：上游 chunk=%s 内容帧=0 —— "
                    "可能是 HTML / 空 body / 上游忽略 stream=True",
                    raw_chunks,
                )
                yield (
                    "data: "
                    + json.dumps(
                        {"error": {"code": "STREAM_NO_CONTENT", "message": "上游未返回任何内容"}},
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

            # 【正常路径的收尾】：
            # 注意 finally 里面只能放清理，不能放【生成值的操作】（例如 yield）
            #   这是因为【客户端断开】时 FastAPI 会转发 aclose()给生成器并抛 GeneratorExit
            #   生成器收到后，只会走进 finally:
            #   （因为 GeneratorExit 是特殊异常，没进 try / exception）
            #   如果 finally 里 yield → 生成器试图“复活” → Python 拒绝（生成器会抛 RuntimeError）
            yield "data: [DONE]\n\n"

        except Exception as exc:
            # 【异常路径：把错误编码进流，再收尾】
            # 这里不用显式放过 CancelledError / GeneratorExit 是因为这俩是特殊异常
            # 他俩直接继承自 BaseException，不是 Exception（普通异常）的子类
            # 所以「客户端断开」和「生成器被关闭」根本不会进这个分支，
            # 会原样往外抛，由 finally 和上层处理
            # logger.exception 会带完整 traceback；而回给前端的只有一句人话
            # （绝不回显 str(exc) 或堆栈 —— 那可能泄露内部结构）
            logger.exception("流式过程中失败：%s", type(exc).__name__)
            yield (
                "data: "
                + json.dumps(
                    {"error": {"code": "STREAM_FAILED", "message": "生成过程中中断"}},
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        finally:
            # ⚠️ finally 只做清理，绝不 yield
            # 【必须手动关】： open_chat_stream 没有 async with 帮我们关
            # 三条路都会走到这里：正常读完 / 流内异常 / 客户端断开（CancelledError）
            # 读完再关 = 连接归还池可复用；没读完就关 = 连接直接被销毁
            await upstream.aclose()

    # 返回流式响应：这里只负责上网，不负责产出
    return StreamingResponse(
        event_source(),
        # 必须是 text/event-stream，浏览器 EventSource 和前端库才认
        media_type="text/event-stream",
        headers={
            # 禁止中间层缓存这次响应（否则可能拿到别人的答案）
            "Cache-Control": "no-cache",
            # 给 nginx 看的：别缓冲，否则流式会被攒成一次性（部署时要注意）
            "X-Accel-Buffering": "no",
        },
    )
