"""
依赖注入的集中地：把 [接口需要用到的资源] 做成可复用、可替换的依赖

依赖注入：接口函数不自己去拿它需要的东西，而是在参数里"声明"我需要一个配置对象，
然后由框架负责把它送进来。deps.py 就是所有这类"声明"的集中存放处

为什么单独一个文件：
    依赖会被多个路由共用：全写在 app.py 里会让路由文件越来越臃肿

只有路由函数会写 Depends；services/ 层不该知道 HTTP 是什么。
    放 api/ 里，services/ 就永远不会反向 import 到它
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import SessionMaker
from app.errors import AppError
from app.llm_client import LlmClient

logger = logging.getLogger(__name__)


def get_settings() -> Settings:
    """
    提供全局配置对象

    做成依赖的意义：测试时可以用 app.dependency_overrides 把它替换成假配置，
    不必去改 .env，也不必 mock 模块

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
    一次请求一个数据库会话：写路由自己 commit，这里只做「收尾兜底提交 + 异常回滚」

    【注意】：这里的 commit 跑在【响应已经发出去之后】，保证不了状态码正确 ——
        所以普通写路由必须在 return 之前自己 commit
        （#54 实测：只在收尾提交时，回 201 但库里没有那一行）。
    【注意】：但它也【不能删】—— 流式收尾（no_content / aborted）的写入发生在响应开始之后，
        且取消路径上不允许 await（见 app.py 的 except BaseException），只能靠这里落盘。

    为什么用 yield 而不是 return：
        会话和事务的生命周期必须【跨整个路由函数】—— 路由要先用会话查数据、
        再改数据、最后才返回。所以框架只能在【路由跑完之后】收尾，
        这正是 yield 依赖提供的能力

    【注意】：except 里必须 raise：不写不会让客户端出错（响应看起来完全一样），
       但日志里原始异常会被 FastAPIError 顶替 —— 根因、类型、行号全丢
    """
    async with SessionMaker() as session:
        # 【注意】：先单独探一次「连得上吗」—— 连不上是【依赖不可用】(503)，
        #   SQL/表结构写错（no such table）必须留在 500。两者都是 OperationalError，
        #   只能靠【抛出阶段】区分：connection() 在建立连接时抛，execute() 在跑 SQL 时抛
        try:
            await session.connection()
        except OperationalError as exc:
            # 只记类型：连接串 / 库路径可能出现在 str(exc) 里
            logger.warning("数据库连接失败：%s", type(exc).__name__)
            raise AppError("DB_UNAVAILABLE", "数据库不可用", headers={"Retry-After": "1"}) from exc
        try:
            yield session  # 路由在这里跑；路由抛异常时，异常会被"抛回"这一行
            # 【注意】：正常路径的兜底提交：只为流式收尾那类「响应已开始后才写」的改动落盘；
            #   普通写路由已在自己 return 前 commit 过，这里是一次空提交
            await session.commit()
        except Exception:
            await session.rollback()  # 出错先回滚，再把异常重新抛出
            raise


DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_upstream_slot(request: Request, config: SettingsDep) -> AsyncIterator[None]:
    """
    上游并发闸门：抢到一个槽位才允许打上游，抢不到就回 503

    【注意】：必须是 yield 依赖 —— 槽位要持有到【整条流结束】才还。
        这正是"同时在生成的上游调用数"该算的范围；与 get_db 相反（那边要尽早还）。
        机制上靠的就是 #59 实测到的"yield 依赖收尾发生在响应彻底结束之后"。
    """
    semaphore: asyncio.Semaphore = request.app.state.upstream_semaphore
    try:
        # 有限等待而不是无限排队：排队期间客户端什么都收不到，还占着 socket
        await asyncio.wait_for(semaphore.acquire(), timeout=config.upstream_queue_timeout)
    except TimeoutError:
        # from None：上面那个 TimeoutError 是预期内的控制流，不该出现在 traceback 里
        raise AppError(
            "SERVER_BUSY", "服务繁忙，请稍后重试", headers={"Retry-After": "1"}
        ) from None
    try:
        yield
    finally:
        semaphore.release()


UpstreamSlotDep = Annotated[None, Depends(get_upstream_slot)]
