"""鉴权与归属（13d-2）：没有 / 错的 key 一律 401；别人的对话一律 404"""

import sqlite3
from pathlib import Path

import pytest
from conftest import OTHER_API_KEY, TEST_API_KEY
from fastapi.testclient import TestClient

REQ = {"messages": [{"role": "user", "content": "hi"}]}


def _revoke(db_path: Path, user_id: int) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,)
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/v1/conversations"),
        ("post", "/v1/conversations"),
        ("get", "/v1/conversations/1"),
        ("post", "/v1/chat"),
        ("post", "/v1/chat/stream"),
        ("get", "/v1/upstream/models"),
    ],
)
def test_business_routes_require_key(anon_client: TestClient, method: str, path: str) -> None:
    """没有任何凭据时，业务端点全部 401（而不是"能调但没数据"）"""
    body = {"title": "x"} if path == "/v1/conversations" and method == "post" else REQ
    resp = anon_client.request(method.upper(), path, json=body)
    assert resp.status_code == 401, f"{method.upper()} {path} → {resp.status_code}"
    payload = resp.json()["error"]
    assert payload["code"] == "UNAUTHORIZED"
    # RFC 9110：401 必须带 WWW-Authenticate，否则客户端不知道该用哪种凭据
    assert resp.headers["www-authenticate"] == "ApiKey"
    assert resp.headers["x-request-id"] == payload["request_id"]


def test_public_routes_need_no_key(anon_client: TestClient) -> None:
    """健康检查与本地静态模型表不能要鉴权 —— 否则负载均衡和探测机器人全挂"""
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/v1/models").status_code == 200


def test_invalid_key_is_401(anon_client: TestClient) -> None:
    resp = anon_client.get("/v1/conversations", headers={"X-API-Key": "sk-nope"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_revoked_key_is_401(
    anon_client: TestClient, other_client: TestClient, db_path: Path
) -> None:
    """撤销 = revoked_at 非空：同一把 key 立刻失效（不删行，留审计）"""
    assert other_client.get("/v1/conversations").status_code == 200
    _revoke(db_path, user_id=2)
    assert other_client.get("/v1/conversations").status_code == 401


def test_cannot_read_others_conversation(client: TestClient, other_client: TestClient) -> None:
    """A 建的对话，B 连"存在"都不该知道 —— 越权与不存在共用 404"""
    conv_id = client.post("/v1/conversations", json={"title": "alice 的"}).json()["id"]

    resp = other_client.get(f"/v1/conversations/{conv_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_others_conversations_do_not_show_in_list(
    client: TestClient, other_client: TestClient
) -> None:
    """列表与 total 都必须按 owner 过滤，否则"条数"会泄露别人的数据量"""
    client.post("/v1/conversations", json={"title": "alice 的"})

    page = other_client.get("/v1/conversations").json()
    assert page["items"] == []
    assert page["total"] == 0


def test_cannot_modify_or_delete_others_conversation(
    client: TestClient, other_client: TestClient
) -> None:
    conv_id = client.post("/v1/conversations", json={"title": "原始"}).json()["id"]

    assert (
        other_client.patch(f"/v1/conversations/{conv_id}", json={"title": "改"}).status_code == 404
    )
    assert other_client.delete(f"/v1/conversations/{conv_id}").status_code == 404
    # 确认真的没被改动
    assert client.get(f"/v1/conversations/{conv_id}").json()["title"] == "原始"


def test_chat_with_others_conversation_id_is_404(
    client: TestClient, other_client: TestClient
) -> None:
    """聊天也会校验归属 —— 否则可以用别人的对话 id 把账单挂到别人头上"""
    conv_id = client.post("/v1/conversations", json={"title": "alice 的"}).json()["id"]

    resp = other_client.post("/v1/chat", json={**REQ, "conversation_id": conv_id})
    assert resp.status_code == 404


def test_key_is_stored_as_sha256_not_plaintext(db_path: Path, client: TestClient) -> None:
    """库里只有 hash：即使备份泄露，也拿不到能直接用的凭据"""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT key_hash FROM api_keys").fetchall()
    finally:
        conn.close()
    stored = {row[0] for row in rows}
    assert TEST_API_KEY not in stored
    assert OTHER_API_KEY not in stored
    assert all(len(value) == 64 for value in stored), stored
