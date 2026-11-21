"""优雅停机验收探针：起一个真服务子进程，在流进行中投递真信号，量窗口是否生效。

用法：uv run python scripts/probe_graceful_shutdown.py
升级 uvicorn / 改停机逻辑 / 发版前跑一次。不进 CI（真端口 + 真信号 + 真 DB，见决策 39）。
"""

import argparse
import asyncio
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DRIP_INTERVAL = 0.2


def free_port() -> int:
    """挑一个当前空闲的端口，避免撞上正在跑的开发服务"""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(port: int, grace: int) -> None:
    """子进程角色：把 app 装好假上游，然后按生产同一条路径 serve"""
    sys.path.insert(0, str(ROOT / "src"))

    import uvicorn

    from app.api.app import app
    from app.api.deps import get_llm_client

    class DripStream:
        """只实现路由会调用的两个方法；故意不继承 LlmChatStream（父类 __init__ 要真响应对象）"""

        async def aiter_chunks(self) -> AsyncIterator[dict[str, Any]]:
            while True:
                await asyncio.sleep(DRIP_INTERVAL)
                yield {"choices": [{"index": 0, "delta": {"content": "滴"}}]}

        async def aclose(self) -> None:
            return None

    class DripLlm:
        async def open_chat_stream(self, body: dict[str, object]) -> DripStream:
            return DripStream()

    app.dependency_overrides[get_llm_client] = DripLlm
    print(f"[子进程 {os.getpid()}] serve 开始，窗口={grace}s", flush=True)
    uvicorn.run(
        "app.api.app:app",
        host="127.0.0.1",
        port=port,
        log_config=None,
        timeout_graceful_shutdown=grace,
    )
    print(f"[子进程 {os.getpid()}] serve 返回（进程即将按信号退出）", flush=True)


def wait_ready(url: str, proc: subprocess.Popen[bytes]) -> bool:
    """轮询 /health 直到可连；子进程先死了立刻返回 False"""
    import httpx

    deadline = time.perf_counter() + 20.0
    while time.perf_counter() < deadline:
        if proc.poll() is not None:
            return False
        try:
            httpx.get(url, timeout=0.5)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def tail(path: Path, lines: int = 15) -> str:
    """失败时把子进程日志末尾打出来 —— 否则只知道 FAIL 不知道为什么"""
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "（读不到子进程日志）"


def drive(port: int, grace: int, hold: float) -> int:
    """父进程角色：建库 → 起子进程 → 开流 → 中途投信号 → 收尸 → 判定"""
    workdir = Path(tempfile.mkdtemp(prefix="probe_graceful_"))
    # 【注意】：每次跑都会留下一个约 60 KB 的临时库 + 子进程日志；不清会一直堆在 %TEMP%（#99）
    try:
        return _drive(workdir, port, grace, hold)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _drive(workdir: Path, port: int, grace: int, hold: float) -> int:
    """真正的流程 —— 拆出来只为让外面那个 finally 覆盖到所有 return 路径"""
    import httpx

    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ)
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{(workdir / 'probe.db').as_posix()}",
            "APP_ENV": "dev",
            "DEBUG": "false",
            "PROBE_PORT": str(port),
            "PROBE_GRACE": str(grace),
            # 【注意】：必须放大上游总时长，否则 13c-3 的 120s 会抢在停机窗口之前掐断流，
            #   就分不清是谁掐的 —— 探针要让窗口成为唯一裁判
            "UPSTREAM_TOTAL_TIMEOUT": "600",
        }
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=True,
    )

    # 【注意】：13d-2 起所有 /v1/* 都要 X-API-Key，而子进程用的是空临时库 ——
    #   这里必须现签一把，否则第一步就 401（#97 / 坑 K100）
    key_result = subprocess.run(
        [sys.executable, "-m", "app.keys", "create", "--user", "probe", "--label", "graceful"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    )
    api_key = next(
        line.strip() for line in key_result.stdout.splitlines() if line.strip().startswith("sk_")
    )

    log_path = workdir / "child.log"
    # 【注意】：必须独立进程组，否则 CTRL_BREAK 会打到我们自己所在的组（Linux 上该常量为 0）
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    print(f"[父进程 {os.getpid()}] 子进程 pid={proc.pid}", flush=True)
    if not wait_ready(f"{base}/health", proc):
        if proc.poll() is None:
            proc.kill()
        print("!! 子进程没起来，日志末尾：\n" + tail(log_path), flush=True)
        return 1

    start = time.perf_counter()
    frames = 0
    last = ""
    signaled_at: float | None = None
    status = 0
    outcome = ""
    try:
        with httpx.Client(timeout=30.0) as client:
            body = {"messages": [{"role": "user", "content": "hi"}]}
            with client.stream(
                "POST",
                f"{base}/v1/chat/stream",
                json=body,
                headers={"X-API-Key": api_key},
            ) as resp:
                status = resp.status_code
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    frames += 1
                    last = line[6:]
                    # 【注意】：客户端自己的死线。窗口没生效时服务端永不关，客户端不能陪它吊死
                    if time.perf_counter() - start > hold + grace + 5.0:
                        print("[父进程] 客户端主动停止读取（已超窗口+5s）", flush=True)
                        break
                    if signaled_at is None and time.perf_counter() - start >= hold:
                        if os.name == "nt":
                            # 【注意】：该常量只在 Windows 存在，写属性名会让 Linux 上的 mypy 报错
                            os.kill(proc.pid, getattr(signal, "CTRL_BREAK_EVENT"))  # noqa: B009
                        else:
                            proc.send_signal(signal.SIGTERM)
                        signaled_at = time.perf_counter()
                        print(f"[父进程] {signaled_at - start:.2f}s 已投递信号", flush=True)
        outcome = "客户端读到流自然结束"
    except Exception as exc:
        outcome = f"客户端异常 {type(exc).__name__}（流被切断时属正常）"

    timed_out = False
    try:
        code = proc.wait(timeout=grace + 15.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = proc.wait(timeout=10.0)
        timed_out = True
    elapsed = time.perf_counter() - start
    cut = (time.perf_counter() - signaled_at) if signaled_at else -1.0

    print(f"[父进程] 响应码={status} 帧数={frames} 末帧={last!r}")
    print(f"[父进程] 客户端结局={outcome}")
    print(f"[父进程] 总耗时={elapsed:.2f}s 信号后={cut:.2f}s 子进程退出码={code}")

    ok = True
    if status != 200:
        print(f"!! 响应码 {status}，不是 200 —— 日志末尾：\n" + tail(log_path))
        ok = False
    if frames == 0:
        print("!! 没收到任何帧 —— 流没起来，探针无效")
        ok = False
    if last == "[DONE]":
        print("!! 信号之后流仍正常收尾（[DONE]）—— 窗口没生效，或别的死线先掐断了它")
        ok = False
    if timed_out:
        print(f"!! 子进程在 {grace + 15.0:.0f}s 内没有退出 —— 优雅窗口可能没生效（None = 无限等）")
        ok = False
    if signaled_at is None:
        print("!! 没有等到发信号的机会 —— hold 设太大了")
        ok = False
    elif not (grace - 0.5 <= cut <= grace + 3.0):
        print(f"!! 信号后 {cut:.2f}s 才断开，超出 {grace}s 窗口预期")
        ok = False
    print("==> 结论：" + ("PASS 窗口生效（在途流按窗口被掐断）" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="优雅停机验收探针")
    parser.add_argument(
        "--grace", type=int, default=2, help="timeout_graceful_shutdown 秒数（默认 2）"
    )
    parser.add_argument("--hold", type=float, default=1.0, help="流跑多久后投递信号（默认 1.0s）")
    parser.add_argument("--port", type=int, default=0, help="0 = 自动挑空闲端口")
    parser.add_argument("--serve", action="store_true", help="（内部）以服务子进程身份运行")
    args = parser.parse_args()

    if args.serve:
        serve(int(os.environ["PROBE_PORT"]), int(os.environ["PROBE_GRACE"]))
        return 0
    return drive(args.port or free_port(), args.grace, args.hold)


if __name__ == "__main__":
    sys.exit(main())
