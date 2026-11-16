"""测「迁移」这一层：迁移文件建出来的库，是否等于模型（metadata）描述的库

【注意】：这是 schema 的唯一守卫 —— 其它测试都跑在「已经建好表」的库上，
模型改了却忘生成迁移时它们全绿，只有这里会红
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.models import Base

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_TABLE = "alembic_version"


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess[str]:
    """在子进程里跑一条 alembic 命令，库指向调用方给的路径

    【注意】：必须用子进程 —— env.py 的连接串取自 settings，而它是 import 那一刻定死的单例，
    进程内改不动；子进程换一个 DATABASE_URL 即可
    """
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _schema(db_path: Path) -> dict[tuple[str, str], str]:
    """库里每个对象的 DDL（表 / 索引），空白归一后比较

    【注意】：排除 alembic_version —— 它由迁移工具自己维护，不属于模型
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()
    return {
        (row_type, name): " ".join((sql or "").split())
        for row_type, name, sql in rows
        if name != _VERSION_TABLE
    }


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """跑一次真实迁移，拿到「迁移建出来的库」；本模块两个用例共用"""
    db_path = tmp_path_factory.mktemp("migrations") / "migrated.db"
    result = _run_alembic(["upgrade", "head"], db_path)
    assert result.returncode == 0, f"alembic upgrade head 失败：\n{result.stdout}\n{result.stderr}"
    return db_path


def test_migrations_leave_no_drift(migrated_db: Path) -> None:
    result = _run_alembic(["check"], migrated_db)
    assert result.returncode == 0, (
        "迁移与模型不同步：改了 models.py 就要 alembic revision --autogenerate 并提交迁移\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_migration_ddl_matches_create_all(migrated_db: Path, tmp_path: Path) -> None:
    created_db = tmp_path / "created.db"
    engine = create_engine(f"sqlite:///{created_db.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    from_migrations = _schema(migrated_db)
    from_create_all = _schema(created_db)
    only_migrations = from_migrations.keys() - from_create_all.keys()
    only_create_all = from_create_all.keys() - from_migrations.keys()
    different = {
        key: (from_migrations[key], from_create_all[key])
        for key in from_migrations.keys() & from_create_all.keys()
        if from_migrations[key] != from_create_all[key]
    }
    assert not (only_migrations or only_create_all or different), (
        "迁移建出的 DDL 与 create_all 不一致：\n"
        f"只在迁移里：{sorted(only_migrations)}\n"
        f"只在 create_all 里：{sorted(only_create_all)}\n"
        f"定义不同：{different}"
    )
