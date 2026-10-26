"""
数据库引擎与会话工厂：决定"连哪个库"和"怎么造一次会话"

为什么单独一个文件（而不是写在 app.py 或者 models.py 里）：
    models.py 只描述【表的形状】，不该知道数据库在哪；
    app.py 是 HTTP 层，不该关心连接池
    把"连接"这件事集中在这里，将来换 PostgreSQL 只改这一个文件。

【注意】：引擎是【模块级单例】，不是每请求新建：连接池要跨请求复用。
   它的释放（dispose）放在 app.py 的 lifespan 关闭段，与进程同生命周期。

【注意】：本文件已打开 SQLite 的【外键强制】（见下面的 connect 监听器）。
   打开后，数据库层的 ondelete="CASCADE" 才会生效（📎 实测：打开前删父行会留下孤儿）。
   ⚠️ 但「子行会不会跟着删」还取决于 ORM 层：如果模型里有 relationship 却没写
   cascade="all, delete-orphan"，ORM 会先抢着把外键置成 NULL，数据库层的 CASCADE
   就无事可做 —— 即使外键已经开着，子行照样留下（📎 十组矩阵实测，详见笔记 §10.6a）
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# 【引擎】：持有连接池，负责"怎么连"。create_async_engine 只建对象，不建立连接
# （真正建立连接发生在第一次执行 SQL 时，所以这一行不会因为数据库不存在而报错）
engine = create_async_engine(settings.database_url)


# 【监听器】：每条连接建立时，先打开外键强制，再交给 SQLAlchemy 使用
# 为什么必须写这段：SQLite 默认【不强制】外键（PRAGMA foreign_keys=0），
#   即使建表语句里写了 FOREIGN KEY，插一个不存在的 conversation_id 也会成功
#   （实测能插进 999，记录变成孤儿）
# 为什么挂在 "connect" 事件上，而不是执行一次 PRAGMA：PRAGMA 是【单条连接】的开关，
#   而且断开重连就恢复默认（它不持久化到数据库文件）。
#   连接池里每条新建的连接都要单独打开；只执行一次的话，池里其它连接仍然是不强制的
# 为什么用 sync_engine：event 监听的是同步引擎这一层（连接池和 DBAPI 都在这层），
#   而拿到的连接对象是 SQLAlchemy 的【适配连接】
#   （sqlalchemy.dialects.sqlite.aiosqlite.AsyncAdapt_aiosqlite_connection，实测确认），
#   它在 greenlet 上下文里提供同步风格的 cursor()，可以直接调
# 为什么参数注解用 Any：运行时的对象不是原生 aiosqlite.Connection。
#   实测注解成 object 会报「没有 cursor 属性」，注解成 aiosqlite.Connection 会报
#   「Result[Cursor] 没有 execute」（因为原生 cursor() 是 awaitable）。
#   注解成 Any 是唯一与事实相符又不撒谎的写法
@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """每条新连接建立时执行：打开 SQLite 的外键强制开关"""
    # 游标（cursor）是 DBAPI 里「发语句 + 拿结果」的载体：连接对象本身不保存执行状态，
    # 游标才保存"这次查询走到第几行了"
    # 也可以用便捷写法 dbapi_connection.execute(...)（实测同样生效、无警告），
    # 但那是内部偷偷建了个游标且不还给你关闭；显式写 cursor + close() 是
    # SQLAlchemy 官方 recipe 的写法，释放时机明确
    # 这里发的是 PRAGMA 而不是 SQL 查询，所以不需要读结果
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
