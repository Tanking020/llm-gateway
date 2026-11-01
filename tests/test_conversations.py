"""对话接口的 HTTP 契约测试：断言状态码 / 响应形状 / 落库效果，不断言 SQL 细节"""

from typing import cast

import pytest
from fastapi.testclient import TestClient


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
