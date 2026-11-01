from fastapi.testclient import TestClient


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
