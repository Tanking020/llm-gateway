"""对话接口的 HTTP 契约测试：断言状态码 / 响应形状 / 落库效果，不断言 SQL 细节"""

import sqlite3
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from conftest import AUTH_HEADERS
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import app


def _create(client: TestClient, title: str) -> dict[str, object]:
    """建一条对话并返回响应体：201 视为成功，其余直接让断言炸在这里"""
    response = client.post("/v1/conversations", json={"title": title})
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_create_then_get(client: TestClient) -> None:
    created = _create(client, "第一个对话")
    assert created["id"] == 1
    assert created["call_count"] == 0
    assert created["total_tokens"] == 0

    response = client.get(f"/v1/conversations/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "第一个对话"


def test_get_missing_returns_404(client: TestClient) -> None:
    response = client.get("/v1/conversations/999")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "CONVERSATION_NOT_FOUND"
    assert error["request_id"] == response.headers["x-request-id"]


def test_patch_updates_title(client: TestClient) -> None:
    created = _create(client, "旧标题")
    response = client.patch(f"/v1/conversations/{created['id']}", json={"title": "新标题"})
    assert response.status_code == 200
    assert response.json()["title"] == "新标题"


def test_delete_then_gone(client: TestClient) -> None:
    created = _create(client, "待删")
    response = client.delete(f"/v1/conversations/{created['id']}")
    assert response.status_code == 204
    assert response.text == ""

    assert client.get(f"/v1/conversations/{created['id']}").status_code == 404
    assert client.delete(f"/v1/conversations/{created['id']}").status_code == 404


# 这个装饰器的作用是：把下面这个测试函数，变成 3 个独立的测试用例
#   分别用 3 组不同的 payload 数据去执行
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"title": "   "}, id="blank"),
        pytest.param({"title": "x" * 101}, id="too_long"),
        pytest.param({}, id="missing"),
    ],
)
def test_invalid_title_returns_422(client: TestClient, payload: dict[str, str]) -> None:
    response = client.post("/v1/conversations", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["loc"] == ["body", "title"]


def test_title_is_stripped(client: TestClient) -> None:
    created = _create(client, "  带空格  ")
    assert created["title"] == "带空格"


def test_pagination_walks_two_pages(client: TestClient) -> None:
    for title in ("c1", "c2", "c3"):
        _create(client, title)

    first = client.get("/v1/conversations", params={"limit": 2}).json()
    assert [item["title"] for item in first["items"]] == ["c1", "c2"]
    assert first["total"] == 3
    assert first["has_more"] is True
    assert first["next_cursor"] == 2

    second = client.get(
        "/v1/conversations", params={"limit": 2, "after_id": first["next_cursor"]}
    ).json()
    assert [item["title"] for item in second["items"]] == ["c3"]
    assert second["has_more"] is False
    assert second["next_cursor"] is None


def _boom_commit(*args: Any, **kwargs: Any) -> Any:
    """模拟「提交那一刻失败」：磁盘满 / 连接被掐 / 唯一约束冲突"""
    raise RuntimeError("模拟提交失败")


def test_create_does_not_report_success_before_commit(client: TestClient, db_path: Path) -> None:
    """回归 #54：提交失败时绝不能已经回过 201 —— 客户端会以为存住了"""
    # 用 client fixture 只为它的清表副作用（下面的断言依赖「库里没有这一行」）
    with patch.object(AsyncSession, "commit", _boom_commit):
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            r = raw.post("/v1/conversations", json={"title": "不该存在"})

    assert r.status_code >= 500, f"提交失败却回了 {r.status_code}（#54 复现）"
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE title = ?", ("不该存在",)
        ).fetchone()[0]
    finally:
        conn.close()
    assert rows == 0, "提交失败后库里不应有这一行"


def test_update_does_not_report_success_before_commit(client: TestClient, db_path: Path) -> None:
    """PATCH 同理：提交失败不能回 200"""
    created = client.post("/v1/conversations", json={"title": "原始标题"}).json()

    with patch.object(AsyncSession, "commit", _boom_commit):
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            r = raw.patch(f"/v1/conversations/{created['id']}", json={"title": "改过的标题"})

    assert r.status_code >= 500, f"提交失败却回了 {r.status_code}（#54 复现）"
    conn = sqlite3.connect(str(db_path))
    try:
        title = conn.execute(
            "SELECT title FROM conversations WHERE id = ?", (created["id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert title == "原始标题", "提交失败后标题不应被改掉"


def test_delete_does_not_report_success_before_commit(client: TestClient, db_path: Path) -> None:
    """DELETE 同理：提交失败不能回 204"""
    created = client.post("/v1/conversations", json={"title": "别删我"}).json()

    with patch.object(AsyncSession, "commit", _boom_commit):
        with TestClient(app, headers=AUTH_HEADERS, raise_server_exceptions=False) as raw:
            r = raw.delete(f"/v1/conversations/{created['id']}")

    assert r.status_code >= 500, f"提交失败却回了 {r.status_code}（#54 复现）"
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE id = ?", (created["id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert rows == 1, "提交失败后这一行不应被删掉"
