"""pytest 的全局准备：本文件在任何测试模块被 import 前执行"""

import os
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


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试一份客户端：with 用来触发 lifespan"""
    with TestClient(app) as c:
        yield c
