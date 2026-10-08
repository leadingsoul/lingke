"""drop countermeasure table, add synced_to_knowledge and hit_count

Revision ID: 002
Revises: 001
Create Date: 2026-07-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 删除 countermeasure 表 ──
    op.drop_index("ix_countermeasure_status", table_name="countermeasure")
    op.drop_index("ix_countermeasure_theme", table_name="countermeasure")
    op.drop_table("countermeasure")

    # ── 2. session_summary：sync_status → synced_to_knowledge ──
    op.drop_column("session_summary", "sync_status")
    op.add_column(
        "session_summary",
        sa.Column("synced_to_knowledge", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    # ── 3. knowledge_item：添加 hit_count ──
    op.add_column(
        "knowledge_item",
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="RAG 命中次数"),
    )


def downgrade() -> None:
    # 逆序回滚

    op.drop_column("knowledge_item", "hit_count")

    op.drop_column("session_summary", "synced_to_knowledge")
    op.add_column(
        "session_summary",
        sa.Column("sync_status", sa.String(10), server_default="未同步"),
    )

    op.create_table(
        "countermeasure",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("theme", sa.String(50), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=True),
        sa.Column("trigger_condition", sa.Text(), nullable=False),
        sa.Column("reply_template", sa.Text(), nullable=False),
        sa.Column("action_plan", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), server_default="草稿"),
        sa.Column("call_count", sa.Integer(), server_default="0"),
        sa.Column("resolve_rate", sa.DECIMAL(5, 2), nullable=True),
        sa.Column("created_by", sa.String(32), nullable=True),
        sa.Column("reviewer_id", sa.String(32), sa.ForeignKey("admin.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_countermeasure_theme", "countermeasure", ["theme"])
    op.create_index("ix_countermeasure_status", "countermeasure", ["status"])
