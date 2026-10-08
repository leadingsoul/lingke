"""消息通知域模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    recipient_id: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="consumer/staff/admin")
    type: Mapped[str] = mapped_column(String(50), nullable=False, comment="工单状态变更/新消息/系统公告")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
