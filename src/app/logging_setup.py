"""
日志配置；进程启动时执行一次

【注意】：不能用 logging.basicConfig，它只在 root 没有 handler 时才生效；
    第二次调用静默失效，所以这里我们用 dictConfig(force=True) 强制接管
    每次进程启动时候强制重启配置，确保使用我们设置的日志配置
"""

import logging.config
from typing import Any

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def configure_logging() -> None:
    """整个进程只用这一套格式、一个 handler"""
    # 【注意】：dictConfig 的参数类型是 dict[str, Any]，不标注会被 mypy 判成 dict[str, object]
    config: dict[str, Any] = {
        "version": 1,
        # 【注意】：必须 False。默认 True 会禁用【下面 loggers 里没命名】的已有 logger，
        #   比如 app.errors —— 500 的 traceback 就靠它打出来
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": _LOG_FORMAT}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
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
