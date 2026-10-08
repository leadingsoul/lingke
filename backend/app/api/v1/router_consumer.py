"""消费者端路由 — 订单 / 咨询 / 售后 / 评价 / 个人资料"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_current_consumer
from app.core.database import get_db
from app.models.chat_models import Conversation
from app.api.v1.router_ws import manager
from app.schemas.consumer_schemas import (
    OrderItem,
    OrderDetail,
    ChatSendRequest,
    ChatMessageResponse,
    TransferRequest,
    TransferResponse,
    AftersaleCreateRequest,
    AftersaleItem,
    AftersaleDetail,
    EvaluationCreateRequest,
    EvaluationUpdateRequest,
    EvaluationItem,
    PendingEval,
    ConsumerProfile,
    ProfileUpdateRequest,
    BindPhoneRequest,
    LinkPlatformRequest,
    FeedbackRequest,
    RateConversationRequest,
)
from app.services.consumer_service import ConsumerService

router = APIRouter()


# ═══════════════ 订单 ═══════════════

@router.get("/orders", response_model=dict, summary="查询订单列表")
async def get_orders(
    status: str = Query(None, description="订单状态过滤"),
    keyword: str = Query(None, description="商品名称/订单号搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_orders(
        consumer_id=current_user["id"], status=status, keyword=keyword,
        page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/orders/{order_id}", response_model=dict, summary="查询订单详情")
async def get_order_detail(
    order_id: str,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    detail = await service.get_order_detail(consumer_id=current_user["id"], order_id=order_id, db=db)
    return {"code": 200, "message": "查询成功", "data": detail}


# ═══════════════ 咨询 ═══════════════

@router.post("/chat/conversations", response_model=dict, summary="创建新的咨询会话")
async def create_conversation(
    payload: dict,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    """进入咨询页时立即创建会话，不等用户发消息"""
    order_id = payload.get("order_id")
    result = await service.create_conversation(
        consumer_id=current_user["id"], order_id=order_id, db=db,
    )
    return {"code": 200, "message": "会话已创建", "data": result}


@router.post("/chat/send", response_model=dict, summary="发送咨询消息")
async def send_chat_message(
    request: ChatSendRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.send_chat_message(
        consumer_id=current_user["id"], session_id=request.session_id,
        order_id=request.order_id, content=request.content,
        image_urls=request.image_urls, db=db,
    )

    # ── 每一条消费者消息都推送给在线客服（不只是转人工时） ──
    session_id = result.get("session_id")
    if session_id:
        # 查询会话，确认是否有已指派的客服
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        conv = conv_result.scalar_one_or_none()
        consumer_name = current_user.get("name") or current_user.get("username", "用户")

        # 构建 WS 消息体
        ws_msg = {
            "event": "new_message",
            "data": {
                "id": result.get("message_id"),
                "conversation_id": session_id,
                "sender_type": "consumer",
                "sender_name": consumer_name,
                "content": request.content,
                "image_urls": request.image_urls or [],
                "created_at": result.get("created_at", ""),
            },
            "timestamp": None,
        }

        if conv and conv.staff_id:
            # 已有指派客服 → 精准推送给该客服
            await manager.send_personal(ws_msg, conv.staff_id)
        elif conv:
            # 未指派客服 → 广播给所有在线客服
            await manager.broadcast_to_role(ws_msg, "cs_staff")

    # 新会话或AI升级为人工时，广播会话状态变更通知给客服
    is_new_conv = conv and (conv.message_count or 0) <= 2
    consumer_name = current_user.get("name") or current_user.get("username", "用户")

    if result.get("is_transferred"):
        await manager.broadcast_to_role(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": result["session_id"],
                    "status": "待客服接手",
                    "priority": "紧急",
                    "consumer_id": current_user["id"],
                    "consumer_name": consumer_name,
                    "intent_level": result.get("intent_level", "L3"),
                    "message": f"🔴 AI 自动升级：{consumer_name} 的会话需要人工处理",
                },
                "timestamp": None,
            },
            "cs_staff",
        )
    elif is_new_conv:
        await manager.broadcast_to_role(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": result["session_id"],
                    "status": conv.status,
                    "priority": conv.priority,
                    "consumer_id": current_user["id"],
                    "consumer_name": consumer_name,
                    "intent_level": result.get("intent_level", "L1"),
                    "message": f"📩 新咨询：{consumer_name} 发起了会话（{result.get('intent_level', 'L1')}）",
                },
                "timestamp": None,
            },
            "cs_staff",
        )

    return {"code": 200, "message": "消息已发送", "data": result}


@router.get("/chat/conversations", response_model=dict, summary="查询消费者的咨询会话列表")
async def get_my_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_my_conversations(
        consumer_id=current_user["id"], page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.delete("/chat/conversations/{session_id}", response_model=dict, summary="删除消费者的咨询会话")
async def delete_my_conversation(
    session_id: str,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.delete_my_conversation(
        consumer_id=current_user["id"], session_id=session_id, db=db,
    )
    return {"code": 200, "message": "会话已删除", "data": None}


@router.post("/chat/conversations/{session_id}/rate", response_model=dict, summary="对已关闭会话进行满意度评分")
async def rate_conversation(
    session_id: str,
    payload: RateConversationRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.rate_conversation(
        consumer_id=current_user["id"],
        session_id=session_id,
        rating=payload.rating,
        feedback=payload.feedback,
        db=db,
    )

    # ═══ WS 通知：评分后推送给客服，刷新绩效页 ═══
    try:
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv and conv.staff_id:
            await manager.send_personal(
                {
                    "event": "rating_update",
                    "data": {
                        "conversation_id": session_id,
                        "rating": payload.rating,
                        "consumer_name": current_user.get("name") or current_user.get("username", "用户"),
                    },
                    "timestamp": None,
                },
                conv.staff_id,
            )
    except Exception:
        pass  # WS 推送失败不影响评分主流程
    return {"code": 200, "message": "评分成功", "data": result}


@router.get("/chat/history/{session_id}", response_model=dict, summary="查询会话历史消息")
async def get_chat_history(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_chat_history(
        session_id=session_id, consumer_id=current_user["id"],
        page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# ── 聊天文件上传 ──

CHAT_ALLOWED_EXTENSIONS = {
    # 图片
    "jpg", "jpeg", "png", "gif", "webp", "svg", "bmp",
    # 视频
    "mp4", "mov", "webm", "avi",
    # 文档
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv",
}

CHAT_MAX_SIZE = 50 * 1024 * 1024  # 50 MB

# 上传根目录（与 main.py 中 StaticFiles mount 路径一致）
_CHAT_UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "uploads"


@router.post("/chat/upload", response_model=dict, summary="上传聊天文件（图片/视频/文档）")
async def upload_chat_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_consumer),
):
    """接收消费者上传的文件，返回可访问的 URL"""

    # 校验扩展名
    ext = Path(file.filename or "unknown").suffix.lstrip(".").lower()
    if ext not in CHAT_ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": f"不支持的文件类型: .{ext}", "data": None},
        )

    # 生成唯一文件名
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = _CHAT_UPLOAD_ROOT / "chat"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 流式写入
    file_path = upload_dir / safe_name
    total = 0
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            total += len(chunk)
            if total > CHAT_MAX_SIZE:
                f.close()
                file_path.unlink(missing_ok=True)
                return JSONResponse(
                    status_code=413,
                    content={"code": 413, "message": "文件大小超过 50MB 限制", "data": None},
                )
            f.write(chunk)

    # 判断文件类型大类
    if ext in {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}:
        file_type = "image"
    elif ext in {"mp4", "mov", "webm", "avi"}:
        file_type = "video"
    else:
        file_type = "document"

    url = f"/uploads/chat/{safe_name}"
    return {
        "code": 200,
        "message": "上传成功",
        "data": {
            "url": url,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": total,
            "extension": ext,
        },
    }


@router.post("/chat/transfer", response_model=dict, summary="请求转接人工客服")
async def transfer_to_human(
    request: TransferRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.transfer_to_human(session_id=request.session_id, db=db)

    # 查询会话详情，向所有在线客服广播新待处理会话
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == request.session_id)
    )
    conv = conv_result.scalar_one_or_none()
    if conv:
        await manager.broadcast_to_role(
            {
                "event": "conversation_update",
                "data": {
                    "conversation_id": conv.id,
                    "status": conv.status,
                    "priority": conv.priority,
                    "consumer_id": conv.consumer_id,
                    "intent_level": conv.intent_level,
                    "created_at": str(conv.created_at or ""),
                    "message": f"用户 {current_user.get('display_name', current_user.get('id', ''))} 请求转接人工客服",
                },
                "timestamp": None,
            },
            "cs_staff",
        )

    return {"code": 200, "message": "已转接人工客服", "data": result}


# ═══════════════ 售后工单 ═══════════════

@router.post("/aftersale", response_model=dict, summary="创建售后工单")
async def create_aftersale(
    request: AftersaleCreateRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.create_aftersale(
        consumer_id=current_user["id"], order_id=request.order_id,
        aso_type=request.aso_type, aso_reason=request.aso_reason,
        description=request.description, evidence_urls=request.evidence_urls, db=db,
    )
    # WS 广播：通知所有在线客服有新工单
    aftersale_id = result.get("id", "")
    await manager.broadcast_to_role(
        {
            "event": "ticket_update",
            "data": {
                "aftersale_id": aftersale_id,
                "aso_type": request.aso_type,
                "aso_reason": request.aso_reason,
                "aso_status": "待审核",
                "urgency": result.get("urgency", "普通"),
                "consumer_name": current_user.get("name") or current_user.get("username", "用户"),
                "message": f"新售后工单：{request.aso_type} - {request.aso_reason}",
            },
            "timestamp": None,
        },
        "cs_staff",
    )
    return {"code": 200, "message": "工单创建成功", "data": result}


@router.get("/aftersale", response_model=dict, summary="查询售后工单列表")
async def get_aftersales(
    aso_status: str = Query(None, description="工单状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_aftersales(
        consumer_id=current_user["id"], aso_status=aso_status,
        page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/aftersale/{aftersale_id}", response_model=dict, summary="查询售后工单详情")
async def get_aftersale_detail(
    aftersale_id: str,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    detail = await service.get_aftersale_detail(consumer_id=current_user["id"], aftersale_id=aftersale_id, db=db)
    return {"code": 200, "message": "查询成功", "data": detail}


@router.delete("/aftersale/{aftersale_id}", response_model=dict, summary="撤销售后工单")
async def cancel_aftersale(
    aftersale_id: str,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.cancel_aftersale(consumer_id=current_user["id"], aftersale_id=aftersale_id, db=db)
    return {"code": 200, "message": "工单已撤销", "data": None}


# ═══════════════ 评价 ═══════════════

@router.post("/evaluation", response_model=dict, summary="提交评价")
async def create_evaluation(
    request: EvaluationCreateRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.create_evaluation(
        consumer_id=current_user["id"], order_id=request.order_id,
        product_rating=request.product_rating, service_rating=request.service_rating,
        logistics_rating=request.logistics_rating, content=request.content,
        image_urls=request.image_urls, is_anonymous=request.is_anonymous, db=db,
    )
    return {"code": 200, "message": "评价提交成功", "data": result}


@router.get("/evaluation", response_model=dict, summary="查询评价列表")
async def get_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_evaluations(
        consumer_id=current_user["id"], page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/evaluation/{evaluation_id}/reply", response_model=dict, summary="追评")
async def reply_evaluation(
    evaluation_id: str,
    request: dict,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.reply_evaluation(
        evaluation_id=evaluation_id, consumer_id=current_user["id"],
        content=request.get("content", ""), image_urls=request.get("image_urls", []), db=db,
    )
    return {"code": 200, "message": "追评成功", "data": None}


@router.put("/evaluation/{evaluation_id}", response_model=dict, summary="修改评价（CON012）")
async def update_evaluation(
    evaluation_id: str,
    request: EvaluationUpdateRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.update_evaluation(
        evaluation_id=evaluation_id, consumer_id=current_user["id"],
        product_rating=request.product_rating, service_rating=request.service_rating,
        logistics_rating=request.logistics_rating, content=request.content, db=db,
    )
    return {"code": 200, "message": "评价已更新", "data": result}


@router.get("/evaluation/pending", response_model=dict, summary="查询待评价订单")
async def get_pending_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    items, total = await service.get_pending_evaluations(
        consumer_id=current_user["id"], page=page, page_size=page_size, db=db,
    )
    return {"code": 200, "message": "查询成功", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# ═══════════════ 个人资料 ═══════════════

@router.get("/profile", response_model=dict, summary="查询个人资料")
async def get_profile(
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.get_profile(consumer_id=current_user["id"], db=db)
    return {"code": 200, "message": "查询成功", "data": result}


@router.put("/profile", response_model=dict, summary="更新个人资料")
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    result = await service.update_profile(
        consumer_id=current_user["id"], nickname=request.nickname, avatar=request.avatar, db=db,
    )
    return {"code": 200, "message": "更新成功", "data": result}


@router.post("/bind-phone", response_model=dict, summary="绑定手机号")
async def bind_phone(
    request: BindPhoneRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.bind_phone(
        consumer_id=current_user["id"], phone=request.phone, sms_code=request.sms_code, db=db,
    )
    return {"code": 200, "message": "绑定成功", "data": None}


@router.post("/link-platform", response_model=dict, summary="关联平台账号")
async def link_platform(
    request: LinkPlatformRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.link_platform(
        consumer_id=current_user["id"], platform=request.platform, account=request.account, db=db,
    )
    return {"code": 200, "message": "关联成功", "data": None}


@router.post("/feedback", response_model=dict, summary="提交意见反馈")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
    service: ConsumerService = Depends(),
):
    await service.submit_feedback(
        consumer_id=current_user["id"], content=request.content, feedback_type=request.type, db=db,
    )
    return {"code": 200, "message": "反馈提交成功", "data": None}


# ═══════════════ 消息通知 ═══════════════

from app.services.notification_service import NotificationService


@router.get("/notifications", response_model=dict, summary="查询通知列表")
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
):
    result = await NotificationService.get_notifications(
        db=db, recipient_id=current_user["id"],
        recipient_type="consumer", page=page, page_size=page_size,
    )
    return {"code": 200, "message": "查询成功", "data": result}


@router.get("/notifications/unread-count", response_model=dict, summary="未读通知数")
async def get_unread_notification_count(
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
):
    count = await NotificationService.get_unread_count(
        db=db, recipient_id=current_user["id"], recipient_type="consumer",
    )
    return {"code": 200, "message": "ok", "data": {"count": count}}


@router.put("/notifications/{notification_id}/read", response_model=dict, summary="标记单条已读")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
):
    await NotificationService.mark_read(db=db, notification_id=notification_id)
    return {"code": 200, "message": "已标记", "data": None}


@router.put("/notifications/read-all", response_model=dict, summary="全部已读")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_consumer),
    db: AsyncSession = Depends(get_db),
):
    await NotificationService.mark_all_read(
        db=db, recipient_id=current_user["id"], recipient_type="consumer",
    )
    return {"code": 200, "message": "已全部标记", "data": None}
