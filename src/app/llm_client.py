"""
上游 LLM 的 HTTP 客户端：构造参数只在这里写一份

为什么单独一个文件（而不是留在 main.py 或 deps.py）:
    main.py（CLI）和 api/deps.py（常驻服务）都要造客户端：
    同一套 base_url / timeout / headers 写两遍 -> 改一处忘另一处，迟早不一致
    这里只回答【怎么造】，不回答【谁负责关闭】：
        CLI 用 async with 自己管；服务用 yield 依赖交给框架管
"""

import httpx

from app.config import settings


def create_llm_client() -> httpx.AsyncClient:
    """按配置造一个上游 LLM 的 HTTP 客户端。【关闭由调用方负责】"""
    return httpx.AsyncClient(
        base_url=settings.llm_base_url,
        timeout=settings.request_timeout,
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
    )
