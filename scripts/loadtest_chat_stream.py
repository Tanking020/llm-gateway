"""容量探针（13f / #76）：并发打 SSE，量「首帧延迟 / 总耗时 / 状态码分布」，并给出 PASS/FAIL

为什么自己写而不装 locust/k6：
  ① 关键指标是【首帧延迟】（TTFB）而不是总时长 —— locust 的 requests 栈要另写流式逻辑才量得到
  ② 我们需要「断言容量边界」而不只是报表：c ≤ 闸门容量全 200、c 远超容量必须出现 503
  ③ 它要能顺手读 `/metrics` 的 `db_pool_checked_out`，与客户端视角对账

【注意】：必须打【真 TCP】+ 真 uvicorn —— TestClient 走 ASGI 直连，客户端不读也不产生背压，
    池占用与并发行为都测不出来（本项目已有此结论）。

用法（配合 scripts/fake_upstream.py，避免打真上游花钱）：
    uv run python scripts/loadtest_chat_stream.py --key sk_xxx --concurrency 1,4,8,16,32
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field

import httpx

BODY = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 64}


@dataclass
class Hit:
    """一次请求的结果"""

    status: int = 0
    ttfb: float | None = None
    total: float = 0.0
    frames: int = 0
    error: str = ""


@dataclass
class Row:
    """一个并发档位的汇总"""

    concurrency: int
    codes: dict[str, int] = field(default_factory=dict)
    ttfb: list[float] = field(default_factory=list)
    total: list[float] = field(default_factory=list)
    walls: list[float] = field(default_factory=list)
    peak_pool: int = 0

    @property
    def ok(self) -> int:
        return self.codes.get("200", 0)

    @property
    def requests(self) -> int:
        return sum(self.codes.values())


async def _one(client: httpx.AsyncClient, base: str, key: str, out: list[Hit]) -> None:
    """发一条流式请求：记录首帧时刻、总耗时、状态码、帧数"""
    hit = Hit()
    start = time.perf_counter()
    first: float | None = None
    try:
        async with client.stream(
            "POST", f"{base}/v1/chat/stream", json=BODY, headers={"X-API-Key": key}, timeout=120
        ) as resp:
            hit.status = resp.status_code
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    if first is None:
                        first = time.perf_counter() - start
                    hit.frames += 1
    except httpx.HTTPError as exc:
        hit.error = type(exc).__name__
        out.append(hit)
        return
    hit.ttfb = first
    hit.total = time.perf_counter() - start
    out.append(hit)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


async def _sample_pool(client: httpx.AsyncClient, base: str) -> int:
    """压测进行中反复采样池占用，返回峰值

    【注意】：抓的是 app 直连端口的 `/metrics`（nginx 那边是 404）
    """
    peak = 0
    for _ in range(40):
        try:
            text = (await client.get(f"{base}/metrics", timeout=5)).text
        except httpx.HTTPError:
            return peak
        for line in text.splitlines():
            if line.startswith("db_pool_checked_out "):
                peak = max(peak, int(float(line.split()[1])))
        await asyncio.sleep(0.02)
    return peak


async def run(base: str, key: str, concurrency: int, rounds: int) -> Row:
    row = Row(concurrency=concurrency)
    limits = httpx.Limits(
        max_connections=concurrency + 8, max_keepalive_connections=concurrency + 8
    )
    async with httpx.AsyncClient(limits=limits) as client:
        for _ in range(rounds):
            hits: list[Hit] = []
            sampler = asyncio.create_task(_sample_pool(client, base))
            start = time.perf_counter()
            await asyncio.gather(*(_one(client, base, key, hits) for _ in range(concurrency)))
            row.walls.append(time.perf_counter() - start)
            row.peak_pool = max(row.peak_pool, await sampler)
            for hit in hits:
                code = hit.error or str(hit.status)
                row.codes[code] = row.codes.get(code, 0) + 1
                if hit.status == 200 and hit.ttfb is not None:
                    row.ttfb.append(hit.ttfb)
                    row.total.append(hit.total)
    return row


def _verdict(rows: list[Row], gate: int) -> list[str]:
    """容量判据（可失败）：低并发必须全成功；远超容量必须出现 503"""
    problems: list[str] = []
    for row in rows:
        if row.concurrency <= gate and row.ok != row.requests:
            problems.append(f"c={row.concurrency} ≤ 闸门 {gate}，却出现了非 200：{row.codes}")
        if row.concurrency >= gate * 4 and "503" not in row.codes:
            problems.append(
                f"c={row.concurrency} ≥ 4×闸门 {gate}，却没有 503 —— 闸门没生效或排队超时太宽"
            )
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser(description="SSE 容量探针（13f）")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="app 直连地址")
    parser.add_argument("--key", required=True, help="X-API-Key 明文")
    parser.add_argument("--concurrency", default="1,4,8,16,32", help="逗号分隔的并发档位")
    parser.add_argument("--rounds", type=int, default=2, help="每档重复几轮")
    parser.add_argument(
        "--gate", type=int, default=4, help="预期闸门（max_concurrent_upstream_calls）"
    )
    args = parser.parse_args()

    rows: list[Row] = []
    for raw in args.concurrency.split(","):
        row = await run(args.base, args.key, int(raw), args.rounds)
        rows.append(row)
        wall = sum(row.walls) / len(row.walls) if row.walls else 0.0
        print(
            f"c={row.concurrency:<3} codes={row.codes} "
            f"ttfb p50={_pct(row.ttfb, 50) * 1000:6.0f}ms p95={_pct(row.ttfb, 95) * 1000:6.0f}ms "
            f"total p95={_pct(row.total, 95) * 1000:6.0f}ms "
            f"wall={wall:.2f}s pool_peak={row.peak_pool}"
        )

    problems = _verdict(rows, args.gate)
    print()
    if problems:
        for problem in problems:
            print("FAIL:", problem)
        return 1
    print("PASS: 低并发全成功、高并发出现 503（闸门生效）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
