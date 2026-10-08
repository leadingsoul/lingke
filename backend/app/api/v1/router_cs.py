"""客服端路由 — 工作台 / 会话 / 工单 / 统计 / 操作记录 / 知识库"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_current_cs_staff, get_current_cs_or_admin
from app.core.database import get_db
from app.models.chat_models import Conversation
from app.api.v1.router_ws import manager
from app.schemas.cs_schemas import (
    CSDashboardResponse,
    ConversationItem,
    ConversationDetail,
    ReplyRequest,
    MessageItem,
    AftersaleItem,
    AftersaleDetail,
    TicketReviewRequest,
    TicketSupplementRequest,
    TicketTagRequest,
    TicketBatchAssignRequest,
    CategoryStats,
    CSPerformanceResponse,
)
from app.schemas.admin_schemas import KnowledgeItem as KnowledgeItemSchema, OperationLogItem
from app.services.admin_service import AdminService
from app.services.cs_service import CSService

router = APIRouter()


# ═══════════════ 工作台 ═══════════════

@router.get("/dashboard", response_model=dict, summary="客服工作台概览")
async def get_dashboard(
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.get_dashboard(staff_id=current_user["id"], db=db)
    return {"code": 200, "message": "查询成功", "data": result}


# ═══════════════ 会话 ═══════════════

@router.get("/conversations", response_model=dict, summary="查询会话列表")
async def get_conversations(
    status: str = Query(None, description="会话状态过滤"),
    priority: str = Query(None, description="优先级过滤"),
    keyword: str = Query(None, description="关键词搜索（用户名/商品名）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    items, total = await service.get_conversations(
        staff_id=current_user["id"],
        status=status,
        priority=priority,
        keyword=keyword,
        page=page,
        page_size=page_size,
        db=db,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.get("/conversations/{conversation_id}", response_model=dict, summary="查询会话详情")
async def get_conversation_detail(
    conversation_id: str,
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    detail = await service.get_conversation_detail(conversation_id=conversation_id, db=db)
    return {"code": 200, "message": "查询成功", "data": detail}


@router.get("/conversations/{conversation_id}/messages", response_model=dict, summary="查询会话消息列表")
async def get_conversation_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    items, total = await service.get_conversation_messages(
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
        db=db,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post("/conversations/{conversation_id}/reply", response_model=dict, summary="客服回复消息")
async def reply_conversation(
    conversation_id: str,
    request: ReplyRequest,
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.reply_conversation(
        conversation_id=conversation_id,
        staff_id=current_user["id"],
        content=request.content,
        db=db,
    )

    # 查询会话的 consumer_id，服务端推送 WS 消息给消费者
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        # 推送新消息给消费者
        await manager.send_personal(
            {
                "event": "new_message",
                "data": {
                    "id": result.get("message_id"),
                    "conversation_id": conversation_id,
                    "sender_type": "staff",
                    "sender_name": current_user.get("name") or current_user.get("username", "客服"),
                    "content": request.content,
                    "created_at": str(conv.updated_at or ""),
                },
                "timestamp": None,
            },
            conv.consumer_id,
        )

        # 广播会话状态变更给所有在线客服，确保列表同步刷新（如"待客服接手→客服处理中"）
        await manager.broadcast_to_role(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": conversation_id,
                    "status": conv.status,
                    "staff_id": current_user["id"],
                    "staff_name": current_user.get("name") or current_user.get("username", "客服"),
                    "updated_at": str(conv.updated_at or ""),
                    "message": f"客服 {current_user.get('name') or current_user.get('username', '未知')} 已接手会话 {conversation_id}",
                },
                "timestamp": None,
            },
            "cs_staff",
        )

    return {"code": 200, "message": "回复成功", "data": result}


@router.post("/conversations/{conversation_id}/close", response_model=dict, summary="关闭会话")
async def close_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    await service.close_conversation(
        conversation_id=conversation_id,
        staff_id=current_user["id"],
        db=db,
    )

    # 推送关闭事件给消费者
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        await manager.send_personal(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": conversation_id,
                    "status": "已关闭",
                    "action": "rate_request",
                },
                "timestamp": None,
            },
            conv.consumer_id,
        )

        # 广播关闭事件给所有在线客服，同步列表刷新
        await manager.broadcast_to_role(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": conversation_id,
                    "status": "已关闭",
                    "staff_id": current_user["id"],
                    "staff_name": current_user.get("name") or current_user.get("username", "客服"),
                    "message": f"客服 {current_user.get('name') or current_user.get('username', '未知')} 已关闭会话 {conversation_id}",
                },
                "timestamp": None,
            },
            "cs_staff",
        )

    return {"code": 200, "message": "会话已关闭", "data": None}


@router.delete("/conversations/{conversation_id}", response_model=dict, summary="删除会话（硬删除）")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    """永久删除会话及其所有关联消息、沉淀文档、满意度反馈、操作记录"""
    await service.delete_conversation(
        conversation_id=conversation_id,
        staff_id=current_user["id"],
        db=db,
    )

    # 广播删除事件给所有在线客服，同步列表刷新
    await manager.broadcast_to_role(
        {
            "event": "conversation_update",
            "data": {
                "conversation_id": conversation_id,
                "status": "已删除",
                "staff_id": current_user["id"],
                "staff_name": current_user.get("name") or current_user.get("username", "客服"),
                "message": f"客服 {current_user.get('name') or current_user.get('username', '未知')} 已删除会话 {conversation_id}",
            },
            "timestamp": None,
        },
        "cs_staff",
    )

    return {"code": 200, "message": "会话已删除", "data": None}


# ═══════════════ 工单 ═══════════════

@router.get("/tickets", response_model=dict, summary="查询售后工单列表")
async def get_tickets(
    aso_type: str = Query(None, description="工单类型过滤"),
    aso_status: str = Query(None, description="工单状态过滤"),
    urgency: str = Query(None, description="紧急程度过滤"),
    keyword: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    items, total = await service.get_tickets(
        aso_type=aso_type,
        aso_status=aso_status,
        urgency=urgency,
        keyword=keyword,
        page=page,
        page_size=page_size,
        db=db,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post("/tickets/batch-assign", response_model=dict, summary="批量分配工单")
async def batch_assign_tickets(
    request: TicketBatchAssignRequest,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.batch_assign_tickets(
        ticket_ids=request.ticket_ids,
        staff_id=request.staff_id,
        db=db,
    )
    return {
        "code": 200,
        "message": f"已为 {result['assigned_count']} 个工单分配客服 {result['staff_name']}",
        "data": result,
    }


@router.get("/tickets/{ticket_id}", response_model=dict, summary="查询工单详情")
async def get_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    detail = await service.get_ticket_detail(ticket_id=ticket_id, db=db)
    return {"code": 200, "message": "查询成功", "data": detail}


@router.post("/tickets/{ticket_id}/review", response_model=dict, summary="审核工单")
async def review_ticket(
    ticket_id: str,
    request: TicketReviewRequest,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.review_ticket(
        ticket_id=ticket_id,
        staff_id=current_user["id"],
        result=request.result,
        opinion=request.opinion,
        db=db,
    )
    return {"code": 200, "message": "审核完成", "data": result}


@router.post("/tickets/{ticket_id}/supplement", response_model=dict, summary="补充工单信息")
async def supplement_ticket(
    ticket_id: str,
    request: TicketSupplementRequest,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    await service.supplement_ticket(
        ticket_id=ticket_id,
        staff_id=current_user["id"],
        note=request.note,
        db=db,
    )
    return {"code": 200, "message": "补充信息已保存", "data": None}


@router.post("/tickets/{ticket_id}/complete", response_model=dict, summary="完成工单")
async def complete_ticket(
    ticket_id: str,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.complete_ticket(
        ticket_id=ticket_id,
        staff_id=current_user["id"],
        db=db,
    )
    return {"code": 200, "message": "工单已完成", "data": result}


@router.post("/tickets/{ticket_id}/tags", response_model=dict, summary="为工单打标签")
async def tag_ticket(
    ticket_id: str,
    request: TicketTagRequest,
    current_user: dict = Depends(get_current_cs_or_admin),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.tag_ticket(
        ticket_id=ticket_id,
        staff_id=current_user["id"],
        tag=request.tag,
        db=db,
    )
    return {"code": 200, "message": "标签添加成功", "data": result}


# ═══════════════ 统计 ═══════════════

@router.get("/stats/category", response_model=dict, summary="工单分类统计")
async def get_category_stats(
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.get_category_stats(db=db)
    return {"code": 200, "message": "查询成功", "data": result}


@router.get("/performance", response_model=dict, summary="客服个人绩效")
async def get_performance(
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    result = await service.get_performance(staff_id=current_user["id"], db=db)
    return {"code": 200, "message": "查询成功", "data": result}


# ═══════════════ 操作记录 ═══════════════

@router.get("/records", response_model=dict, summary="查询操作记录")
async def get_operation_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
    service: CSService = Depends(),
):
    items, total = await service.get_operation_records(
        staff_id=current_user["id"],
        page=page,
        page_size=page_size,
        db=db,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


# ═══════════════ 知识库（只读） ═══════════════

@router.get("/knowledge", response_model=dict, summary="查询知识库列表")
async def get_knowledge(
    type: str = Query(None, description="知识类型过滤"),
    tag: str = Query(None, description="标签过滤"),
    keyword: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_cs_staff),
    db: AsyncSession = Depends(get_db),
):
    admin_service = AdminService()
    items, total = await admin_service.get_knowledge_items(
        type=type, tag=tag, keyword=keyword, status="启用",
        page=page, page_size=page_size, db=db,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }
