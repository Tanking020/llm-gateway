"""
数据库引擎与会话工厂：决定"连哪个库"和"怎么造一次会话"

为什么单独一个文件（而不是写在 app.py 或者 models.py 里）：
    models.py 只描述【表的形状】，不该知道数据库在哪；
    app.py 是 HTTP 层，不该关心连接池
    把"连接"这件事集中在这里，将来换 PostgreSQL 只改这一个文件。

【注意】：引擎是【模块级单例】，不是每请求新建：连接池要跨请求复用。
   它的释放（dispose）放在 app.py 的 lifespan 关闭段，与进程同生命周期。

【注意】：本文件已打开 SQLite 外键强制。打开后 ondelete="CASCADE" 才生效；
   但若模型里有 relationship 却忘了写 cascade，ORM 会先把外键置 NULL，
   数据库层就无事可做（子行留下）。完整规则见笔记 §10.6a。
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# 引擎：持有连接池，负责"怎么连"。create_async_engine 只建对象，不建立连接
# （真正建立连接发生在第一次执行 SQL 时，所以这一行不会因为数据库不存在而报错）
engine = create_async_engine(settings.database_url)


# SQLite 默认不强制外键（PRAGMA foreign_keys=0），且该开关是【每条连接】一份、
# 不持久化 —— 所以必须挂 "connect" 事件逐条打开，不能只在启动时执行一次
@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """每条新连接建立时执行：打开 SQLite 的外键强制开关

    注解写 Any：拿到的不是原生 aiosqlite.Connection，而是 SQLAlchemy 的同步风格
    适配连接（写 object 或 aiosqlite.Connection 都会让 mypy 报错）。
    为什么用 sync_engine、为什么需要游标，见笔记 §10.6b-1
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 【会话工厂】：一个"造会话的模具"。SessionMaker() 每次调用产出一个新的 AsyncSession
# 【注意】：expire_on_commit=False：commit 之后对象的属性仍然可读
#   如果保持默认 True，commit 后访问 conv.title 会触发一次隐式查询，
#   而异步下如果发生在同步序列化阶段（如 response_model 处理时）就无法 await → 报错
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

# 重新导出一遍，让调用方只 import 这一个文件就能拿到三样东西
__all__ = ["engine", "SessionMaker", "AsyncSession"]
