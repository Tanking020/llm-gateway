"""每用户速率限制：令牌桶（进程内）

为什么是「桶」而不是「每分钟计数」：
    固定窗口会在边界放行两倍流量（59 秒 60 个 + 61 秒再 60 个）；桶按时间连续补充，
    既允许短时突发，又保证长期速率 —— 客户端也不会在整分钟边界上被突然掐断。
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

# 桶数量上限：超过就顺手清掉「已经补满」的桶（满桶不携带状态，删掉不影响判断）
_MAX_BUCKETS = 10_000


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """按 key（本项目是 user.id）分桶的令牌桶

    【注意】：clock 默认 time.monotonic 而不是墙钟 —— 进程内只关心「过了多久」，
        不关心「现在几点」；墙钟会被 NTP 校时跳变，往回跳一次就白送一大桶令牌。
        （若将来把桶搬到 Redis 做多实例共享，那边必须换墙钟：要对齐的是【跨进程】时间）
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        # 【注意】：clock 可注入是为了让测试不 sleep —— 假时钟直接"快进"即可
        self._clock = clock
        self._buckets: dict[int, _Bucket] = {}

    def acquire(self, key: int, *, capacity: int, per_minute: int) -> float:
        """尝试取 1 个令牌。成功返回 0.0；失败返回「建议等多少秒」"""
        now = self._clock()
        refill_per_second = per_minute / 60.0

        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= _MAX_BUCKETS:
                self._drop_full_buckets(capacity)
            # 新用户一上来就是满桶：允许他最初的突发
            bucket = _Bucket(tokens=float(capacity), updated=now)
            self._buckets[key] = bucket
        else:
            # 【注意】：max(0.0, …) 兜住「时钟倒退」（假时钟用错、或将来换成墙钟）：
            #   宁可少补，也不要凭空多给令牌
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(float(capacity), bucket.tokens + elapsed * refill_per_second)
            bucket.updated = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return 0.0
        # per_minute 由配置校验保证 >= 1，这里不会除 0
        return (1.0 - bucket.tokens) / refill_per_second

    def retry_after_seconds(self, wait: float) -> int:
        """把「还要等几秒」变成 Retry-After 的整数秒

        【注意】：向上取整且至少 1 —— 给 0 等于让客户端立刻重试，正好是限流要防的事
        """
        return max(1, math.ceil(wait))

    def _drop_full_buckets(self, capacity: int) -> None:
        """清掉已补满的桶：它们是「和从没来过一样」的状态，删掉不影响任何判断"""
        for key in [k for k, b in self._buckets.items() if b.tokens >= capacity]:
            del self._buckets[key]
