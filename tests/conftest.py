"""pytest 的全局准备：本文件在任何测试模块被 import 前执行

【注意】：建表由 alembic 迁移负责（决策 32）—— 迁移文件写错时这里会先炸
"""

import os

# sqlite3 这个库支持直接执行 SQL 字符串
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

# 在测试启动前，先把环境变量设好，再 import app:
#   原因：settings 是模块级单例，import 那一刻就定死了
# 设置测试数据库路径
# 【注意】：文件名必须带进程号（#87 / 坑 K94）—— 固定文件名时，两个 pytest
#   （或「刚跑完紧接着再跑」）会互相 DELETE 对方的表，表现为偶发 `76 errors`，
#   而偶发红比稳定红更贵：它让人学会「重跑一次」，真 bug 也会被重跑掉
_TEST_DB = Path(tempfile.gettempdir()) / f"llm-app-test-{os.getpid()}.db"
# 删除旧的测试数据库文件（只可能是【本进程】上一次残留，pid 被复用时才会命中）
for _suffix in ("", "-wal", "-shm"):
    Path(str(_TEST_DB) + _suffix).unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _TEST_DB.as_posix()
os.environ["APP_ENV"] = "dev"
os.environ["DEBUG"] = "false"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.app import app  # noqa: E402
from app.auth import hash_api_key  # noqa: E402
from app.constants import HEADER_API_KEY  # noqa: E402
from app.models import Base  # noqa: E402

# 测试套件固定使用的两把 key（明文只在这里出现；库里存的是它的 sha256）
TEST_API_KEY = "sk-test-alice"
OTHER_API_KEY = "sk-test-bob"
AUTH_HEADERS = {HEADER_API_KEY: TEST_API_KEY}
OTHER_HEADERS = {HEADER_API_KEY: OTHER_API_KEY}

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated() -> Iterator[None]:
    """整个会话只建一次表：跑真实迁移，让「迁移文件写错」在这里就炸"""
    # 【注意】：ini 用绝对路径 —— alembic 内部的 script_location 是相对 ini 所在目录解析的；
    # 写死路径后从任何工作目录跑 pytest 都能找到 alembic/
    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    # 【注意】：一条 revision 都没有时 upgrade 静默成功（实测）→ 必须自己断言表已建出，
    #   否则症状会变成别的用例里的 no such table（根因不直观）
    conn = sqlite3.connect(str(_TEST_DB))
    try:
        found = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    missing = {table.name for table in Base.metadata.sorted_tables} - found
    assert not missing, (
        f"迁移没有建出这些表：{sorted(missing)} —— alembic/versions/ 的迁移文件提交了吗？"
    )
    yield
    # 会话结束删掉本进程的库（尽力而为）：Windows 上连接没完全释放时会报 PermissionError，
    # 忽略即可 —— 下次是另一个文件名，不会打架
    for _suffix in ("", "-wal", "-shm"):
        with suppress(OSError):
            Path(str(_TEST_DB) + _suffix).unlink(missing_ok=True)


def _truncate_all() -> None:
    """
    清空所有业务表：让每个测试都从空库开始

    【注意】：必须在 migrated 之后调用 —— 表由它建（别再依赖 lifespan 的 create_all）
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


def _seed_identities() -> None:
    """写入两个测试用户 + 两把 key

    【注意】：13d-2 起所有业务端点都要 X-API-Key —— 这里直接写库（不走 HTTP），
        因为签发接口本身也需要鉴权，用它准备测试数据会绕成一个圈
    """
    conn = sqlite3.connect(str(_TEST_DB))
    try:
        for user_id, name, raw in ((1, "alice", TEST_API_KEY), (2, "bob", OTHER_API_KEY)):
            conn.execute(
                "INSERT INTO users (id, name, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (user_id, name),
            )
            conn.execute(
                "INSERT INTO api_keys (user_id, key_hash, label, created_at)"
                " VALUES (?, ?, 'suite', CURRENT_TIMESTAMP)",
                (user_id, hash_api_key(raw)),
            )
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """清空业务表并写入测试身份 —— client 与 live_server 两类 fixture 共用"""
    _truncate_all()
    _seed_identities()


# @pytest.fixture 的三种常见用法: 返回数据，创建对象，清理资源，这里是返回数据（依赖注入）
@pytest.fixture
def db_path() -> Path:
    """测试库的文件路径：想绕过 API 直接查库的测试用它（路径只有本文件知道）"""
    return _TEST_DB


@pytest.fixture
def client() -> Iterator[TestClient]:
    """每个测试一份客户端：with 用来触发 lifespan；默认带上 alice 的 key"""
    with TestClient(app, headers=AUTH_HEADERS) as c:
        reset_db()
        yield c


@pytest.fixture
def other_client(client: TestClient) -> Iterator[TestClient]:
    """bob 的客户端（依赖 client 保证库已清空并写好身份）"""
    with TestClient(app, headers=OTHER_HEADERS) as c:
        yield c


@pytest.fixture
def anon_client(client: TestClient) -> Iterator[TestClient]:
    """不带任何凭据的客户端：测 401 用"""
    with TestClient(app) as c:
        yield c
