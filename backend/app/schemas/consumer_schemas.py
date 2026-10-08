"""消费者端 Schema — 订单 / 咨询 / 售后 / 评价 / 个人资料"""

from pydantic import BaseModel, Field, field_validator, model_validator


# 售后相关常量
_ASO_TYPES = {"仅退款", "退货退款", "换货", "维修"}
_ASO_REASONS = {"质量问题", "发错货", "物流问题", "七天无理由", "描述不符", "未收到货", "尺码不合适", "意外损坏", "其他"}


# ═══════════ 订单 ═══════════
class OrderItem(BaseModel):
    id: str
    order_no: str | None = None
    product_name: str
    product_image: str | None = None
    price: float
    quantity: int
    total_amount: float
    status: str
    status_text: str | None = None
    platform: str | None = None
    shop_name: str | None = None
    created_at: str
    can_aftersale: bool = False

    class Config:
        from_attributes = True


class LogisticsInfo(BaseModel):
    company: str | None = None
    tracking_no: str | None = None
    status: str | None = None
    status_text: str | None = None
    delivery_time: str | None = None


class OrderDetail(BaseModel):
    id: str
    order_no: str | None = None
    platform: str | None = None
    shop_name: str | None = None
    product_name: str
    product_image: str | None = None
    product_spec: str | None = None
    price: float
    quantity: int
    total_amount: float
    discount_amount: float = 0.0
    payment_amount: float = 0.0
    status: str
    status_text: str | None = None
    logistics: LogisticsInfo | None = None
    aftersale_status: str | None = None
    aftersale_id: str | None = None
    can_aftersale: bool = False
    can_evaluate: bool = False
    created_at: str
    completed_at: str | None = None

    class Config:
        from_attributes = True


# ═══════════ 咨询 ═══════════
class ChatSendRequest(BaseModel):
    session_id: str | None = None
    order_id: str | None = None
    content: str = Field("", max_length=2000)
    image_urls: list[str] = []

    @model_validator(mode='after')
    def content_or_files(self) -> 'ChatSendRequest':
        """至少需要文字内容或文件附件之一"""
        if not self.content.strip() and not self.image_urls:
            raise ValueError("消息内容不能为空，或至少上传一个文件")
        return self


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    content: str
    ai_reply: str | None = None
    intent: str | None = None
    intent_level: str | None = None
    confidence: float | None = None
    suggestions: list[str] = []
    transfer_status: str | None = None
    created_at: str


class TransferRequest(BaseModel):
    session_id: str


class TransferResponse(BaseModel):
    message: str = "已转接人工客服"
    session_id: str
    transfer_status: str


# ═══════════ 售后工单 ═══════════
class AftersaleCreateRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    aso_type: str
    aso_reason: str
    description: str | None = Field(None, max_length=2000)
    evidence_urls: list[str] = []

    @field_validator("aso_type")
    @classmethod
    def validate_aso_type(cls, v: str) -> str:
        if v not in _ASO_TYPES:
            raise ValueError(f"售后类型必须为: {', '.join(_ASO_TYPES)}")
        return v

    @field_validator("aso_reason")
    @classmethod
    def validate_aso_reason(cls, v: str) -> str:
        if v not in _ASO_REASONS:
            raise ValueError(f"售后原因必须为: {', '.join(sorted(_ASO_REASONS))}")
        return v


class AftersaleItem(BaseModel):
    id: str
    order_id: str
    aso_type: str
    aso_reason: str
    aso_status: str
    description: str | None = None
    urgency: str = "普通"
    handler_name: str | None = None
    created_at: str
    completed_at: str | None = None

    class Config:
        from_attributes = True


class AftersaleDetail(BaseModel):
    id: str
    order_id: str
    consumer_id: str
    aso_type: str
    aso_reason: str
    aso_status: str
    description: str | None = None
    evidence_urls: list | None = None
    handler_id: str | None = None
    handler_name: str | None = None
    review_opinion: str | None = None
    urgency: str
    responsibility: str
    custom_tags: list | None = None
    created_at: str
    updated_at: str | None = None
    completed_at: str | None = None

    class Config:
        from_attributes = True


# ═══════════ 评价 ═══════════
class EvaluationCreateRequest(BaseModel):
    order_id: str
    product_rating: int = Field(..., ge=1, le=5)
    service_rating: int = Field(..., ge=1, le=5)
    logistics_rating: int = Field(..., ge=1, le=5)
    content: str | None = Field(None, max_length=2000)
    image_urls: list[str] = []
    is_anonymous: int = 0


class EvaluationItem(BaseModel):
    id: str
    order_id: str
    product_rating: int
    service_rating: int
    logistics_rating: int
    content: str | None = None
    sentiment: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class PendingEval(BaseModel):
    order_id: str
    order_sn: str | None = None
    product_name: str
    product_image: str | None = None
    total_amount: float = 0.0
    finished_at: str | None = None


class EvaluationUpdateRequest(BaseModel):
    """CON012：修改评价（7天内可改）"""
    product_rating: int | None = Field(None, ge=1, le=5)
    service_rating: int | None = Field(None, ge=1, le=5)
    logistics_rating: int | None = Field(None, ge=1, le=5)
    content: str | None = Field(None, max_length=2000)


# ═══════════ 个人资料 ═══════════
class ConsumerProfile(BaseModel):
    id: str
    nickname: str | None = None
    avatar: str | None = None
    phone: str | None = None
    platform_account: str | None = None
    level: str | None = "普通用户"
    platforms: list[str] = []
    created_at: str


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, max_length=50)
    avatar: str | None = Field(None, max_length=255)


class BindPhoneRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    sms_code: str = Field(..., min_length=4, max_length=6)


class LinkPlatformRequest(BaseModel):
    platform: str = Field(..., min_length=1, max_length=50)
    account: str = Field(..., min_length=1, max_length=100)


class FeedbackRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    type: str = "建议"


class RateConversationRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="满意度评分 1-5 星")
    feedback: str | None = Field(None, max_length=500, description="选填文字反馈")
