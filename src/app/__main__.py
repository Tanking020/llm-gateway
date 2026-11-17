"""启动入口：uv run python -m app

settings.host / settings.port 只有走这里才生效，命令行 uvicorn 会绕过它们

【注意】：第一个参数必须是【import 字符串】，不能传 app 对象：
    reload / workers 要把「从哪 import」交给子进程，传对象会让 reload 静默失效
"""

import uvicorn

from app.config import settings
from app.logging_setup import configure_logging


def main() -> None:
    # reloader 父进程不会 import app.api.app，所以这里也要配一次（force=True，重复调用无害）
    configure_logging()
    uvicorn.run(
        "app.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        # 【注意】：必须 None。默认 uvicorn 会装它自己那套格式，日志就变成两种样式
        log_config=None,
        # 【注意】：窗口内跑完的流正常收尾；超窗口的流被明确切断（连接关闭、无 [DONE]）
        #   不传就是 None = 无限等 —— 一条慢流就能把 docker stop 挂住
        timeout_graceful_shutdown=settings.graceful_shutdown_timeout,
    )


if __name__ == "__main__":
    main()
