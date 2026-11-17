"""owner_id on conversations

Revision ID: 7c1f0a2d9b44
Revises: 7112e775108b
Create Date: 2026-11-17 19:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1f0a2d9b44"
down_revision: Union[str, Sequence[str], None] = "7112e775108b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ① 先加可空列：SQLite 的 ADD COLUMN 只能加「可空」或「带默认值」的列
    op.add_column("conversations", sa.Column("owner_id", sa.Integer(), nullable=True))

    # ② 回填：库里已有对话时，造一个 legacy 用户把它们全接住（否则下一步设 NOT NULL 会失败）
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM conversations LIMIT 1")).first() is not None:
        bind.execute(
            sa.text("INSERT INTO users (name, created_at) VALUES ('legacy', CURRENT_TIMESTAMP)")
        )
        legacy_id = bind.execute(sa.text("SELECT id FROM users WHERE name = 'legacy'")).scalar_one()
        bind.execute(
            sa.text("UPDATE conversations SET owner_id = :oid WHERE owner_id IS NULL"),
            {"oid": legacy_id},
        )

    # ③ 再在【重建表】里把列改成 NOT NULL 并挂上外键/索引
    # 【注意】：SQLite 不支持 ALTER COLUMN，batch_alter_table 是「建新表 → 拷数据 → 换名」
    with op.batch_alter_table("conversations") as batch:
        batch.alter_column("owner_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_conversations_owner_id_users", "users", ["owner_id"], ["id"]
        )
        batch.create_index("ix_conversations_owner_id", ["owner_id"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("conversations") as batch:
        batch.drop_index("ix_conversations_owner_id")
        batch.drop_constraint("fk_conversations_owner_id_users", type_="foreignkey")
        batch.drop_column("owner_id")
    # 回填时造的 legacy 用户留在库里：downgrade 只回退结构，不删数据
    # （删了它会让「某次 downgrade 之后用户的对话凭空换了主人」这种更难查的事发生）
