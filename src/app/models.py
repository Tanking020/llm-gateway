"""ORM 模型定义：把数据库表映射成 Python 类（本文件只放表结构，不含业务逻辑）"""

from datetime import UTC, datetime

# String(length) 用于声明有长度限制的文本列，例如对话标题
from sqlalchemy import String

# DeclarativeBase 是 ORM 模型共用的声明式基类；Mapped 标记映射字段及其 Python 类型；
# mapped_column 用来配置数据库列属性。
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    所有 ORM 模型的公共基类

    它的作用是收集元数据：每个继承它的类都会往 Base.metadata 里登记一张表，
    之后 create_all 就靠这份清单建表（没有它就无法"一次性建全部表"）
    """


class Conversation(Base):
    """
    一段对话的元信息（标题 + 创建时间）

    暂时只建表结构，还没有 message 关系
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
