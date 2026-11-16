"""最小冒烟测试：证明 tests/ 能跑起来、lifespan 真的执行过、独立临时库生效、健康检查两态"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession


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
