"""测「迁移」这一层：迁移文件建出来的库，是否等于模型（metadata）描述的库

【注意】：这是 schema 的唯一守卫 —— 其它测试都跑在「已经建好表」的库上，
模型改了却忘生成迁移时它们全绿，只有这里会红

【注意】：比的是【结构】不是 SQL 文本 —— SQLite 没有任何 ALTER COLUMN，
    alembic 的 batch 模式（建新表 → 拷数据 → 改名）会让 sqlite_master 里的语句
    带上双引号表名、把列追加到末尾、给外键加 CONSTRAINT 名字。这些都不改变语义，
    但会让「文本相等」的比较误报。所以这里用 PRAGMA 读出结构来比。
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


def _schema(db_path: Path) -> dict[str, dict[str, object]]:
    """库里每张表的【结构】：列 / 外键 / 索引 / 唯一约束

    【注意】：排除 alembic_version —— 它由迁移工具自己维护，不属于模型。
    列按名字排序、约束按内容排序：顺序不是语义，缺一个才是
    """
    conn = sqlite3.connect(str(db_path))
    try:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            if row[0] != _VERSION_TABLE
        ]
        out: dict[str, dict[str, object]] = {}
        for table in names:
            columns = sorted(
                (name, decl_type, bool(notnull), int(pk), default)
                for _cid, name, decl_type, notnull, default, pk in conn.execute(
                    f"PRAGMA table_info({table})"
                )
            )
            # PRAGMA foreign_key_list 的列序：id, seq, table(父表), from(本表列), to(父表列),
            #   on_update, on_delete, match —— 只取会改变语义的前五项
            foreign_keys = sorted(
                (row[3], row[2], row[4], row[5], row[6])
                for row in conn.execute(f"PRAGMA foreign_key_list({table})")
            )
            constraints: list[tuple[str, bool, tuple[str, ...]]] = []
            for row in conn.execute(f"PRAGMA index_list({table})"):
                # 列序：seq, name, unique, origin, partial —— origin: c=CREATE INDEX，
                #   u=UNIQUE 约束自动建的，pk=主键（主键已在 columns 里体现，跳过）
                index_name, unique, origin = row[1], bool(row[2]), row[3]
                if origin == "pk":
                    continue
                cols = tuple(r[2] for r in conn.execute(f"PRAGMA index_info({index_name})"))
                constraints.append(("unique" if origin == "u" else "index", unique, cols))
            out[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "constraints": sorted(constraints),
            }
        return out
    finally:
        conn.close()


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


def test_migration_schema_matches_create_all(migrated_db: Path, tmp_path: Path) -> None:
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
        table: {"迁移": from_migrations[table], "create_all": from_create_all[table]}
        for table in from_migrations.keys() & from_create_all.keys()
        if from_migrations[table] != from_create_all[table]
    }
    assert not (only_migrations or only_create_all or different), (
        "迁移建出的结构与 create_all 不一致：\n"
        f"只在迁移里：{sorted(only_migrations)}\n"
        f"只在 create_all 里：{sorted(only_create_all)}\n"
        f"结构不同：{different}"
    )
