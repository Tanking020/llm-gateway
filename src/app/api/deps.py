"""
依赖注入的集中地：把 [接口需要用到的资源] 做成可复用、可替换的依赖

依赖注入：接口函数不自己去拿它需要的东西，而是在参数里"声明"我需要一个配置对象，
然后由框架负责把它送进来。deps.py 就是所有这类"声明"的集中存放处

为什么单独一个文件：
    依赖会被多个路由共用：全写在 app.py 里会让路由文件越来越臃肿

只有路由函数会写 Depends；services/ 层不该知道 HTTP 是什么。
    放 api/ 里，services/ 就永远不会反向 import 到它
"""

# AsyncIterator 是 Python 中异步迭代器的类型，核心作用是：
#   逐个获取数据，但每次获取都需要等待（await），而且不一次性加载全部数据到内存
#   在 SSE 流式中它让"一个请求"的数据能边收边发而不是等全部生成完再一次返回
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import Settings, settings
from app.llm_client import create_llm_client


def get_settings() -> Settings:
    """
    提供全局配置对象

    做成依赖的意义：测试时可以用 app.dependency_overrides 把它替换成
    假配置，不必去改 .env，也不必 mock 模块

    造了一个可替换的接缝，有接缝才能替换：dependency_overrides[get_settings] = ...
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_llm_client() -> AsyncIterator[httpx.AsyncClient]:
    """
    每个请求造一个 HTTP 客户端，请求结束时【由框架关闭】

    生命周期跟着【请求】走 -> yield 依赖
    跟着【应用】走 -> lifespan
    （实际上 HTTP 客户端通常“应该” 全局共享，本项目这里这么做是教学选择，不是性能最优）

    注意：async with 包住 yield，是为了保证【路由抛异常时也能关闭】；
    如果把关闭写成 yield 之后的普通语句，异常时那行会被跳过

    因此核心规则：yield之后只写“清理”，而且清理必须包在 async with 或
    try / finally 里 —— 绝不要写成裸的普通语句
    """
    async with create_llm_client() as client:
        # yield vs return : yield = "暂停并返回一个值，下次从暂停处继续"
        # 在 FastAPI 里，它主要用于：流式输出（打字机效果）和依赖注入（自动关闭资源）
        yield client


# Annotated[类型, Depends(函数)] = “这个参数的值，由 Depends 里的函数来提供”
LlmClientDep = Annotated[httpx.AsyncClient, Depends(get_llm_client)]
