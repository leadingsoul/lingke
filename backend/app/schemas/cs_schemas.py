"""客服端 Schema — 工作台 / 会话 / 工单"""

from pydantic import BaseModel, Field, field_validator


# ═══════════ 工作台 ═══════════
class CSDashboardResponse(BaseModel):
    pending_replies: int = 0
    pending_reviews: int = 0
    today_handled: int = 0
    avg_response_time: float = 0.0
    urgent_conversations: list = []
    pending_tickets: list = []


# ═══════════ 会话 ═══════════
class ConversationItem(BaseModel):
    id: str
    consumer_name: str | None = None
    consumer_avatar: str | None = None
    last_message: str | None = None
    status: str
    intent_level: str | None = None
    priority: str = "普通"
    message_count: int = 0
    unread_count: int = 0
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


class MessageItem(BaseModel):
    id: str
    sender_type: str
    sender_id: str | None = None
    msg_type: str = "text"
    content: str
    image_urls: list | None = None
    ai_metadata: dict | None = None
    created_at: str

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: str
    consumer_id: str
    consumer_name: str | None = None
    consumer_avatar: str | None = None
    order_id: str | None = None
    status: str
    intent_level: str | None = None
    priority: str
    messages: list[MessageItem] = []
    ai_suggestions: list[str] = []
    created_at: str


class ReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


# ═══════════ 工单 ═══════════
class TicketFilterRequest(BaseModel):
    aso_type: str | None = None
    aso_status: str | None = None
    urgency: str | None = None
    keyword: str | None = None


VALID_REVIEW_RESULTS = {"通过", "拒绝", "需补充"}

class TicketReviewRequest(BaseModel):
    result: str = Field(..., description="审核结果: 通过/拒绝/需补充")
    opinion: str | None = Field(None, max_length=500)

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        if v not in VALID_REVIEW_RESULTS:
            raise ValueError(f"result 必须是以下之一: {', '.join(sorted(VALID_REVIEW_RESULTS))}")
        return v


class TicketSupplementRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=500)


class TicketTagRequest(BaseModel):
    tag: str = Field(..., min_length=1, max_length=50)


class TicketBatchAssignRequest(BaseModel):
    ticket_ids: list[str] = Field(..., min_length=1, description="工单ID列表")
    staff_id: str = Field(..., min_length=1, description="客服ID")


class CSPerformanceResponse(BaseModel):
    today_handled: int = 0
    today_replies: int = 0
    today_reviews: int = 0
    avg_response_time: float = 0.0
    satisfaction_rate: float = 0.0
    online_hours: float = 0.0


# ═══════════ 统计 ═══════════
class CategoryStats(BaseModel):
    category: str
    count: int
    percentage: float


# ═══════════ 工单列表项 ═══════════
class AftersaleItem(BaseModel):
    id: str
    order_id: str | None = None
    consumer_name: str | None = None
    aso_type: str
    aso_reason: str | None = None
    aso_status: str
    urgency: str = "普通"
    responsibility: str = "待定"
    description: str | None = None
    created_at: str
    updated_at: str | None = None

    class Config:
        from_attributes = True


class AftersaleDetail(BaseModel):
    id: str
    order_id: str | None = None
    consumer_id: str | None = None
    consumer_name: str | None = None
    order_info: dict | None = None
    aso_type: str
    aso_reason: str | None = None
    description: str | None = None
    evidence_urls: list = []
    aso_status: str
    urgency: str = "普通"
    responsibility: str = "待定"
    suggested_action: str | None = None
    handle_opinion: str | None = None
    handle_staff: str | None = None
    custom_tags: list = []
    created_at: str
    updated_at: str | None = None
    timeline: list = []
