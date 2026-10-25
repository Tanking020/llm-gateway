"""
依赖注入的集中地：把 [接口需要用到的资源] 做成可复用、可替换的依赖

依赖注入：接口函数不自己去拿它需要的东西，而是在参数里"声明"我需要一个配置对象，
然后由框架负责把它送进来。deps.py 就是所有这类"声明"的集中存放处

为什么单独一个文件：
    依赖会被多个路由共用：全写在 app.py 里会让路由文件越来越臃肿

只有路由函数会写 Depends；services/ 层不该知道 HTTP 是什么。
    放 api/ 里，services/ 就永远不会反向 import 到它
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import SessionMaker
from app.llm_client import LlmClient


def get_settings() -> Settings:
    """
    提供全局配置对象

    做成依赖的意义：测试时可以用 app.dependency_overrides 把它替换成
    假配置，不必去改 .env，也不必 mock 模块

    造了一个可替换的接缝，有接缝才能替换：dependency_overrides[get_settings] = ...
    """
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_llm_client(request: Request) -> LlmClient:
    """从 app.state 里取【应用级共享】的上游适配器（生命周期由 lifespan 管，不是请求）"""
    # request.app 就是那个 FastAPI 实例：state 是挂在它身上的"任意属性袋"
    client: LlmClient = request.app.state.llm_client
    return client


# Annotated[类型, Depends(函数)] = “这个参数的值，由 Depends 里的函数来提供”
# 注意这里声明的是 LlmClient 而不是 httpx.AsyncClient：
# 路由代码里拿到的对象物理上只有 LlmClient 的方法
# 没有 .get / .stream 这些 httpx 原生方法可调，从类型层面就杜绝了"绕过错误翻译直接调上游"的可能
LlmClientDep = Annotated[LlmClient, Depends(get_llm_client)]


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    一次请求一个数据库会话：正常结束自动提交，出异常自动回滚

    为什么用 yield 而不是 return：
        会话和事务的生命周期必须【跨整个路由函数】—— 路由要先用会话查数据、
        再改数据、最后才返回。所以框架只能在【路由跑完之后】收尾，
        这正是 yield 依赖提供的能力

    ⚠️ except 里必须 raise：不写不会让客户端出错（响应看起来完全一样），
       但日志里原始异常会被 FastAPIError 顶替 —— 根因、类型、行号全丢
    """
    async with SessionMaker() as session:
        try:
            yield session  # 路由在这里跑；路由抛异常时，异常会被"抛回"这一行
            await session.commit()  # 只有正常路径才走到（事务边界收在这一处）
        except Exception:
            await session.rollback()  # 出错先回滚，再把异常重新抛出
            raise


DbDep = Annotated[AsyncSession, Depends(get_db)]
