"""ORM 模型定义：把数据库表映射成 Python 类（本文件只放表结构，不含业务逻辑）"""

from datetime import UTC, datetime
from enum import StrEnum

# String(length) 用于声明有长度限制的文本列，例如对话标题
# ForeignKey 声明"这一列引用另一张表的主键"，这是【数据库层】的约束
from sqlalchemy import ForeignKey, String

# DeclarativeBase 是 ORM 模型共用的声明式基类；Mapped 标记映射字段及其 Python 类型；
# mapped_column 用来配置数据库列属性。
# relationship 声明"关系"：它不产生任何列，只提供 Python 层的对象导航（conv.calls）
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    所有 ORM 模型的公共基类

    它的作用是收集元数据：每个继承它的类都会往 Base.metadata 里登记一张表，
    之后 create_all 就靠这份清单建表（没有它就无法"一次性建全部表"）
    """


class Conversation(Base):
    """
    一段对话的元信息（标题 + 创建时间）

    calls 是一对多关系，指向本对话的所有 LLM 调用记录（账单）
    注意：对话的**消息内容**还没有表（见能力档案待办 #35）
    """

    __tablename__ = "conversations"

    # 两边分别是"列类型注解"和"列配置"
    id: Mapped[int] = mapped_column(primary_key=True)

    # 归属：这条对话属于谁。NOT NULL + 索引 —— 每次查询都会带 owner_id 过滤
    # 【注意】：故意【不写】ondelete="CASCADE"：删用户不能连对话和账单一起蒸发（决策 16 / 40）
    #   不写 = NO ACTION，数据库会拒绝删一个还有对话的用户，逼你先处理归属
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # 【注意】：SQLite 不强制这个上限（实测塞 200 字符能存进去），真正的长度校验要在
    # pydantic 层做；写在这里是为了换 PostgreSQL 时语义正确、也便于生成文档
    title: Mapped[str] = mapped_column(String(100))

    # 默认值必须是"可调用对象"（lambda），不能直接写 datetime.now(UTC)：
    # 直接写会在【import 类的那一刻】求值一次，导致后续所有行共用同一个时间
    # 数据库存 UTC（协调世界时），展示时再转本地时间
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 【注意】：onupdate 是 SQLAlchemy 在 Python 侧算好再塞进 UPDATE 的，
    #   不是数据库触发器 —— 绕过 ORM 直接写 SQL 时它不会更新
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # 一对多：一个对话有多条调用记录
    # relationship 让两个属性互指，ORM 才知道它们是同一个关系的两侧
    # LlmCall 在后面才定义，所以写成字符串（延迟解析，否则 NameError）
    # 【注意】：故意【不写 cascade="all, delete-orphan"】——
    #   那会让删对话时把计费记录一起删掉（级联删除），账目就丢了
    calls: Mapped[list["LlmCall"]] = relationship(back_populates="conversation")

    # 反向导航：conv.owner 拿到属主。不写 back_populates（User 那边不需要 conversations）
    owner: Mapped["User"] = relationship()


class LlmCallStatus(StrEnum):
    """
    账单行的状态：只表达【这一行的金额准不准】，不表达【内容空不空】

    【注意】：数据库里存的是【字符串值】不是成员名 —— 列类型仍是 String(20)，无需迁移。
        读回来是普通 str，所以比较时候可以直接写 row.status == "completed"。
    """

    PENDING = "pending"
    COMPLETED = "completed"
    ABORTED = "aborted"
    NO_CONTENT = "no_content"


class LlmCall(Base):
    """
    一次 LLM 调用的用量记录（账单）

    conversation_id 可空：允许"不属于任何对话"的调用
        客户端没传 conversation_id 时就是这种
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 外键：这一列的值必须是 conversations 表里已存在的 id
    # ondelete="SET NULL"：父行被删时只把这一列置 NULL，整条记录保留
    # 【注意】：不能写 CASCADE —— 计费是账目，删对话不能连带删账
    #   （实测写 CASCADE 时删 1 个对话丢 900 token）
    # index=True：要按 conversation_id 查「这个对话花了多少」，不建会全表扫
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        index=True,
    )

    # 上游回报的模型名（客户端可能不指定，所以记录"实际用的那个"）
    model: Mapped[str] = mapped_column(String(100))

    # 三种 token 数都默认 0：上游没回 usage 时就是 0，而不是 NULL
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)

    # 这次调用怎么结束的，取值见 LlmCallStatus：
    #   completed = 拿到完整 usage（金额可信）/ aborted = 客户端断开或上游异常
    #   no_content = 上游 200 但一帧内容都没有 / pending = 没走到收尾（进程崩了）
    # 【注意】：断开时上游【已经产出的 token 照样收费】，所以不能因为没拿到 usage
    # 就把这一行丢掉 —— 否则账面完全看不到这次调用，月底对账查不出差额来自哪里
    status: Mapped[str] = mapped_column(String(20), default=LlmCallStatus.COMPLETED)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 反向导航：call.conversation 拿到那条对话
    conversation: Mapped["Conversation | None"] = relationship(back_populates="calls")


class User(Base):
    """
    一个「拥有资源的人」—— 目前只有名字，将来放邮箱 / 配额

    【注意】：删用户【不】连带删对话（owner_id 外键不写 CASCADE）——
        对话与账单是资产，删人必须先处理归属，让数据库替我们拒绝
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 删用户时凭据一起删（凭据是附属品，不是资产）
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    """
    一把可用于调用 API 的钥匙 —— 库里只存 sha256，明文只在生成时给一次

    【注意】：存 hash 不存明文：库或备份泄露都不泄露可用凭据。
        不用 bcrypt：key 是 32 字节随机串（高熵），慢哈希只增加每个请求的 CPU
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # unique=True：一把 key 不可能属于两个人；unique 自带索引，鉴权每次走它查
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # 人看的标签（"笔记本" / "CI"），不参与鉴权
    label: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 撤销时间：非空 = 已停用。不删行是为了留审计痕迹
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship(back_populates="api_keys")
