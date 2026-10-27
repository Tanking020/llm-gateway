"""ORM 模型定义：把数据库表映射成 Python 类（本文件只放表结构，不含业务逻辑）"""

from datetime import UTC, datetime

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

    # 【注意】：SQLite 不强制这个上限（实测塞 200 字符能存进去），真正的长度校验要在
    # pydantic 层做；写在这里是为了换 PostgreSQL 时语义正确、也便于生成文档
    title: Mapped[str] = mapped_column(String(100))

    # 默认值必须是"可调用对象"（lambda），不能直接写 datetime.now(UTC)：
    # 直接写会在【import 类的那一刻】求值一次，导致后续所有行共用同一个时间
    # 数据库存 UTC（协调世界时），展示时再转本地时间
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 一对多：一个对话有多条调用记录
    # relationship 让两个属性互指，ORM 才知道它们是同一个关系的两侧
    # LlmCall 在后面才定义，所以写成字符串（延迟解析，否则 NameError）
    # 【注意】：故意【不写 cascade="all, delete-orphan"】——
    #   那会让删对话时把计费记录一起删掉，账目就丢了
    calls: Mapped[list["LlmCall"]] = relationship(
        back_populates="conversation",
        # 删父时，所有失去父对象的子对象都直接删掉
        cascade="all, delete-orphan",
    )


class LlmCall(Base):
    """
    一次 LLM 调用的用量记录（账单）

    conversation_id 可空：允许"不属于任何对话"的调用
        客户端没传 conversation_id 时就是这种
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 外键：告诉数据库【这一列的值必须是 conversations 表里已存在的 id】
    # ondelete="CASCADE"：父行被删时，数据库自动删掉子行
    # index=True: 按外键额外建一条索引（外键常要建索引，因为要按外键查子记录，否则会变成全表扫）
    # 【注意】：上面这个 ondelete 只在【绕过 ORM 直接发 DELETE 语句】时生效。
    #   走 session.delete() 时它【管不到】—— 实测即使写了 ondelete="CASCADE"，
    #   ORM 仍然只把 conversation_id 置成 NULL（因为这一列可空）。
    #   真正让 ORM 删子行的是 Conversation.calls 上的 cascade="all, delete-orphan"。
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )

    # 上游回报的模型名（客户端可能不指定，所以记录"实际用的那个"）
    model: Mapped[str] = mapped_column(String(100))

    # 三种 token 数都默认 0：上游没回 usage 时就是 0，而不是 NULL
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # 反向导航：call.conversation 拿到那条对话
    conversation: Mapped["Conversation | None"] = relationship(back_populates="calls")
