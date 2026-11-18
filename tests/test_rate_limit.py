"""每用户速率限制（13d-4）：桶数学 + 429 形状 + 桶按用户隔离 + 假时钟验证恢复"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.deps import get_settings
from app.config import Settings
from app.ratelimit import RateLimiter


class _FakeClock:
    """可手动快进的时钟：让「等一分钟」变成 0 秒"""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ============ 桶本身（不经过 HTTP） ============


def test_bucket_allows_burst_then_refuses() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(clock=clock)

    # 满桶 3 个：前三次全部放行
    for _ in range(3):
        assert limiter.acquire(1, capacity=3, per_minute=60) == 0.0
    # 第四次没有令牌了：返回「还要等多久」而不是 -1/异常
    wait = limiter.acquire(1, capacity=3, per_minute=60)
    assert wait > 0


def test_bucket_refills_over_time() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(clock=clock)

    for _ in range(3):
        limiter.acquire(1, capacity=3, per_minute=60)  # 60/min = 每秒 1 个
    assert limiter.acquire(1, capacity=3, per_minute=60) > 0

    clock.advance(1.0)  # 过 1 秒 → 补 1 个令牌
    assert limiter.acquire(1, capacity=3, per_minute=60) == 0.0


def test_bucket_does_not_exceed_capacity() -> None:
    """久不访问也只是补满，不会攒出「无限突发」"""
    clock = _FakeClock()
    limiter = RateLimiter(clock=clock)
    limiter.acquire(1, capacity=2, per_minute=60)

    clock.advance(3600)  # 一小时没来
    assert limiter.acquire(1, capacity=2, per_minute=60) == 0.0
    assert limiter.acquire(1, capacity=2, per_minute=60) == 0.0
    # 第三次就该没了 —— 说明这一小时只把它补到 2，而不是补到 3600
    assert limiter.acquire(1, capacity=2, per_minute=60) > 0


def test_bucket_is_isolated_per_key() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(clock=clock)
    for _ in range(2):
        assert limiter.acquire(1, capacity=2, per_minute=60) == 0.0
    assert limiter.acquire(1, capacity=2, per_minute=60) > 0
    # 另一个 key 不受影响：这就是「一个人刷爆不影响别人」
    assert limiter.acquire(2, capacity=2, per_minute=60) == 0.0


def test_retry_after_is_a_positive_integer_that_rounds_up() -> None:
    limiter = RateLimiter()
    assert limiter.retry_after_seconds(0.1) == 1  # 不足 1 秒也要给 1（给 0 = 叫客户端立刻重试）
    assert limiter.retry_after_seconds(1.2) == 2
    assert limiter.retry_after_seconds(0.0) == 1


# ============ 经过 HTTP（真依赖链） ============


@pytest.fixture
def tight_quota() -> Iterator[None]:
    """把配额压到 2：「第 3 个请求必须 429」才好在测试里稳定触发"""
    app.dependency_overrides[get_settings] = lambda: Settings(
        rate_limit_per_minute=1, rate_limit_burst=2
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_third_request_gets_429_with_retry_after(client: TestClient, tight_quota: None) -> None:
    assert client.get("/v1/conversations").status_code == 200
    assert client.get("/v1/conversations").status_code == 200

    response = client.get("/v1/conversations")
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    # RFC 9110：429 必须告诉客户端什么时候可以再来
    retry_after = int(response.headers["Retry-After"])
    assert retry_after >= 1
    assert response.headers["x-request-id"] == error["request_id"]


def test_quota_is_per_user_not_per_key(
    client: TestClient, other_client: TestClient, tight_quota: None
) -> None:
    """一个人被限流，另一个人照常 —— 否则一把 key 刷爆等于全站瘫痪"""
    for _ in range(3):
        client.get("/v1/conversations")  # 打满 alice 的桶

    assert other_client.get("/v1/conversations").status_code == 200


def test_quota_recovers_after_waiting(client: TestClient, tight_quota: None) -> None:
    """桶会随时间补满 —— 用假时钟快进，不靠 sleep（靠 sleep 的测试必然 flaky）"""
    clock = _FakeClock()
    app.state.rate_limiter = RateLimiter(clock=clock)

    for _ in range(2):
        assert client.get("/v1/conversations").status_code == 200
    assert client.get("/v1/conversations").status_code == 429

    clock.advance(60.0)  # 60 秒补 1 个（per_minute=1）
    assert client.get("/v1/conversations").status_code == 200


def test_rejected_requests_do_not_consume_someone_elses_quota(
    anon_client: TestClient, client: TestClient
) -> None:
    """没带 key 的请求连身份都没有 —— 它们不能消耗任何人的配额"""
    for _ in range(5):
        assert anon_client.get("/v1/conversations").status_code == 401

    assert client.get("/v1/conversations").status_code == 200
