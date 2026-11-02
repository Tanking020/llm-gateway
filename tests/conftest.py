"""pytest 的全局准备：本文件在任何测试模块被 import 前执行"""

import os

# sqlite3 这个库支持直接执行 SQL 字符串
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

# 在测试启动前，先把环境变量设好，再 import app:
#   原因：settings 是模块级单例，import 那一刻就定死了
# 设置测试数据库路径
_TEST_DB = Path(tempfile.gettempdir()) / "llm-app-test.db"
# 删除旧的测试数据库文件
for _suffix in ("", "-wal", "-shm"):
    Path(str(_TEST_DB) + _suffix).unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _TEST_DB.as_posix()
os.environ["APP_ENV"] = "dev"
os.environ["DEBUG"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.app import app  # noqa: E402
from app.models import Base  # noqa: E402


def _truncate_all() -> None:
    """
    清空所有业务表：让每个测试都从空库开始

    【注意】：必须在 with 之后调用 —— 表是 lifespan 里的 create_all 建的
    """
    conn = sqlite3.connect(str(_TEST_DB))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        # 开启外键约束后需要按 子->父 的顺序做删除
        for table in reversed(Base.metadata.sorted_tables):
            # 只清数据，保留表结构，不必再 create_all
            conn.execute(f"DELETE FROM {table.name}")
        conn.commit()
    finally:
        conn.close()


# @pytest.fixture 的三种常见用法: 返回数据，创建对象，清理资源，这里是返回数据（依赖注入）
@pytest.fixture
def db_path() -> Path:
    """测试库的文件路径：想绕过 API 直接查库的测试用它（路径只有本文件知道）"""
    return _TEST_DB


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试一份客户端：with 用来触发 lifespan"""
    with TestClient(app) as c:
        _truncate_all()
        yield c
