"""
FastAPI 应用对象：本项目对外的 HTTP 服务入口

为什么不写进 main.py:
    main.py 是工程基础阶段的【命令行程序】（跑完即退出）；
    本文件是【常驻服务】的应用对象，两者生命周期与职责都不同
"""

# Annotated：用于给函数签名中参数的 "类型位" 扩容
from typing import Annotated

# Query: 用于在上面勾选"这个查询参数要被怎么对待"，FastAPI 读它去约束和写文档
from fastapi import FastAPI, Query

from app.api.deps import SettingsDep
from app.schemas import ChatRequest, ChatResponse

# app 就是 uvicorn 要托管的那个对象
# 命令行里写 app.api.app:app 的读法：包 app -> 子包 api -> 模块 app -> 里面的变量 app
app = FastAPI(
    title="llm-service",
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
    return {"model_name": model_name}


@app.post("/v1/chat")
async def chat(request: ChatRequest, config: SettingsDep) -> ChatResponse:
    """
    request 是【请求体】—— 类型是 pydantic 模型，所以 FastAPI 从 JSON body 里面取；
    config 是【依赖】—— FastAPI 调 get_settings() 后注入
    """
    last = request.messages[-1]
    return ChatResponse(content=f"[echo] {last.content}", model=request.model or config.llm_model)
