"""
数据契约：本服务【对外收发数据】的形状定义

为什么要单独一个文件：
  ① 入参和出参的形状属于"接口的一部分"，应该能一眼看全
  ② 阶段 1 的 FastAPI 会直接拿这些模型做请求校验和接口文档生成
  ③ 校验规则集中在这里，而不是散落在各处的 if 判断里
"""

from datetime import datetime

# Literal：标准库 typing 里的类型，表示"只能是这几个值之一"
from typing import Literal

# BaseModel：pydantic 的【普通】数据模型
#   对比用过的 BaseSettings —— 后者是它的子类，
#   额外具备"从环境变量 / .env 读取"的能力；BaseModel 没有，
#   它只负责【校验和转换数据】
# Field：给【单个字段】加约束（范围、长度、默认值…）
from pydantic import BaseModel, ConfigDict, Field


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

    # 用哪个模型。None = "客户端不指定"，由服务端用配置里的默认模型兜底
    # 为什么不在契约里写死模型名：契约层只描述【形状】，不该直到【哪家供应商的哪个模型】
    # 换供应商时这里不该跟着改（见 config.llm_model）
    model: str | None = None

    # 采样温度(控制大模型生成下一个 token时有多随机):
    # ge=0.0 即 >= 0.0，le=2.0 即 <= 2.0，超出会被拦截
    # （这个范围是 OpenAI 兼容接口的约定）
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

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


# 接口语义不同时不能复用，要写新的响应模型：
class ModelItem(BaseModel):
    """模型清单里的一个模型：只暴露调用方需要的字段"""

    # 字段名要与【上游 JSON 的键名】一致，才能用 model_validate(上游单条) 直接转换
    id: str = Field(description="模型 id，调用 /v1/chat 时传它")

    # 供应商给的展示名，设成可选（并非所有 OpenAI 兼容服务都返回 name 字段）
    name: str | None = Field(default=None, description="供应商给的展示名")

    context_window: int | None = Field(default=None, ge=1, description="上下文窗口（token 数）")


class ModelListResponse(BaseModel):
    """模型清单的统一响应形状（后续 /v1/models 与 /v1/upstream/models 共用）"""

    # total 是【过滤后命中的总数】，不是本页条数 —— 分页时这两个数不一样，不要弄混
    total: int = Field(ge=0, description="命中总数（不是本页条数）")

    # 此处用 list[ModelItem] 而不是 list[dict]的好处:
    #   文档层：/docs 能展开每个字段（给使用 API 的人看）
    #   安全层：响应模型是【白名单】：没声明的字段不可能出现在响应里
    items: list[ModelItem] = Field(description="本页的模型列表")


class ConversationIn(BaseModel):
    """
    新建对话的请求体：只让客户端填标题

    【注意】：这里不含 id 和 created_at —— 它们应该由数据库生成
    max_length=100 必须写：数据库的 String(100) 在 SQLite 上【不强制】
        所以长度校验只能靠这里挡
    """

    title: str = Field(min_length=1, max_length=100, description="对话标题")


class ConversationOut(BaseModel):
    """
    对话的响应形状（白名单：没声明的字段不会出现在响应里）

    from_attributes=True 让 pydantic 能【读对象属性】而不是只认 dict:
    路由直接返回 ORM 对象时，靠它才能转换
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="数据库生成的唯一编号")
    title: str = Field(description="对话标题")
    created_at: datetime = Field(description="创建时间（UTC，读回时 tzinfo 会丢）")
