"""Alembic 运行环境：告诉 alembic「连哪个库」和「表的定义在哪」。

同时被 alembic CLI 与测试（conftest 里 in-process 调 command.upgrade）使用
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.models import Base

config = context.config

# 【注意】：disable_existing_loggers 必须 False。默认 True 会把已建好的 logger 全置 disabled，
# 测试里 caplog 就抓不到 app.* 日志（表现为「找不到那条日志」，根因不直观）。见 DEVLOG 坑 K87
config_file_name = config.config_file_name
if config_file_name is not None:
    fileConfig(config_file_name, disable_existing_loggers=False)

# 【注意】：连接串以 settings 为唯一事实来源；% 必须转义成 %%，否则 configparser
# 会把它当插值语法直接抛 ValueError。见坑 K88
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：不连库，只把 SQL 打到 stdout"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在已建立的连接上执行迁移（同步签名，由 run_sync 包一层）"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：建异步引擎 → 借一条连接 → 交给同步入口

    【注意】：NullPool —— 迁移是一次性动作，留连接池只会多一步 dispose 等待
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
