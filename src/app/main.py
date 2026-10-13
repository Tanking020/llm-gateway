"""
程序入口：把 config / schemas 串起来的 "组合层"

职责边界（重要）：
    定义配置 -> config.py
    定义数据形状 -> schemas.py
    决定执行流程 -> 本文件
"""

import asyncio
import sys

import httpx

from app.config import settings  # 直接用同一个 settings 单例，不在别处再 Setting() 一遍
from app.schemas import ChatRequest, ChatResponse, Message


def build_demo_request() -> ChatRequest:
    """
    造一个假请求用于演示：离线、不联网、不花钱

    可测试、将来可替换、职责单一
    """
    return ChatRequest(
        # 模型名从配置读：换供应商只改 .env，这里不动
        model=settings.llm_model,
        messages=[
            # role 是聊天类发模型 API 的通用约定，指这条消息由谁说的
            # system = 系统/开发者指令（人设、规则、格式要求、拒答边界）；
            # user = 用户这一轮说的话；assistant = 模型之前已经回答过的话
            Message(role="system", content="你是一个简洁的中文助手"),
            Message(role="user", content="用一句话解释什么是 FastAPI"),
        ],
    )


def echo(request: ChatRequest) -> ChatResponse:
    """占位实现：把最后一条消息原样回显（真实的模型调用留到阶段 1）"""
    last = request.messages[-1]
    # 客户端没指定模型时（None），回落到服务端配置的默认模型
    return ChatResponse(content=last.content, model=request.model or settings.llm_model)


def create_client() -> httpx.AsyncClient:
    """
    按配置造一个 HTTP 客户端
    一处配置（以后加代理、重试、日志，只改这四行）、可替换、职责单一
    用的时候从全局配置 settings 里面拿（依赖注入）
    """
    return httpx.AsyncClient(
        base_url=settings.llm_base_url,  # 客户端地址前缀
        timeout=settings.request_timeout,
        # Bearer sk-xxxxxxxx 前者指【持票人】，后者是密钥【凭证】
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},  # 客户端默认请求头
    )


async def fetch_model_ids(client: httpx.AsyncClient) -> list[str]:
    """套上游可用模型。client 由调用方传入（依赖注入），测试时可换成假的"""
    response = await client.get("/models")
    response.raise_for_status()
    payload: dict[str, list[dict[str, object]]] = response.json()
    return [str(item["id"]) for item in payload["data"]]


async def main(argv: list[str]) -> int:
    """异步入口。argv[0] 是程序名，argv[1] 起才是用户输入的参数"""
    if len(argv) > 1 and argv[1] == "ping":
        # llm_api_key = str | None 允许不填，此时为 None
        # 它不会报错，而是会拼出一个看起来像真的、其实是垃圾的头：Authorization: Bearer None
        # 结果是拿着假凭证去请求，服务端只能回 401，而报错信息会说 "认证失败"
        # 容易误导认为是密钥错了，但其实根本是"忘了配密钥"
        # 所以这句检查必须放在造客户端之前
        if not settings.llm_api_key:  # 先检查有没有
            print("未配置 LLM_API_KEY，跳过网络检查")
            return 1
        async with create_client() as client:  # 再动手造
            model_ids = await fetch_model_ids(client)
        print(f"可用模型 {len(model_ids)} 个：{', '.join(model_ids[:5])}")
        return 0

    request = build_demo_request()
    response = echo(request)

    print(f"应用={settings.app_name} 环境={settings.app_env} 调试={settings.debug}")
    print(f"收到 {len(request.messages)} 条消息, 模型={request.model}")
    print(f"响应内容：{response.content}")
    return 0


def cli() -> None:
    """命令行入口：把控制权交给 asyncio.run"""
    raise SystemExit(asyncio.run(main(sys.argv)))


if __name__ == "__main__":
    cli()
