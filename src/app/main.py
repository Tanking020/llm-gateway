"""
程序入口：把 config / schemas 串起来的 "组合层"

职责边界（重要）：
    定义配置 -> config.py
    定义数据形状 -> schemas.py
    决定执行流程 -> 本文件
"""

import asyncio
import sys

from app.config import settings # 直接用同一个 settings 单例，不在别处再 Setting() 一遍
from app.schemas import ChatRequest, ChatResponse, Message

def build_demo_request() -> ChatRequest:
    """造一个演示请求：离线、不联网、不花钱"""
    return ChatRequest(
        messages=[
            Message(role="system", content="你是一个简洁的中文助手"),
            Message(role="user", content="用一句话解释什么是 FastAPI"),
        ]
    )

def echo(request: ChatRequest)
