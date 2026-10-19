"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

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

import httpx

# Query: 用于在上面勾选"这个查询参数要被怎么对待"，FastAPI 读它去约束和写文档
# status：是一个装了一堆 HTTP 状态码的模块
# HTTPException：是一个普通异常类，负责把异常抛给框架，再由框架翻译成 HTTP 响应
from fastapi import FastAPI, HTTPException, Query, Request, Response, status

from app.api.deps import LlmClientDep, SettingsDep
from app.constants import HEADER_REQUEST_ID
from app.errors import AppError, register_exception_handlers
from app.llm_client import create_llm_client
from app.schemas import ChatRequest, ChatResponse, ModelItem, ModelListResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用启动时建共享 client，关闭时关掉它（整个进程各一次，不是每请求）

    为什么用 async with 包住 yield：
        退出 async with 时会自动 await client.aclose()（httpx 的 __aexit__）
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-app-engineering",
    description="LLM 应用后端（学习项目，阶段 1）",
    version="0.1.0",
    lifespan=lifespan,
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


@app.post("/v1/chat")
async def chat(request: ChatRequest, config: SettingsDep) -> ChatResponse:
    """
    request 是【请求体】—— 类型是 pydantic 模型，所以 FastAPI 从 JSON body 里面取；
    config 是【依赖】—— FastAPI 调 get_settings() 后注入
    """
    last = request.messages[-1]
    # 语义检查：形状合法 ≠ 能回答。最后一条不是 user，就没有【要回答的问题】
    #   这种语义错（业务规则）不进 schemas.py
    #   规则：形状归 pydantic，语义归路由
    #
    # ⚠️ 这条规则【对当前这个问答接口正确】，但【不是绝对正确】，有些场景允许以 assistant 收尾
    #   我们的接口约定优先使用严格版，后续有支持续写的需求可以放开
    if last.role != "user":
        raise AppError(
            code="LAST_MESSAGE_NOT_USER",
            message=f"最后一条消息必须是 user，当前是 {last.role}",
        )
    return ChatResponse(content=f"[echo] {last.content}", model=request.model or config.llm_model)


async def fetch_upstream_models(client: LlmClientDep) -> list[ModelItem]:
    """
    查上游真实可用的模型名列表

    上游返回 10 个键，我们只用 3 个 —— 用 model_validate 把原始 dict 转成
    ModelItem: 多余的键被忽略（白名单），缺 id 会在这一行直接报错

    这是本项目第一次由服务端主动访问外部网络：
        之前的 /v1/models 返回的是硬编码的 KNOWN_MODELS；
        现在这条路由返回的是真实上游数据，形成对照

    单独成一个函数（而不是写在路由里）：
        1. 可测试 —— client 是参数，测试时能传假 client，不联网
        2. 职责清晰 —— 路由只管接请求/返响应，业务逻辑单独放

    ⚠️ 上游出错时这里不自己处理：直接让 httpx 的异常往上冒 ——
       上游【有回应】但状态码是 4xx/5xx → HTTPStatusError；
       上游【根本没回应】(连不上 / 超时) → RequestError。
       由调用方 upstream_models 把两者统一翻译成 502 Bad Gateway
    """
    resp = await client.get("/models")
    resp.raise_for_status()
    # json() 返回的是【未校验的原始数据】，声明成全 object 只是为了让 mypy 允许我们继续处理
    #   ⚠️ 这个注解防不住上游改结构：payload["data"] 若被改名会 KeyError → 500（不是 422 / 502）
    payload: dict[str, list[dict[str, object]]] = resp.json()
    # model_validate 是 Pydantic 的类方法，作用：
    #   把一个字典（或 JSON）校验并转换成 Pydantic 模型实例
    #   通过这个转换把不可信的原始数据变成经过校验、类型安全的 Python 对象
    return [ModelItem.model_validate(item) for item in payload["data"]]


# FastAPI 构建路由时会检查：有显式 response_model 就用它，没有就用【返回注解】
# 两者相同时只需写返回注解 —— 这里故意不写 response_model=，避免同一件事写两遍
@app.get("/v1/upstream/models")
async def upstream_models(client: LlmClientDep) -> ModelListResponse:
    """
    真实调用上游 /models。与 /v1/models（硬编码）对照用。

    client 是【依赖】：从 app.state 取出由 lifespan 创建的【应用级共享】客户端，
    请求结束不会被关闭（连接池要复用），进程关闭时由 lifespan 统一释放
    """
    # 更新：上游挂了返回 502（上游错误），不能返回 500（LLM 应用后端（我们）错误）
    try:
        models = await fetch_upstream_models(client)
    except httpx.HTTPStatusError as exc:
        # 错误类型 1：上游【有回应】但状态码是 4xx/5xx → 能读 exc.response.status_code
        #   ⚠️【上游报给服务器】的 401 与【服务器报给客户端】的 401 意义不同，所以不能透传
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"上游返回状态码 {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        # 错误类型 2：上游【根本没有回应】（连不上 / 超时 / DNS 失败）→ 没有 .response 可读
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法连接上游模型服务",
        ) from exc

    # total 由【我们】算：过滤后的条数，不是上游返回的条数
    #   现在还没加过滤，所以暂时等于 len(上游列表)；加了 prefix 过滤后两者就不相等了
    return ModelListResponse(total=len(models), items=models)
