"""指标层（13e-3 / 决策 50）：只钉「会不会算错」和「会不会漏报」

为什么不测具体数值：Prometheus counter 是【进程内累加、永不归零】的，
    拿它和"期望 1"比会在其它用例先打过同一个路径时随机失败（假红）。
    所以这里只钉【形状与标签】，数值留给真栈验收。
"""

from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_llm_client
from fakes import FakeLlm

# 流式请求的最小合法 body（最后一条必须是 user）
_CHAT_BODY = {"messages": [{"role": "user", "content": "hi"}]}

_CORE_SERIES = (
    "http_requests_total",
    "http_request_duration_seconds_bucket",
    "app_errors_total",
    "llm_tokens_total",
    "db_pool_checked_out",
)


def test_metrics_is_not_in_openapi_schema(client: TestClient) -> None:
    """回归：运维端点不属于对外契约，不能出现在 /openapi.json 里"""
    resp = client.get("/openapi.json")
    if resp.status_code != 200:  # prod 下文档路由是关的
        return
    assert "/metrics" not in resp.json().get("paths", {})


def test_metrics_output_has_core_series(client: TestClient) -> None:
    """回归：抓取端点必须产出 Prometheus 文本格式，且核心指标都在"""
    client.get("/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    for name in _CORE_SERIES:
        assert name in resp.text, f"缺指标 {name}"


def test_request_counter_uses_route_template_not_raw_path(client: TestClient) -> None:
    """回归：path 标签必须是路由模板 —— 否则每个 id 各建一条时间序列（卡片式爆炸）"""
    client.post("/v1/conversations", json={"title": "a"})
    client.get("/v1/conversations/1")
    body = client.get("/metrics").text
    assert 'path="/v1/conversations/{conv_id}"' in body
    assert 'path="/v1/conversations/1"' not in body


def test_error_counter_counts_every_code(anon_client: TestClient) -> None:
    """回归：错误计数走 _error_response 单一出口 —— 401 这种"不经过路由"的也要记上

    【注意】：必须用 anon_client —— client fixture 自带 X-API-Key，打出来会是 200
    """
    anon_client.get("/v1/conversations")  # 无 key → 401
    body = anon_client.get("/metrics").text
    assert 'app_errors_total{code="UNAUTHORIZED",status="401"}' in body


def test_stream_requests_are_not_in_latency_histogram(client: TestClient) -> None:
    """回归：流式不记总时长 —— 它由上游预算决定，混进来会让 p99 永久趴在 120s

    【注意】：必须真打一次流式请求 —— 否则"没有该序列"在变异（流式也记时长）下仍然成立，
        守卫就是假绿（📎 变异验证时踩到）
    """
    fake = FakeLlm()
    app.dependency_overrides[get_llm_client] = lambda: fake
    try:
        client.post("/v1/chat/stream", json=_CHAT_BODY)
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
    body = client.get("/metrics").text
    assert 'http_request_duration_seconds_count{path="/v1/chat/stream"}' not in body
    # 反向证据：非流式路径【确实】记了时长 —— 否则上面那条断言可能只是因为整个直方图是空的
    assert 'http_request_duration_seconds_count{path="/v1/conversations"}' in body


def test_probe_paths_are_not_metered(client: TestClient) -> None:
    """回归：探针与抓取端点不计量 —— 它们频率远超真实流量，会把 5xx 比例的分母撑大"""
    client.get("/health")
    client.get("/health/ready")
    client.get("/metrics")
    body = client.get("/metrics").text
    for path in ("/health", "/health/ready", "/metrics"):
        assert f'http_requests_total{{method="GET",path="{path}"' not in body, f"{path} 不该被计量"
