"""最小冒烟测试：证明 tests/ 能跑起来、lifespan 真的执行过、独立临时库生效、健康检查两态"""

import os
import subprocess
import sys
from pathlib import Path

import conftest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_conversation(client: TestClient) -> None:
    r = client.post("/v1/conversations", json={"title": "测试对话"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "测试对话"
    assert body["call_count"] == 0


def test_ready_when_db_is_ok(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_ready_returns_503_when_db_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """回归：DB 挂了必须是 503 + DB_UNAVAILABLE（让编排系统摘流量），不是 500"""

    async def boom(*args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(AsyncSession, "execute", boom)
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "DB_UNAVAILABLE"


def test_test_db_path_is_per_process() -> None:
    """回归 #87：测试库必须「一进程一个」—— 否则两个 pytest 会互相 DELETE 对方的表

    【注意】：这里真的起一个子进程去 import conftest —— 只断言「路径里含我自己 pid」
        属于复述实现，改坏真实行为时不会红（假的守卫）
    """
    code = "import conftest, os, sys; sys.stdout.write(f'{os.getpid()}|{conftest._TEST_DB.name}')"
    child = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_TESTS_DIR),
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    child_pid, child_db = child.stdout.strip().split("|")

    assert child_db != conftest._TEST_DB.name, f"子进程与本进程用了同一个测试库：{child_db}"
    assert str(os.getpid()) in conftest._TEST_DB.name, conftest._TEST_DB.name
    assert child_pid in child_db, f"子进程的库名里没有它的 pid：{child_db}"
