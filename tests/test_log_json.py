"""日志格式层：每行必须能被机器解析（13e-2，决策 48）

为什么起子进程：`configure_logging()` 改的是【全局】logging 配置 ——
在进程内调用会污染同一 pytest 会话里其它用例的日志行为。
"""

import json
import logging
import subprocess
import sys

from app.logging_setup import JsonFormatter

_EMIT_SCRIPT = """
from app.logging_setup import configure_logging
import logging

configure_logging()
lg = logging.getLogger("app.test")
lg.info("中文 %s", "带换行\\n和引号\\"")
lg.info("request", extra={"client": "203.0.113.7", "status": 200})
try:
    1 / 0
except ZeroDivisionError:
    lg.exception("炸了")
"""


def test_every_emitted_line_is_one_json_object() -> None:
    """回归：真实进程输出里，每一行都要能 json.loads（含中文与 traceback）"""
    result = subprocess.run(
        [sys.executable, "-c", _EMIT_SCRIPT],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 3, f"应当 3 行（一条日志一行），实际 {len(lines)} 行：{lines}"
    for line in lines:
        payload = json.loads(line)
        assert set(payload) >= {"ts", "level", "logger", "msg"}
    assert json.loads(lines[1])["client"] == "203.0.113.7"
    assert "Traceback" in json.loads(lines[2])["exc"]


def test_traceback_stays_on_one_line_and_extra_is_merged() -> None:
    """回归：traceback 不能把一条日志切成多行；extra 字段不能被 formatter 吃掉"""
    formatter = JsonFormatter()
    record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "炸了", (), None)
    record.client = "203.0.113.7"
    record.status = 500
    try:
        raise ValueError("boom\n第二行")
    except ValueError:
        record.exc_info = sys.exc_info()

    rendered = formatter.format(record)
    # 【注意】：真实换行会把一条日志切成多条 —— json.dumps 必须把它转义成 \n
    assert "\n" not in rendered, "traceback 里还有真实换行 → 会被切成多行日志"
    payload = json.loads(rendered)
    assert payload["client"] == "203.0.113.7"
    assert payload["status"] == 500
    assert "Traceback" in payload["exc"]
