"""咨询域模型：Conversation / Message / SessionSummary / SatisfactionFeedback / ServiceRecord"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    consumer_id: Mapped[str] = mapped_column(String(32), ForeignKey("consumer.id"), nullable=False)
    staff_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("customer_service_staff.id"), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("`order`.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="AI进行中", comment="AI进行中/待客服接手/客服处理中/已关闭")
    intent_level: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="L1/L2/L3")
    priority: Mapped[str] = mapped_column(String(10), default="普通")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversation.id"), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="consumer/ai/staff/system")
    sender_id: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="AI 时为 NULL")
    msg_type: Mapped[str] = mapped_column(String(20), default="text", comment="text/image/system_notice/ai_recommend")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI 元数据：意图/置信度/引用来源")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SessionSummary(Base):
    __tablename__ = "session_summary"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversation.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="MD 格式沉淀文档")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(10), default="待审核", comment="待审核/已审核")
    synced_to_knowledge: Mapped[bool] = mapped_column(default=False, comment="是否已同步至知识库")
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SatisfactionFeedback(Base):
    __tablename__ = "satisfaction_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversation.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(32), ForeignKey("consumer.id"), nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False, comment="1-5 星")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ServiceRecord(Base):
    __tablename__ = "service_record"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    staff_id: Mapped[str] = mapped_column(String(32), ForeignKey("customer_service_staff.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="回复/审核/关闭/转接")
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="conversation/ticket")
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
