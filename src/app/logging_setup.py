"""
日志配置；进程启动时执行一次

【注意】：不能用 logging.basicConfig，它只在 root 没有 handler 时才生效；
    第二次调用静默失效，所以这里我们用 dictConfig(force=True) 强制接管
    每次进程启动时候强制重启配置，确保使用我们设置的日志配置
"""

import json
import logging.config
from datetime import UTC, datetime
from typing import Any

# LogRecord 自带的属性名（+ 两个只在格式化阶段才存在的）—— extra 合并时要把它们排除，
#   否则每条日志都会多出 pathname / thread / process 这类噪声
_RESERVED_KEYS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    """一行一个 JSON 对象 —— 日志平台按字段过滤，而不是拿正则去抠字符串"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            # 【注意】：保留毫秒与 UTC 偏移，跨时区排查才不用换算
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 【注意】：logger.info(..., extra={...}) 的业务字段原样带出来，不做白名单
        for key, value in vars(record).items():
            if key not in _RESERVED_KEYS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            # 【注意】：json.dumps 会把换行转义掉 → traceback 仍是【一行】，不会被日志采集器切碎
            payload["exc"] = self.formatException(record.exc_info)
        # 【注意】：ensure_ascii=False 保留中文可读；代价是采集端与终端必须按 UTF-8 解码
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """整个进程只用这一套格式、一个 handler"""
    # 【注意】：dictConfig 的参数类型是 dict[str, Any]，不标注会被 mypy 判成 dict[str, object]
    config: dict[str, Any] = {
        "version": 1,
        # 【注意】：必须 False。默认 True 会禁用【下面 loggers 里没命名】的已有 logger，
        #   比如 app.errors —— 500 的 traceback 就靠它打出来
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonFormatter}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            # 清空 uvicorn 自带的 handler + propagate=True：交给下面同一个 handler 输出
            "uvicorn": {"handlers": [], "level": "INFO", "propagate": True},
            "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": True},
            # 访问日志关掉：中间件已经打了一行带 request_id 的
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
        },
        "root": {"handlers": ["console"], "level": "INFO"},
    }
    logging.config.dictConfig(config)
