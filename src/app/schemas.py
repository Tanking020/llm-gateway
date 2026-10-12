"""
数据契约：本服务【对外收发数据】的形状定义

为什么要单独一个文件：
  ① 入参和出参的形状属于"接口的一部分"，应该能一眼看全
  ② 阶段 1 的 FastAPI 会直接拿这些模型做请求校验和接口文档生成
  ③ 校验规则集中在这里，而不是散落在各处的 if 判断里
"""

# Literal：标准库 typing 里的类型，表示"只能是这几个值之一"
from typing import Literal

# BaseModel：pydantic 的【普通】数据模型
#   对比用过的 BaseSettings —— 后者是它的子类，
#   额外具备"从环境变量 / .env 读取"的能力；BaseModel 没有，
#   它只负责【校验和转换数据】

# Field：给【单个字段】加约束（范围、长度、默认值…）
from pydantic import BaseModel, Field


class Message(BaseModel):
    """对话中的一条消息"""

    # role 只能是这三个值之一。
    # 为什么用 Literal 而不是 str：拼错时【立刻报错】，
    # 而不是静默走进"谁都不匹配"的分支（与 config.py 的 app_env 同一个道理）
    role: Literal["system", "user", "assistant"]

    # 消息正文。str 类型；没有默认值 = 必填
    content: str


class ChatRequest(BaseModel):
    """客户端发来的聊天请求"""

    # 消息列表:
    # Flied(min_length=1) = 至少一条
    # 传空列表会被拦截（"一条消息都没有"的请求是无意义的）
    messages: list[Message] = Field(min_length=1)

    # 用哪个模型。给了默认值，所以客户端可以不传
    model: str = "gpt-4o-mini"

    # 采样温度(控制大模型生成下一个 token时有多随机):
    # ge=0.0 即 >= 0.0，le=2.0 即 <= 2.0，超出会被拦截
    # （这个范围是 OpenAI 兼容接口的约定）
    temperature: float = Field(default=0.7,ge=0.0,le=2.0)

    # 最多生成多少 token:
    # int | None = "整数或空"，默认 None = 不限制；
    # gt=0 = "如果填了，必须大于 0"
    max_tokens: int | None = Field(default=None, gt=0)


class ChatResponse(BaseModel):
    """返回给客户端的响应"""

    # 模型生成的内容
    content: str

    # 实际使用的模型名（客户端可能不指定，所以要回告）
    model: str

    # 本次消耗的 token 数
    # 默认 0 = "没有信息时用 0"
    usage_tokens: int = 0
