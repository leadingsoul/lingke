"""售后工单域模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class AfterSaleOrder(Base):
    __tablename__ = "after_sale_order"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("`order`.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(32), ForeignKey("consumer.id"), nullable=False)
    aso_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="仅退款 / 退货退款 / 换货 / 维修")
    aso_reason: Mapped[str] = mapped_column(String(20), nullable=False, comment="质量问题/发错货/物流问题/七天无理由/描述不符/其他")
    aso_status: Mapped[str] = mapped_column(String(20), default="待审核", comment="待审核/审核通过/处理中/已完成/已拒绝/已撤销")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_urls: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="凭证图片 URL 数组")
    handler_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("customer_service_staff.id"), nullable=True)
    review_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str] = mapped_column(String(10), default="普通", comment="AI 标记：普通/紧急")
    responsibility: Mapped[str] = mapped_column(String(10), default="待定", comment="AI 标记：商家/物流/用户/待定")
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True, comment="AI 建议处理方案")
    custom_tags: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="自定义标签数组")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
