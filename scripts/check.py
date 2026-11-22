"""五道质量门的唯一入口（决策 63）

为什么需要它：同一串命令原本写在 CONTRIBUTING / README / RUNBOOK / PR 模板 / ci.yml 五处，
失效方式不是「有人写错」，而是「只改了一部分」—— 于是「CI 绿的」和「文档说该跑的」不是同一件事。
【注意】：门槛的命令与参数只在这个文件里定义，ci.yml 与文档只调用它。
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Gate:
    name: str
    args: list[str]
    title: str


# args 与「人手敲的命令」一字不差 —— 脚本不能成为只有它自己知道怎么跑的黑盒
GATES: list[Gate] = [
    Gate("format", ["ruff", "format", "--check", "."], "格式化检查（只读）"),
    Gate("lint", ["ruff", "check", "."], "lint（E/F/I/UP/B/TID）"),
    Gate("mypy", ["mypy", "."], "类型检查（strict）"),
    Gate("pyright", ["pyright"], "类型检查（对齐编辑器）"),
    Gate("test", ["pytest", "-q"], "回归测试"),
]


def _run(gate: Gate) -> int:
    cmd = ["uv", "run", *gate.args]
    started = time.perf_counter()
    done = subprocess.run(cmd, cwd=ROOT, check=False)
    spent = time.perf_counter() - started
    mark = "ok  " if done.returncode == 0 else f"FAIL({done.returncode})"
    print(f"  {mark} {spent:5.1f}s  {gate.name:8}{gate.title}", flush=True)
    return done.returncode


def main(argv: list[str]) -> int:
    if argv and argv[0] in {"-l", "--list"}:
        for gate in GATES:
            print(f"{gate.name:8}uv run {' '.join(gate.args)}")
        return 0

    selected = GATES
    if argv:
        known = {gate.name for gate in GATES}
        unknown = [name for name in argv if name not in known]
        if unknown:
            print(f"未知的门：{unknown}；可选：{sorted(known)}", file=sys.stderr)
            return 2
        selected = [gate for gate in GATES if gate.name in argv]

    print(f"质量门 {len(selected)} 道 | {ROOT}")
    for gate in selected:
        code = _run(gate)
        if code != 0:
            print(f"未通过：{gate.name}（uv run {' '.join(gate.args)}）", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
