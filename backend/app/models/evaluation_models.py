"""评价域模型：Evaluation / EvaluationReply"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON, DECIMAL, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Evaluation(Base):
    __tablename__ = "evaluation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("`order`.id"), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(32), ForeignKey("consumer.id"), nullable=False)
    product_rating: Mapped[int] = mapped_column(nullable=False, comment="商品质量 1-5")
    service_rating: Mapped[int] = mapped_column(nullable=False, comment="服务质量 1-5")
    logistics_rating: Mapped[int] = mapped_column(nullable=False, comment="物流速度 1-5")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_anonymous: Mapped[int] = mapped_column(default=0, comment="是否匿名")
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="AI：positive/neutral/negative")
    sentiment_intensity: Mapped[float | None] = mapped_column(DECIMAL(3, 2), nullable=True)
    themes: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="AI 主题归类结果")
    risk_level: Mapped[str] = mapped_column(String(10), default="low")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class EvaluationReply(Base):
    __tablename__ = "evaluation_reply"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    evaluation_id: Mapped[str] = mapped_column(String(32), ForeignKey("evaluation.id"), nullable=False)
    reply_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="consumer(追评) / merchant(商家回复)")
    replier_id: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
