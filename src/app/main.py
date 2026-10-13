"""
程序入口：把 config / schemas 串起来的 "组合层"

职责边界（重要）：
    定义配置 -> config.py
    定义数据形状 -> schemas.py
    决定执行流程 -> 本文件
"""

import asyncio
import sys

from app.config import settings  # 直接用同一个 settings 单例，不在别处再 Setting() 一遍
from app.schemas import ChatRequest, ChatResponse, Message


def build_demo_request() -> ChatRequest:
    """
    造一个假请求用于演示：离线、不联网、不花钱

    可测试、将来可替换、职责单一
    """
    return ChatRequest(
        messages=[
            # role 是聊天类发模型 API 的通用约定，指这条消息由谁说的
            # system = 系统/开发者指令（人设、规则、格式要求、拒答边界）；
            # user = 用户这一轮说的话；assistant = 模型之前已经回答过的话
            Message(role="system", content="你是一个简洁的中文助手"),
            Message(role="user", content="用一句话解释什么是 FastAPI"),
        ]
    )


def echo(request: ChatRequest) -> ChatResponse:
    """占位实现：把最后一条消息原样回显（真实的模型调用留到阶段 1）"""
    last = request.messages[-1]
    return ChatResponse(content=last.content, model=request.model)


async def main(argv: list[str]) -> int:
    """异步入口(argv 现在用不上，0.28b的 ping 分支会用它)"""
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
