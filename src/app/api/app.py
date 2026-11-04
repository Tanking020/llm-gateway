"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

import asyncio
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

# datetime 只用于 _conversation_stats_stmt 的返回类型注解（元组里那两个时间列）
from datetime import datetime

# Annotated：用于给函数签名中参数的 "类型位" 扩容
from typing import Annotated, Any

# Query: 用于在上面勾选"这个查询参数要被怎么对待"，FastAPI 读它去约束和写文档
# status：是一个装了一堆 HTTP 状态码的模块
from fastapi import FastAPI, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbDep, LlmClientDep, SettingsDep, UpstreamSlotDep
from app.config import Settings, settings
from app.constants import HEADER_REQUEST_ID
from app.database import engine
from app.errors import AppError, register_exception_handlers
from app.llm_client import create_llm_client
from app.logging_setup import configure_logging
from app.models import Base, Conversation, LlmCall, LlmCallStatus
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationIn,
    ConversationPageOut,
    ConversationPatch,
    ConversationStatsOut,
    ModelListResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用启动时建一个共享的【上游适配器】，关闭时关掉它（整个进程各一次，不是每请求）

    为什么用 async with 包住 yield：
        退出 async with 时会自动 await client.aclose()（LlmClient 的 __aexit__）
        写成 yield 之后的普通语句，异常时那行会被跳过 → 连接池泄漏

    【注意】：yield 只能出现一次，而且它【必须在 async with 里面】。
        放在外面不会报错（实测），但清理会发生在【启动阶段】：
        with 先退出 → client 先被关掉 → 然后才交给服务使用，
        于是整个运行期间每个请求拿到的都是一个已关闭的客户端。
        判据：async with 的作用域 = 【它被使用的那段时间】。
    """

    # 启动段[1]：建表。create_all 只建"还不存在的表"，已存在的表不会改结构
    #   run_sync 用 greenlet 在同线程内跑同步风格的 DDL（不是线程池）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 启动段[2]：上游并发闸门（进程级）。放在 state 上，deps 里按请求取
    # 【注意】：必须每次启动都新建 —— 复用一个被上一轮测试耗尽的 Semaphore 会永远挡住请求
    app.state.upstream_semaphore = asyncio.Semaphore(settings.max_concurrent_upstream_calls)

    # 启动段[3]：整个进程共享一个上游适配器
    async with create_llm_client() as client:
        # 把 client 挂到 app.state 的 llm_client 属性上
        app.state.llm_client = client
        yield  # 服务运行期间停在这里；关闭时从这行继续
        # 关闭段[1]：退出 async with 自动 aclose()

    # 关闭段[2]：释放数据库连接池
    await engine.dispose()


# 日志设置：整个进程只用一套格式、一个 handler（配置内容在 app/logging_setup.py）
configure_logging()

logger = logging.getLogger(__name__)


# 交互式文档只在开发环境开放：prod 下它会把全部接口形状公开给任何人
# 【注意】：三个要一起关 —— 只关 docs 时 /openapi.json 仍能拿到完整结构
_DOCS_ENABLED = settings.app_env == "dev"


# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-app-engineering",
    description="LLM 应用后端（学习项目，阶段 1）",
    version="0.1.0",
    # 只有开发才开：debug=True 时异常处理器被绕过，traceback 直接进响应体
    #   （APP_ENV=prod 时 config.py 已禁止 DEBUG=true，这里才敢直接接）
    debug=settings.debug,
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
    lifespan=lifespan,
)


# 允许跨域的前端来源（浏览器里的"源" = 协议 + 域名 + 端口，三者全同才算同源）
# 【注意】：必须写完整 origin，末尾不带斜杠；
#   "http://localhost:5173/" 与 "http://localhost:5173" 不算同一个
# 【注意】：这里故意【不写 "*"】：配 allow_credentials=True 时写 "*" 等于对任何网站开放凭证访问
# 【注意】：allow_methods 必须与【实际注册的路由】保持一致。2026-10-25 实测事故：
#   加了 PATCH / DELETE 路由但忘了加到这个列表 -> 浏览器预检 OPTIONS 直接 400，
#   前端完全无法调用这两个接口；而 curl 测不出来（CORS 只在浏览器生效）。
#   判据：新增一个非 GET/POST 的路由时，必须回头检查这里。
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


# CORS 中间件：给响应补 Access-Control-Allow-* 头，并直接答复浏览器的预检 OPTIONS
# 它注册在【路由之前】，所以预检请求即使打的是不存在的路径也会直接被它答掉
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 只有这些来源的响应才带 CORS 头
    allow_credentials=True,  # 允许浏览器带 Cookie / Authorization
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # 只放行实际用到的方法（不要写 "*"）
    # 请求头全部放行（含 Content-Type / Authorization），若后续进生产环境要考虑收紧
    # 注意：允许所有请求头 ≠ 后端会处理所有请求头，只是不拦截而已
    allow_headers=["*"],
)


# 【登记翻译器】：异常由 ExceptionMiddleware 查表后调用
# 【注意】：管不到 @app.middleware 里抛的异常 —— 那层在它外面，会变成 500
#   原理：内层中间件无法捕获"外层中间件在调用内层之前抛出的异常"
register_exception_handlers(app)


# 【中间件】：包在【所有路由】外面的一层管道，每个请求都会经过
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


@app.get("/health/ready")
async def health_ready(db: DbDep) -> dict[str, str]:
    """
    就绪检查：和 /health 【不能合并】 ——
    /health       <- liveness  探针 = 进程活着吗？不检查外部依赖
    /health/ready <- readiness 探针 = 能接流量吗？检查数据库这类关键依赖
    K8s 里：
        liveness  探针打 /health，失败就重启 Pod
        readiness 探针打 /health/ready，失败就从负载均衡摘掉，不转发请求
    把探库放进 liveness 的话，数据库抖动时编排系统会不停重启全部实例，
        而重启治不好数据库 —— 雪崩
    """
    # text 用于让我们能直接写原生 SQL 语句，适合 ORM 写不出的复杂语句
    # 另外也用来做健康检查、PRAGMA、EXPLAIN 这类 SQLAlchemy 不需要理解的操作
    # 【注意】：用 text 绝对不能直接拼用户输入，这会导致【数据库注入漏洞】
    #   要用参数绑定方法：db.execute(stmt, {"id": user_input})
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        # 只记类型，不回显 str(exc)（可能带库路径 / 连接串等）
        logger.error("就绪检查失败：%s", type(exc).__name__)
        raise AppError(code="DB_UNAVAILABLE", message="数据库不可用") from exc
    return {"status": "ready"}


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
    """固定路径。【注意】：必须写在下面 /v1/models/{model_name} 的【前面】"""
    return {"model_name": KNOWN_MODELS[0]}


@app.get("/v1/models/{model_name}")
async def get_model(model_name: str) -> dict[str, str]:
    """model_name 是【路径参数】—— 来自 URL 路径那一小段"""
    # 更新：未知模型返回 404
    # raise 会立即中止函数，后面的 return 不执行；异常由框架统一转成响应
    if model_name not in KNOWN_MODELS:
        raise AppError(code="MODEL_NOT_FOUND", message=f"模型不存在：{model_name}")
    return {"model_name": model_name}


def ensure_last_message_is_user(request: ChatRequest) -> None:
    """
    语义检查：形状合法 ≠ 能回答。最后一条不是 user，就没有【要回答的问题】

    规则分工：形状归 pydantic（schemas.py），语义归业务代码（本函数）

    【注意】：为什么抽成函数，而不是在每条路由里各写一遍：
        /v1/chat 与 /v1/chat/stream 共用同一个 ChatRequest 契约，
        同一条业务规则就必须只有一份实现 —— 否则新加路由时一定会漏
        （本项目已经漏过一次：/v1/chat/stream 曾放过 assistant 收尾的请求，
          还真的把那段话发给上游、拿回一整段回答，且白花一次 token）

    【注意】：这条规则【对当前这个问答接口正确】，但不是绝对正确：
        有些场景允许以 assistant 收尾（例如"续写/补全上一句"），后续需要时可以放开
    """
    last = request.messages[-1]
    if last.role != "user":
        raise AppError(
            code="LAST_MESSAGE_NOT_USER",
            message=f"最后一条消息必须是 user，当前是 {last.role}",
        )


def ensure_max_tokens_within_ceiling(request: ChatRequest, config: Settings) -> None:
    """
    成本护栏：客户端要的 max_tokens 不能超过服务端上限

    与 ensure_last_message_is_user 同一个位置、同一个理由（两条路由共用一份实现）。

    【注意】：这里【只拒绝、不改写】。把 8000 悄悄改成 4096 会让回答中途被截断，
        而客户端只会看到 finish_reason=length，根本不知道是被我们改的 —— 静默失效
    """
    if request.max_tokens is not None and request.max_tokens > config.max_tokens_ceiling:
        raise AppError(
            code="INVALID_MAX_TOKENS",
            message=f"max_tokens 超过服务端上限 {config.max_tokens_ceiling}",
        )


def _conversation_not_found(conv_id: int) -> AppError:
    """
    404 的唯一来源：改文案或者状态码只改这里

    【注意】：返回异常对象而不是抛出 —— 由调用方决定在哪里 raise
    """
    return AppError(
        code="CONVERSATION_NOT_FOUND",
        message=f"对话不存在：{conv_id}",
    )


def _conversation_stats_stmt() -> Select[int, str, datetime, datetime, int, int]:
    """
    对话 + 账单统计的查询骨架：列表与详情共用这一份

    【注意】：必须 outerjoin —— 用 join 会让没有任何账单的对话整行消失；
        coalesce 兜住 SUM 对空集返回的 NULL
    """
    return (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            Conversation.updated_at,
            # 在数据库内算好再拿出来，而不是全查出来再到 Python 里循环（规避 1 + N）
            func.count(LlmCall.id).label("call_count"),
            func.coalesce(func.sum(LlmCall.total_tokens), 0).label("total_tokens"),
        )
        .outerjoin(LlmCall, LlmCall.conversation_id == Conversation.id)
        .group_by(Conversation.id)
    )


def _row_to_stats(row: Any) -> ConversationStatsOut:
    """
    把一行查询结果装成响应对象（列表与详情共用）

    【注意】：Row 不是 ORM 对象，select 点名了几列就只装几列 —— 不能靠
        from_attributes 自动转换，只能手写映射；写在一处才能「加字段只改这里」
    """
    return ConversationStatsOut(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        call_count=row.call_count,
        total_tokens=row.total_tokens,
    )


async def _fetch_conversation_stats(db: AsyncSession, conv_id: int) -> ConversationStatsOut:
    """按 id 取【对话 + 账单统计】：不存在就抛 404"""
    stmt = _conversation_stats_stmt().where(Conversation.id == conv_id)
    row = (await db.execute(stmt)).first()
    if row is None:
        raise _conversation_not_found(conv_id)
    return _row_to_stats(row)


async def require_conversation(db: AsyncSession, conv_id: int) -> Conversation:
    """
    按 id 取对话：不存在就抛 404

    【注意】：db.get 找不到时返回 None（不抛异常），所以必须判空 ——
        不判返回 None 会流到 response_model → ResponseValidationError（input=None）→ 500。
        实测【不是】AttributeError

    【注意】：五处路由共用这一份实现（两条 chat + GET/PATCH/DELETE），
        改文案或改状态码只改这里 —— 否则一定会漏
    """
    conv = await db.get(Conversation, conv_id)
    if conv is None:
        raise _conversation_not_found(conv_id)
    return conv


def _as_dict(value: object) -> dict[str, Any]:
    """
    把上游可能给的任意 JSON 值收窄成 dict；不是 dict 就给空 dict

    为什么需要它：上游字段可能是 null / 字符串 / 数组（json.loads 可返回任意 JSON 类型），
        直接 .get() 会抛 AttributeError，而那时响应头早已发出 —— 一个坏帧会打断整条流。
        （实测 "usage": "oops" 会让整条流 STREAM_FAILED，尽管回答内容本来能正常送达）

    为什么不在这里记 warning：usage 在多数帧里就是 null（正常现象），记了会刷屏。
        真正需要人看的"零内容"由 content_frames == 0 那条 error 兜住。
    """
    return value if isinstance(value, dict) else {}


def _as_int(value: object) -> int:
    """把上游的 token 计数收窄成 int：不是 int 就记 0（上游可能给字符串 / None / 浮点）"""
    return value if isinstance(value, int) else 0


@app.post("/v1/chat")
async def chat(request: ChatRequest, config: SettingsDep, db: DbDep) -> ChatResponse:
    """
    request 是【请求体】—— 类型是 pydantic 模型，所以 FastAPI 从 JSON body 里面取；
    config 是【依赖】—— FastAPI 调 get_settings() 后注入
    """
    ensure_last_message_is_user(request)  # 便宜的语义检查在前，与 chat_stream 保持同一顺序
    ensure_max_tokens_within_ceiling(request, config)

    if request.conversation_id is not None:
        await require_conversation(db, request.conversation_id)

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


@app.post("/v1/conversations", response_model=ConversationStatsOut, status_code=201)
async def create_conversation(payload: ConversationIn, db: DbDep) -> ConversationStatsOut:
    """
    新建一个对话，返回带 id 的完整对象（含账单统计）

    为什么必须 flush 而不是只 add：
        id 由数据库生成，不把 INSERT 打下去就不知道是几，没法返回给客户端。
        flush 只发 SQL、不提交 —— 提交由 get_db 在路由返回后统一做。

    【注意】：刚建的对话统计必然是 0 / 0，但形状必须与列表 / 详情 / PATCH 一致 ——
        否则前端把 POST 返回值塞进列表缓存时，那条数据会缺两个字段
    """
    # payload 是 pydantic 对象，不是字符串 —— 必须取 .title
    #   写 Conversation(title=payload) 会 500：数据库绑不了 ConversationIn 这个类型
    conv = Conversation(title=payload.title)
    # add 只登记（一个 SQL 都没发）；flush 才真的发 INSERT，
    # 并把数据库分配的自增 id 填回 conv 对象 —— 所以后面能拿 conv.id 再查一次
    db.add(conv)
    await db.flush()
    # 提交不在这里：get_db 会在路由函数返回之后统一 commit
    #   flush 已在同一事务内发出 INSERT，所以接下来这次查询能看到刚写入的行
    return await _fetch_conversation_stats(db, conv.id)


@app.get("/v1/conversations/{conv_id}", response_model=ConversationStatsOut)
async def get_conversation(conv_id: int, db: DbDep) -> ConversationStatsOut:
    """
    按 id 查一个对话（含账单统计）：不存在返回 404

    与列表返回【同一种形状】—— 同一个资源两种形状，前端点进详情就会丢字段
    """
    return await _fetch_conversation_stats(db, conv_id)


@app.delete("/v1/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conv_id: int, db: DbDep) -> None:
    """
    删除一个对话：不存在返回 404

    【注意】：返回注解必须是 None，且 status_code 必须是 204：
    204 语义是【成功了，但没有任何内容要返回】
    FastAPI 在注册路由时就会检查：若声明了 response 内容会直接
    AssertionError: Status code 204 must not have a response body
    （服务根本起不来，不是运行时才报）
    """
    conv = await require_conversation(db, conv_id)
    await db.delete(conv)  # AsyncSession.delete 是异步方法，必须 await
    # 不写 return: -> None 的函数隐式返回 None


@app.patch("/v1/conversations/{conv_id}", response_model=ConversationStatsOut)
async def update_conversation(
    conv_id: int,
    payload: ConversationPatch,
    db: DbDep,
) -> ConversationStatsOut:
    """
    修改一个对话的标题：不存在返回 404

    PATCH = 部分更新：【只改客户端传了的字段】，没传的保持原样
    PUT = 整体替换：没传的字段会被重置成默认值

    本项目只有 title 一个可改字段，所以两者行为暂时相同
    接口名写 PATCH 是为将来加字段时留的余地
    """
    conv = await require_conversation(db, conv_id)
    conv.title = payload.title
    # 【注意】：必须 flush —— updated_at 的 onupdate 在 flush 生成 UPDATE 时才求值，
    # 少这一行会让响应带着改动前的旧时间（此时 SQL 也还没发出去）
    await db.flush()
    # 不写 commit: 由 get_db 依赖统一提交（事务边界只在一处）
    # 与列表 / 详情返回同一种形状：否则前端拿 PATCH 响应刷新缓存会丢掉统计字段
    return await _fetch_conversation_stats(db, conv_id)


@app.get("/v1/conversations", response_model=ConversationPageOut)
async def list_conversations(
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100, description="这一页最多几条")] = 20,
    after_id: Annotated[int | None, Query(ge=0, description="游标：只返回 id 比它大的")] = None,
) -> ConversationPageOut:
    """
    分页列出对话（含账单统计），按 id 升序

    order_by 不能省：SQL 不保证返回顺序（"恰好"按插入顺序只是实现细节）

    【注意】：用游标 after_id 而不是 offset —— offset 数的是【位置】，数据增删会让位置漂移
        实测在翻页期间删一行会漏掉一条：游标数的是【值】（id > N），不受影响
    【注意】：必须 outerjoin —— 用 join 会让没有账单的对话整行消失
    【注意】：必须 coalesce —— SUM 遇到空集返回 NULL，响应里就变成 null 而不是 0
    """
    stmt = _conversation_stats_stmt()
    if after_id is not None:
        stmt = stmt.where(Conversation.id > after_id)

    # 多取一条来判断【还有没有下一页】—— 比再跑一次 COUNT 便宜
    rows = (await db.execute(stmt.order_by(Conversation.id).limit(limit + 1))).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    total = (await db.execute(select(func.count(Conversation.id)))).scalar_one()

    return ConversationPageOut(
        items=[_row_to_stats(r) for r in rows],
        total=total,
        limit=limit,
        next_cursor=rows[-1].id if has_more and rows else None,
        has_more=has_more,
    )


class SseResponse(StreamingResponse):
    """SSE 响应：让 /docs 把 200 的 content-type 标成 text/event-stream"""

    # 【注意】：只写 responses={200: {...}} 不够 —— FastAPI 会保留自动生成的
    #   application/json 一起合并，Swagger 里变成两个可选类型。必须靠 media_type 替换
    media_type = "text/event-stream"


# 【时序验证】流式必须起真服务；但 curl -w 的 ttfb 量的是"响应头"不是"首帧"
#   （2026-10-20 实测订正）要证明"内容在流"，必须用带时间戳的客户端量首个数据帧
@app.post("/v1/chat/stream", response_class=SseResponse)
async def chat_stream(
    # 客户端请求体：与 /v1/chat 复用同一份契约
    # （messages / model / temperature / max_tokens 四个字段都已在那里校验过）
    request: ChatRequest,
    # 【注意】：放在最前面 —— 依赖按参数顺序解析、按【反序】收尾，
    #   所以闸门是最后一个释放的：它覆盖到下面 db 的 commit 也做完
    _slot: UpstreamSlotDep,
    client: LlmClientDep,
    config: SettingsDep,
    db: DbDep,
) -> StreamingResponse:
    """真模型流式：逐帧解析上游，转发回答文字 + 结束原因 + token 用量（思维链按产品要求丢弃）"""

    # 与 /v1/chat 完全同一条业务规则，所以调同一个函数
    # 【注意】：必须放在 pre-flight 之前：否则会白花一次上游调用（真金白银）
    ensure_last_message_is_user(request)
    ensure_max_tokens_within_ceiling(request, config)

    # pre-flight：对话存在性必须在【打开上游流之前】查。放后面的话
    #   会白花一次上游调用，而且响应头已经发出，改不了 404
    if request.conversation_id is not None:
        await require_conversation(db, request.conversation_id)

    actual_model = request.model or config.llm_model

    # 客户端没指定 max_tokens 时用服务端上限兜底
    # 【注意】：不能"不传" = "不限制" —— 那样成本上限形同虚设（客户端只要不写这个字段就绕过去了）
    max_tokens = request.max_tokens if request.max_tokens is not None else config.max_tokens_ceiling

    # 上游请求体的字段名由 OpenAI 兼容协议规定
    body: dict[str, object] = {
        "model": actual_model,
        # Message 是 pydantic 模型，必须先 model_dump() 转成纯 dict 才能序列化
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
        "max_tokens": max_tokens,
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
        # raw_chunks=0 -> 上游根本没按 SSE 回（HTML / 空 body）
        # raw_chunks>0 而 content_frames=0 -> 回了帧但没有内容帧（忽略 stream=True / 只有思维链）
        raw_chunks = 0  # 收到的原始 SSE 帧数量
        content_frames = 0  # 其中包含回答文字的帧数量

        # 先落一行 pending 账单：断开 / 上游异常时它会被改成 aborted 后随请求事务落库
        # 【注意】：上游已产出的 token 照样收费 —— 不留这行，账面就看不到这次调用
        # 【注意】：必须是 commit 不是 flush —— flush 只发 SQL 不结束事务，写锁会一直持有到
        #   整条流结束，并发流会被 SQLite 串行化（见笔记 §12.7b、待办 #73）；而且 flush 不持久化，
        #   进程一崩这行就没了
        call = LlmCall(
            conversation_id=request.conversation_id,
            model=actual_model,
            status=LlmCallStatus.PENDING,
        )
        db.add(call)
        await db.commit()

        recorded = False  # 两阶段记账：幂等守卫

        # 先发一帧状态，前端可以立刻显示"模型思考中"
        #   注意：加了 pre-flight 之后，这一帧要等上游响应头回来才发得出去
        #   实测 TTFB 从 60.0ms 变成约 181~266ms，仍远小于首个内容帧的 845.8ms
        yield f"data: {json.dumps({'status': 'thinking'}, ensure_ascii=False)}\n\n"

        async def record_usage(usage: dict[str, Any]) -> None:
            """把这次调用记成一行账单：只记一次（usage 可能在多帧里重复出现）"""
            nonlocal recorded
            if recorded:
                return  # 【注意】：上游可能多帧给 usage，这里防止重复扣费
            recorded = True
            # 两阶段记账核心是用同一个对象走完全程，所以这里改字段而不是再 add 一行
            call.prompt_tokens = _as_int(usage.get("prompt_tokens"))
            call.completion_tokens = _as_int(usage.get("completion_tokens"))
            call.total_tokens = _as_int(usage.get("total_tokens"))
            call.status = LlmCallStatus.COMPLETED
            # 【注意】：commit 而不是 flush —— 同上，flush 会把写锁一直持有到请求结束
            await db.commit()

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
                usage = _as_dict(chunk.get("usage"))
                # 【注意】：记账必须排在下面三个 continue 之前 —— 结构坏的帧里 usage 可能是好的，
                #   一旦先 continue，这次调用的金额就永久丢了（见笔记 §12.5d、待办 #70）
                if usage:
                    await record_usage(usage)
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
                delta = _as_dict(choice.get("delta"))

                # 结束原因：只在最后一帧有值（"stop" = 模型自己说完 / "length" = 被截断）
                #   必须放在下面 content 的判断【之前】，否则会被 continue 跳过
                finish_reason = choice.get("finish_reason")
                # 只转发字符串：非字符串（如对象/数组）会让前端的 === "stop" 悄悄失效
                if isinstance(finish_reason, str) and finish_reason:
                    logger.info("流式结束: reason=%s", finish_reason)
                    payload = json.dumps({"finish_reason": finish_reason}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                elif finish_reason is not None and not isinstance(finish_reason, str):
                    # 上游给了结束原因但【不是字符串】—— 我们无法转发，
                    #   前端的 "说完 / 被截断" 判断会失效，所以必须留痕
                    #   （否则上游改结构了，我们事后完全查不到）
                    # 注意两个"不报警"的情况：
                    #   None / '' —— 都是"本帧还没有结束原因"，是正常的中间帧
                    logger.warning(
                        "上游 finish_reason 不是字符串，已丢弃: type=%s value=%r",
                        type(finish_reason).__name__,
                        finish_reason,
                    )

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
                # 零内容时金额是【不确定】的；上游可能已经扣费，但我们拿不到数字
                # 【注意】：有 usage 的情况走不到这里（recorded 已为 True，status 已是 completed）
                if not recorded:
                    call.status = LlmCallStatus.NO_CONTENT
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
            # 为什么【不能】放 finally 里：
            #   客户端断开时 Starlette 的 StreamingResponse 会取消任务，对生成器调 aclose()，
            #   后者往生成器里抛 GeneratorExit
            #   GeneratorExit 直接继承 BaseException（不是 Exception），所以只会走到 finally，
            #   不会进下面的 except 分支
            #   如果 finally 里 yield → 生成器试图"复活" → Python 拒绝（RuntimeError:
            #   async generator ignored GeneratorExit）
            # 为什么还要在 except 里【再写一次】：
            #   try 里的正常路径和 except 里的异常路径是两个【互斥】分支 ——
            #   异常一旦抛出，try 里后面的 yield 一行都不会执行
            #   所以"两条路都要发 [DONE]"必须在两个分支各写一次，不能靠 finally 兜
            yield "data: [DONE]\n\n"

        except Exception as exc:
            # 【异常路径：把错误编码进流，再收尾】
            # 上游给坏帧 / flush 失败等普通异常都会进这里
            # logger.exception 会带完整 traceback；而回给前端的只有一句人话
            # （绝不回显 str(exc) 或堆栈 —— 那可能泄露内部结构）
            # 上游已经产出的 token 照样收费，所以不能抹掉这一行，只能标成 aborted
            if not recorded:
                call.status = LlmCallStatus.ABORTED

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

        except BaseException:
            # 【注意】：必须是 BaseException —— CancelledError 继承它，except Exception 拦不住
            # 【注意】：这里只做同步赋值，绝不 await —— 此刻处在【已取消的 anyio cancel scope】里，
            #   任何 await 一进去就被再取消（实测 asyncio.shield 也挡不住；只有 anyio 的
            #   CancelScope(shield=True) 能挡，但没必要）；纯内存赋值不发 await，一定成功
            # 【判据】：可能被取消的路径上只做同步操作，落盘交给不会被取消的 get_db
            if not recorded:
                call.status = "aborted"
            raise

        finally:
            # 【注意】：finally 只做清理，绝不 yield
            # 【必须手动关】： open_chat_stream 没有 async with 帮我们关
            # 三条路都会走到这里：正常读完 / 流内异常 / 客户端断开（CancelledError）
            # 读完再关 = 连接归还池可复用；没读完就关 = 连接直接被销毁
            await upstream.aclose()

    # 返回流式响应：这里只负责上网，不负责产出
    return SseResponse(
        event_source(),
        headers={
            # 禁止中间层缓存这次响应（否则可能拿到别人的答案）
            "Cache-Control": "no-cache",
            # 给 nginx 看的：别缓冲，否则流式会被攒成一次性（部署时要注意）
            "X-Accel-Buffering": "no",
        },
    )
