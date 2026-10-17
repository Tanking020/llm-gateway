"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

# Annotated：用于给函数签名中参数的 "类型位" 扩容
from typing import Annotated

import httpx

# Query: 用于在上面勾选"这个查询参数要被怎么对待"，FastAPI 读它去约束和写文档
# status：是一个装了一堆 HTTP 状态码的模块
# HTTPException：是一个普通异常类，负责把异常抛给框架，再由框架翻译成 HTTP 响应
from fastapi import FastAPI, HTTPException, Query, status

from app.api.deps import LlmClientDep, SettingsDep
from app.schemas import ChatRequest, ChatResponse

# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-app-engineering",
    description="LLM 应用后端（学习项目，阶段 1）",
    version="0.1.0",
)


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
    return ChatResponse(content=f"[echo] {last.content}", model=request.model or config.llm_model)


async def fetch_upstream_models(client: LlmClientDep) -> list[str]:
    """
    查上游真实可用的模型名列表

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
    payload: dict[str, list[dict[str, object]]] = resp.json()
    return [str(item["id"]) for item in payload["data"]]


@app.get("/v1/upstream/models")
async def upstream_models(client: LlmClientDep) -> dict[str, object]:
    """
    真实调用上游 /models。与 /v1/models（硬编码）对照用。

    client 是【依赖】：框架造好并注入，请求结束后自动关闭
    """
    # 更新：上游挂了返回 502（上游错误），不能返回 500（LLM 应用后端（我们）错误）
    try:
        model_ids = await fetch_upstream_models(client)
    except httpx.HTTPStatusError as exc:
        # 错误类型 1：上游【有回应】但状态码是 4xx / 5xx：
        #   把上游的号码告诉客户端，但不说细节
        #   ！注意区分：【上游报给服务器】的 401 和【服务器报给客户端】的 401 意义并不一样
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"上游返回状态码 {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        # 错误类型 2：上游【根本没回应】：连不上 / 超时 / DNS 失败
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法连接上游模型服务",
        ) from exc

    return {"total": len(model_ids), "items": model_ids}
