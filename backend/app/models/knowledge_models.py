"""知识运营域模型：KnowledgeItem / CrawlTask / CrawledReview"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class KnowledgeItem(Base):
    __tablename__ = "knowledge_item"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="商品知识/FAQ/售后政策")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Markdown 内容")
    status: Mapped[str] = mapped_column(String(10), default="启用")
    source: Mapped[str] = mapped_column(String(20), default="人工创建", comment="人工创建/批量导入/进化同步")
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, comment="RAG 命中次数")
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class CrawlTask(Base):
    __tablename__ = "crawl_task"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, comment="淘宝/京东/拼多多")
    keywords: Mapped[list] = mapped_column(JSON, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, comment="单次/每小时/每天")
    status: Mapped[str] = mapped_column(String(20), default="待启动", comment="待启动/运行中/已暂停/已完成/失败")
    progress: Mapped[int] = mapped_column(default=0)
    total_collected: Mapped[int] = mapped_column(default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("admin.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class CrawledReview(Base):
    __tablename__ = "crawled_review"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("crawl_task.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(nullable=True)
    review_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True)
    themes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_processed: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


