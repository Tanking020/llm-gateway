"""
依赖注入的集中地：把 [接口需要用到的资源] 做成可复用、可替换的依赖

依赖注入：接口函数不自己去拿它需要的东西，而是在参数里"声明"我需要一个配置对象，
然后由框架负责把它送进来。deps.py 就是所有这类"声明"的集中存放处

为什么单独一个文件：
    依赖会被多个路由共用：全写在 app.py 里会让路由文件越来越臃肿

只有路由函数会写 Depends；services/ 层不该知道 HTTP 是什么。
    放 api/ 里，services/ 就永远不会反向 import 到它
"""

from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.config import Settings, settings


def get_settings() -> Settings:
    """
    提供全局配置对象

    做成依赖的意义：测试时可以用 app.dependency_overrides 把它替换成
    假配置，不必去改 .env，也不必 mock 模块

    造了一个可替换的接缝，有接缝才能替换：dependency_overrides[get_settings] = ...
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_llm_client(request: Request) -> httpx.AsyncClient:
    """从 app.state 里取【应用级共享】的 HTTP 客户端（生命周期由 lifespan 管，不是请求）"""
    # request.app 就是那个 FastAPI 实例：state 是挂在它身上的"任意属性袋"
    client: httpx.AsyncClient = request.app.state.llm_client
    return client


# Annotated[类型, Depends(函数)] = “这个参数的值，由 Depends 里的函数来提供”
LlmClientDep = Annotated[httpx.AsyncClient, Depends(get_llm_client)]
