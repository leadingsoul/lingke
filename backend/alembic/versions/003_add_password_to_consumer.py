"""add password column to consumer table

Revision ID: 003
Revises: 002
Create Date: 2026-09-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("consumer", sa.Column("password", sa.String(255), nullable=True, comment="bcrypt 密码（账号登录用）"))


def downgrade() -> None:
    op.drop_column("consumer", "password")