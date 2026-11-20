"""指标最小集（13e-3 / 决策 50）：只做「出事时能回答为什么」的那几个

【注意】：都是【进程内】计数 —— 多副本 / 多 worker 时每个进程各一份，
    抓取到的只是「被路由到的那一个进程」的账（与 #44 / 决策 42 同型）
"""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# 请求总数：按 method / path / status 三标签。status 是字符串，5xx 用 "5.." 正则选
# 【注意】：path 必须是【路由模板】（/v1/conversations/{conv_id}），不是真实 URL ——
#   否则 id 不同就会炸出无数时间序列
REQUESTS = Counter("http_requests_total", "HTTP 请求数", ["method", "path", "status"])

# 【注意】：只统计【非流式】路径 —— 流式请求的总时长由 upstream_total_timeout（120s）决定，
#   它衡量的是「模型写了多久」而不是「我们慢不慢」，混进来会让 p99 永久趴在 120s
DURATION = Histogram(
    "http_request_duration_seconds",
    "非流式请求耗时",
    ["path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
)

# 错误码计数：出故障时「哪个 code 涨了」比「5xx 涨了」有用得多
# 【注意】：只覆盖走 _error_response 的错误 —— 流内的 STREAM_* 帧已回 200，不经过那里
ERRORS = Counter("app_errors_total", "错误响应数", ["code", "status"])

# token 吞吐：方向分开（prompt 决定成本，completion 决定速度）
TOKENS = Counter("llm_tokens_total", "上游 token 数", ["direction"])

# 数据库连接池占用：在 /metrics 被抓取的那一刻采样（Gauge 没有累加语义的负担）
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "已借出的数据库连接数")


def sample_pool_checked_out(checked_out: int) -> None:
    """把当前池占用写进 Gauge —— 由 /metrics 路由在生成输出之前调用"""
    DB_POOL_CHECKED_OUT.set(checked_out)


def render() -> tuple[bytes, str]:
    """生成 Prometheus 抓取输出：返回 (body, content-type)

    【注意】：本模块是【唯一】import prometheus_client 的地方（同 llm_client.py 之于 httpx）
    """
    return generate_latest(), CONTENT_TYPE_LATEST
