"""启动入口：uv run python -m app

settings.host / settings.port 只有走这里才生效，命令行 uvicorn 会绕过它们

【注意】：第一个参数必须是【import 字符串】，不能传 app 对象：
    reload / workers 要把「从哪 import」交给子进程，传对象会让 reload 静默失效
"""

import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
