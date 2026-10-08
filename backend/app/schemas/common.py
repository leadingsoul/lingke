"""通用 Schema：统一响应、分页、WebSocket 事件"""

from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "操作成功"
    data: T | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "查询成功"
    data: PaginatedData[T]


class WSMessage(BaseModel):
    event: str           # new_message / ticket_status_change / new_conversation / new_ticket / system_notice / heartbeat
    data: dict
    timestamp: str | None = None
