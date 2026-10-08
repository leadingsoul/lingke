"""管理员端 Schema — 概览 / 知识库 / 客服 / 统计 / 爬虫 / 对策库 / 沉淀文档 / 操作日志"""

from pydantic import BaseModel, Field


# ═══════════ 系统概览 ═══════════
class AdminDashboardResponse(BaseModel):
    total_consultations: int = 0
    pending_tickets: int = 0
    negative_evals: int = 0
    online_staff: int = 0
    consultation_trend: list = []
    ticket_trend: list = []
    sentiment_trend: list = []


# ═══════════ 知识库 ═══════════
class KnowledgeCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(商品知识|FAQ|售后政策)$")
    tags: list[str] = []
    content: str = Field(..., min_length=1)
    status: str = "启用"


class KnowledgeUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    type: str | None = Field(None, pattern="^(商品知识|FAQ|售后政策)$")
    tags: list[str] | None = None
    content: str | None = None
    status: str | None = None


class KnowledgeItem(BaseModel):
    id: str
    title: str
    type: str
    tags: list | None = None
    content: str
    status: str
    source: str
    created_by: str | None = None
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


# ═══════════ 客服管理 ═══════════
class StaffCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    name: str = Field(..., min_length=1, max_length=50)
    role: str = "普通客服"
    phone: str | None = None
    email: str | None = None
    max_concurrent: int = 5


class StaffUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=50)
    role: str | None = None
    status: str | None = None
    email: str | None = None
    max_concurrent: int | None = None


class StaffItem(BaseModel):
    id: str
    username: str
    name: str
    role: str
    status: str
    phone: str | None = None
    email: str | None = None
    max_concurrent: int
    today_handled: int = 0
    satisfaction_rate: float = 0.0
    created_at: str

    class Config:
        from_attributes = True


class StaffPerformanceItem(BaseModel):
    staff_id: str
    staff_name: str
    today_handled: int
    avg_response_time: float
    satisfaction_rate: float
    total_conversations: int
    total_reviews: int


# ═══════════ 统计 ═══════════
class StatsQueryRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    group_by: str = "day"   # day / week / month


class ExportRequest(BaseModel):
    type: str = Field(..., pattern="^(satisfaction|ticket|performance|hot_topics|product_eval)$")
    format: str = "xlsx"
    start_date: str | None = None
    end_date: str | None = None


class AIInsightRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None


# ═══════════ 爬虫 ═══════════
class CrawlTaskCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    platform: str = Field(..., min_length=1, max_length=50)
    keywords: list[str] = Field(..., min_items=1)
    frequency: str = Field(..., pattern="^(单次|每小时|每天)$")


class CrawlTaskItem(BaseModel):
    id: str
    name: str
    platform: str
    status: str
    progress: int
    total_collected: int
    last_run_at: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class CrawledReviewItem(BaseModel):
    id: str
    platform: str
    reviewer_nickname: str | None = None
    content: str
    rating: int | None = None
    sentiment: str | None = None
    is_processed: int
    created_at: str

    class Config:
        from_attributes = True


# ═══════════ 沉淀文档 ═══════════
class SummaryItem(BaseModel):
    id: str
    conversation_id: str
    tags: list | None = None
    review_status: str
    synced_to_knowledge: bool = False
    reviewer_id: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class SummaryDetail(BaseModel):
    id: str
    conversation_id: str
    content: str
    tags: list | None = None
    review_status: str
    synced_to_knowledge: bool = False
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    created_at: str

    class Config:
        from_attributes = True


# ═══════════ 操作日志 ═══════════
class OperationLogItem(BaseModel):
    id: str
    staff_id: str
    staff_name: str | None = None
    action: str
    target_type: str
    target_id: str
    detail: str | None = None
    created_at: str

    class Config:
        from_attributes = True
