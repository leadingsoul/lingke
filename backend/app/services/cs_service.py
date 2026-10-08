"""CSService — 客服端聚合服务，封装 ChatService + TicketService + 工作台/绩效/操作记录"""

import uuid
import logging
from datetime import datetime, timezone
from app.utils import format_dt

from sqlalchemy import select, func, desc, insert, text, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat_models import Conversation, Message, SessionSummary, SatisfactionFeedback, ServiceRecord
from app.models.aftersale_models import AfterSaleOrder
from app.models.notification_models import Notification
from app.models.user_models import Consumer, CustomerServiceStaff
from app.models.product_models import Order, OrderDetail
from app.api.v1.router_ws import manager

# AI 引擎（客服端直接使用，不绕 ChatService）
from ai_engine.llm_gateway import LLMGateway
from ai_engine.rag_engine import RAGEngine

logger = logging.getLogger(__name__)


# 意图等级 → 固定推荐话术（纯本地降级，不依赖 LLM）
FALLBACK_SUGGESTIONS = {
    "L1": [
        "您好，很高兴为您服务！关于您咨询的问题，我来为您详细解答。",
        "感谢您的咨询，请问还有其他需要帮助的吗？",
        "如需进一步了解，请随时联系我们。",
    ],
    "L2": [
        "您好，我了解您的问题了，请稍等我来为您核实处理。",
        "关于您反馈的情况，我们非常重视，马上为您查询。",
        "请提供一下您的订单号，我帮您查一下具体情况。",
    ],
    "L3": [
        "非常抱歉给您带来了不便，我已经记录了您的问题，会立即优先为您处理。",
        "您的心情我完全理解，作为客服我会尽快帮您解决。请问可以描述一下更多细节吗？",
        "我们对此给您带来的困扰深表歉意。请放心，我会全程跟进您的问题直到解决。",
    ],
}


class CSService:
    """客服端聚合服务"""

    # 类级别 RAG 引擎（懒加载）
    _rag_engine: RAGEngine | None = None

    def __init__(self, db=None):
        self.db = db

    @classmethod
    def _get_rag(cls) -> RAGEngine:
        """懒加载 RAG 引擎"""
        if cls._rag_engine is None:
            try:
                cls._rag_engine = RAGEngine(gateway=LLMGateway.from_env())
            except Exception:
                cls._rag_engine = RAGEngine(gateway=None)
        return cls._rag_engine

    # ═══════════════ 工作台 ═══════════════

    async def get_dashboard(self, staff_id: str, db: AsyncSession = None) -> dict:
        db = db or self.db

        # ── 统计卡 ──
        pending_conv_result = await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.status.in_(["AI进行中", "待客服接手", "客服处理中"])
            )
        )
        pending_ticket_result = await db.execute(
            select(func.count(AfterSaleOrder.id)).where(
                AfterSaleOrder.aso_status == "待审核"
            )
        )

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_processed_result = await db.execute(
            select(func.count(ServiceRecord.id)).where(
                ServiceRecord.staff_id == staff_id,
                ServiceRecord.created_at >= today_start,
            )
        )

        # ── 平均响应时间 (first-response: consumer 首条 → staff 首条, per conversation) ──
        avg_time_sql = text("""
            SELECT AVG(TIMESTAMPDIFF(SECOND, first_consumer.created_at, first_staff.created_at))
            FROM (
                SELECT conversation_id, MIN(created_at) AS created_at
                FROM message
                WHERE sender_type = 'consumer'
                GROUP BY conversation_id
            ) first_consumer
            INNER JOIN (
                SELECT conversation_id, MIN(created_at) AS created_at
                FROM message
                WHERE sender_type = 'staff'
                GROUP BY conversation_id
            ) first_staff
                ON first_staff.conversation_id = first_consumer.conversation_id
            WHERE first_staff.created_at > first_consumer.created_at
        """)
        avg_result = await db.execute(avg_time_sql)
        avg_seconds = avg_result.scalar() or 0

        if avg_seconds < 60:
            avg_response_str = f"{int(avg_seconds)}秒"
        elif avg_seconds < 3600:
            avg_response_str = f"{avg_seconds / 60:.1f}分钟"
        else:
            avg_response_str = f"{avg_seconds / 3600:.1f}小时"

        # ── 紧急会话列表 (JOIN Consumer.nickname + Message.content) ──
        urgent_conv_raw = await db.execute(
            select(Conversation).where(
                Conversation.status.in_(["AI进行中", "待客服接手", "客服处理中"])
            ).order_by(Conversation.updated_at.desc()).limit(5)
        )
        urgent_conv = []
        for c in urgent_conv_raw.scalars().all():
            # username from Consumer
            consumer_result = await db.execute(
                select(Consumer.nickname).where(Consumer.id == c.consumer_id)
            )
            nickname = consumer_result.scalar() or f"用户{c.consumer_id[:6]}"

            # last_message from Message
            last_msg_result = await db.execute(
                select(Message.content).where(
                    Message.conversation_id == c.id
                ).order_by(Message.created_at.desc()).limit(1)
            )
            last_msg = last_msg_result.scalar() or ""

            urgent_conv.append({
                "id": c.id,
                "username": nickname,
                "last_message": last_msg,
                "intent_level": c.intent_level if hasattr(c, 'intent_level') else "L1",
                "urgency": "high" if (c.intent_level == "L3") else ("medium" if c.intent_level == "L2" else "low"),
                "priority": c.priority if hasattr(c, 'priority') else "普通",
                "created_at": format_dt(c.created_at) or "",
            })

        # ── 待审核工单列表 (JOIN Consumer.nickname as applicant) ──
        pending_tickets_raw = await db.execute(
            select(AfterSaleOrder).where(
                AfterSaleOrder.aso_status == "待审核"
            ).order_by(AfterSaleOrder.created_at.desc()).limit(5)
        )
        pending_ticket_list = []
        for t in pending_tickets_raw.scalars().all():
            consumer_result = await db.execute(
                select(Consumer.nickname).where(Consumer.id == t.consumer_id)
            )
            applicant = consumer_result.scalar() or f"用户{t.consumer_id[:6]}"

            pending_ticket_list.append({
                "id": t.id,
                "ticket_no": f"ASO-{t.id[:8].upper()}",
                "type": t.aso_type,
                "urgency": t.urgency,
                "status": t.aso_status,
                "applicant": applicant,
                "description": t.description or t.aso_reason,
                "created_at": format_dt(t.created_at) or "",
            })

        return {
            "pending_conversations": pending_conv_result.scalar() or 0,
            "pending_tickets": pending_ticket_result.scalar() or 0,
            "today_processed": today_processed_result.scalar() or 0,
            "avg_response_time": avg_response_str,
            "urgent_conversations": urgent_conv,
            "pending_ticket_list": pending_ticket_list,
        }

    # ═══════════════ 会话 ═══════════════

    async def get_conversations(
        self, staff_id: str, status: str = None, priority: str = None,
        keyword: str = None,
        page: int = 1, page_size: int = 10, db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(Conversation)
        count_query = select(func.count(Conversation.id))

        if status:
            base_query = base_query.where(Conversation.status == status)
            count_query = count_query.where(Conversation.status == status)
        if priority:
            base_query = base_query.where(Conversation.priority == priority)
            count_query = count_query.where(Conversation.priority == priority)
        if keyword:
            # 搜索消费者名称（JOIN Consumer 表）
            kw_pattern = f"%{keyword}%"
            base_query = base_query.join(Consumer, Conversation.consumer_id == Consumer.id).where(
                Consumer.nickname.ilike(kw_pattern)
            )
            count_query = count_query.join(Consumer, Conversation.consumer_id == Consumer.id).where(
                Consumer.nickname.ilike(kw_pattern)
            )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        # 状态排序权重：需人工的排最前
        status_priority = case(
            (Conversation.status == "待客服接手", 1),
            (Conversation.status == "待客服确认", 2),
            (Conversation.status == "AI进行中", 3),
            (Conversation.status == "客服处理中", 4),
            else_=5,
        )
        # 需人工介入的会话：按 oldest-first 排序（等待越久越靠前）；其余按 newest-first
        human_needed = Conversation.status.in_(["待客服接手", "待客服确认"])
        human_updated_asc = case(
            (human_needed, Conversation.updated_at),
            else_=None,
        )
        # MySQL 不支持 NULLS LAST，拆成两步：先按 IS NULL 排序（NULL 排最后）
        result = await db.execute(
            base_query.order_by(
                status_priority,
                human_updated_asc.is_(None),          # NULL → 1（排最后），有值 → 0
                human_updated_asc.asc(),               # 非 NULL 的按 updated_at 升序
                Conversation.updated_at.desc(),
            ).offset(offset).limit(page_size)
        )
        items = []
        conv_list = list(result.scalars().all())

        # Batch load last messages (avoid N+1 per conversation)
        last_msg_map: dict[str, str] = {}
        if conv_list:
            conv_ids = [c.id for c in conv_list]
            # Subquery: last message per conversation
            from sqlalchemy import and_
            last_msg_subq = (
                select(
                    Message.conversation_id,
                    Message.content,
                )
                .where(Message.conversation_id.in_(conv_ids))
                .order_by(Message.created_at.desc())
                .subquery()
            )
            # Use DISTINCT ON pattern — just fetch latest per conv_id manually
            for cid in conv_ids:
                lm_result = await db.execute(
                    select(Message.content)
                    .where(Message.conversation_id == cid)
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                row = lm_result.scalar()
                if row:
                    last_msg_map[cid] = row[:80] if len(row) > 80 else row

        for c in conv_list:
            # Query actual consumer name from Consumer table
            consumer_name = ""
            try:
                cons_result = await db.execute(
                    select(Consumer).where(Consumer.id == c.consumer_id)
                )
                cons = cons_result.scalar_one_or_none()
                consumer_name = getattr(cons, "nickname", None) or getattr(cons, "name", None) or ""
            except Exception:
                pass
            if not consumer_name:
                consumer_name = str(c.consumer_id)[:12]

            # 可读会话标识：优先显示商品名 → 用户昵称 + 日期时间
            product_label = ""
            if c.order_id:
                od_result = await db.execute(
                    select(Order).options(selectinload(Order.details)).where(Order.id == c.order_id)
                )
                order_obj = od_result.scalar()
                if order_obj and order_obj.details:
                    product_label = order_obj.details[0].product_name[:20]

            c_time = c.created_at or c.updated_at
            date_part = ""
            if c_time:
                try:
                    from datetime import timezone as _tz
                    utc_now = datetime.now(_tz.utc)
                    ct = c_time.replace(tzinfo=_tz.utc) if c_time.tzinfo is None else c_time
                    diff = utc_now - ct
                    if diff.days == 0:
                        date_part = c_time.strftime("%H:%M")
                    elif diff.days == 1:
                        date_part = "昨天 " + c_time.strftime("%H:%M")
                    else:
                        date_part = c_time.strftime("%m-%d %H:%M")
                except Exception:
                    date_part = ""

            # 构建 display_label：商品名优先
            parts = [p for p in [product_label, consumer_name, date_part] if p]
            display_label = " · ".join(parts) if parts else c.id[:8]

            items.append({
                "id": c.id,
                "consumer_name": consumer_name,
                "display_label": display_label,
                "consumer_avatar": None,
                "last_message": last_msg_map.get(c.id, ""),
                "status": c.status,
                "intent_level": getattr(c, "intent_level", "L1"),
                "priority": getattr(c, "priority", "普通"),
                "message_count": getattr(c, "message_count", 0),
                "unread_count": 0,
                "created_at": format_dt(c.created_at) or "",
                "updated_at": format_dt(c.updated_at) or "",
            })
        return items, total

    async def get_conversation_detail(self, conversation_id: str, db: AsyncSession = None) -> dict:
        db = db or self.db
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        c = result.scalar_one_or_none()
        if c is None:
            return {}

        # Query actual consumer name
        consumer_name = ""
        try:
            cons_result = await db.execute(
                select(Consumer).where(Consumer.id == c.consumer_id)
            )
            cons = cons_result.scalar_one_or_none()
            consumer_name = getattr(cons, "nickname", None) or getattr(cons, "name", None) or str(c.consumer_id)[:12]
        except Exception:
            consumer_name = str(c.consumer_id)[:12]

        # Fetch associated order info if exists
        order_status = None
        order_amount = 0
        if c.order_id:
            order_result = await db.execute(
                select(Order).where(Order.id == c.order_id)
            )
            order = order_result.scalar_one_or_none()
            if order:
                order_status = order.status
                order_amount = float(order.total_amount or 0)

        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = []
        pending_draft = None
        for m in msg_result.scalars().all():
            # ai_draft 单独提取，不在消息流中展示（对齐 ChatService）
            if getattr(m, "sender_type", None) == "ai_draft":
                pending_draft = {
                    "id": m.id,
                    "content": m.content,
                    "ai_metadata": m.ai_metadata if hasattr(m, "ai_metadata") else None,
                    "created_at": format_dt(m.created_at) or "",
                }
                continue
            messages.append({
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type if hasattr(m, 'msg_type') else "text",
                "content": m.content,
                "image_urls": m.image_urls,
                "ai_metadata": m.ai_metadata,
                "created_at": format_dt(m.created_at) or "",
            })

        # 生成 AI 推荐回复（根据最近对话上下文动态生成）
        logger.info(f"[CSService] 开始生成 AI 建议，会话={conversation_id}，消息数={len(messages)}")
        rag = self._get_rag()
        ai_suggestions = rag._fallback_suggestions(getattr(c, "intent_level", "L1"))
        try:
            recent_texts = [
                f"[{m.get('sender_type', '')}] {m.get('content', '')}"
                for m in messages[-10:]
            ]
            # 注入订单上下文
            order_context = ""
            if c.order_id and order_status:
                try:
                    detail_result = await db.execute(
                        select(OrderDetail).where(OrderDetail.order_id == c.order_id).limit(1)
                    )
                    detail = detail_result.scalar_one_or_none()
                    order_context = f"用户购买的商品是「{detail.product_name if detail else '未知'}」"
                except Exception:
                    pass
            logger.info(f"[CSService] 调用 RAG suggest_replies, intent={getattr(c, 'intent_level', 'L1')}")
            ai_suggestions = rag.suggest_replies(
                recent_messages=recent_texts,
                intent_level=getattr(c, "intent_level", "L1"),
                priority=getattr(c, "priority", "普通"),
                order_context=order_context,
            )
            logger.info(f"[CSService] AI 建议生成成功，{len(ai_suggestions)} 条")
        except Exception as e:
            logger.warning(f"[CSService] AI 建议生成失败：{e}，使用降级话术")
            # ai_suggestions 已在 try 前初始化为 _fallback_suggestions，异常时保持不变

        return {
            "id": c.id,
            "consumer_id": c.consumer_id,
            "consumer_name": consumer_name,
            "consumer_avatar": None,
            "order_id": c.order_id,
            "order_status": order_status,
            "order_amount": order_amount,
            "customer_tags": [],
            "status": c.status,
            "intent_level": getattr(c, "intent_level", "L1"),
            "priority": getattr(c, "priority", "普通"),
            "messages": messages,
            "pending_draft": pending_draft,
            "ai_suggestions": ai_suggestions,
            "created_at": format_dt(c.created_at) or "",
        }

    async def get_conversation_messages(
        self, conversation_id: str, page: int = 1, page_size: int = 50, db: AsyncSession = None,
    ) -> tuple:
        """获取会话的消息列表（分页）"""
        db = db or self.db
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        all_messages = []
        for m in msg_result.scalars().all():
            # ai_draft 不在普通消息流中展示（对齐 ChatService）
            if getattr(m, "sender_type", None) == "ai_draft":
                continue
            all_messages.append({
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type if hasattr(m, 'msg_type') else "text",
                "content": m.content,
                "image_urls": m.image_urls,
                "ai_metadata": m.ai_metadata,
                "created_at": format_dt(m.created_at) or "",
            })

        total = len(all_messages)
        start = (page - 1) * page_size
        end = start + page_size
        return all_messages[start:end], total

    async def reply_conversation(
        self, conversation_id: str, staff_id: str, content: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        msg = Message(
            id=str(uuid.uuid4()).replace("-", "")[:12],
            conversation_id=conversation_id,
            sender_type="staff",
            sender_id=staff_id,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.flush()

        # Update conversation timestamp and message count
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            # 首次接手：状态从"待客服接手/待客服确认/AI进行中"→"客服处理中"
            if conv.status in ("待客服接手", "待客服确认", "AI进行中"):
                conv.status = "客服处理中"
            # 分配客服（如果尚未分配）
            if conv.staff_id is None:
                conv.staff_id = staff_id
            conv.message_count = (conv.message_count or 0) + 1
            conv.updated_at = datetime.now(timezone.utc)

        # 删除该会话的 ai_draft 消息（客服已回复 = 已审批，草稿应消失）
        drafts = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.sender_type == "ai_draft",
            )
        )
        for draft in drafts.scalars().all():
            await db.delete(draft)

        # Create service record
        record = ServiceRecord(
            id=str(uuid.uuid4()).replace("-", "")[:12],
            target_type="conversation",
            target_id=conversation_id,
            staff_id=staff_id,
            action="reply",
        )
        db.add(record)
        await db.flush()

        return {"message_id": msg.id, "content": content}

    async def close_conversation(
        self, conversation_id: str, staff_id: str, db: AsyncSession = None,
    ):
        db = db or self.db
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            conv.status = "已关闭"
            conv.staff_id = staff_id
            conv.closed_at = datetime.now(timezone.utc)
            conv.updated_at = datetime.now(timezone.utc)
            await db.flush()

            # G3: 会话关闭后生成 LLM 沉淀文档
            from app.services.evolution_service import EvolutionService
            try:
                staff_name = "客服"
                staff_result = await db.execute(
                    select(CustomerServiceStaff).where(CustomerServiceStaff.id == staff_id)
                )
                staff = staff_result.scalar_one_or_none()
                if staff and staff.name:
                    staff_name = staff.name
                await EvolutionService.generate_session_summary(
                    db=db, conversation_id=conversation_id, staff_name=staff_name,
                )
            except Exception as e:
                logger.warning(f"[G3] Session summary generation failed (non-fatal): {e}")

        # 记录服务操作
        record = ServiceRecord(
            id=str(uuid.uuid4()).replace("-", "")[:12],
            target_type="conversation",
            target_id=conversation_id,
            staff_id=staff_id,
            action="关闭",
        )
        db.add(record)

    async def delete_conversation(
        self, conversation_id: str, staff_id: str, db: AsyncSession = None,
    ):
        """硬删除会话及其所有关联数据"""
        db = db or self.db

        # 1. 级联删除子记录（FK 无 ON DELETE CASCADE，需手动删除）
        # Messages
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
        )
        for m in msg_result.scalars().all():
            await db.delete(m)

        # SessionSummary
        summary_result = await db.execute(
            select(SessionSummary).where(SessionSummary.conversation_id == conversation_id)
        )
        for s in summary_result.scalars().all():
            await db.delete(s)

        # SatisfactionFeedback
        fb_result = await db.execute(
            select(SatisfactionFeedback).where(SatisfactionFeedback.conversation_id == conversation_id)
        )
        for fb in fb_result.scalars().all():
            await db.delete(fb)

        # ServiceRecord（string target_id，非 FK，清理保持数据卫生）
        sr_result = await db.execute(
            select(ServiceRecord).where(
                ServiceRecord.target_type == "conversation",
                ServiceRecord.target_id == conversation_id,
            )
        )
        for sr in sr_result.scalars().all():
            await db.delete(sr)

        # 2. 删除会话本身
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            await db.delete(conv)

        # 3. 创建一条审计记录（孤立记录，记录删除操作本身）
        record = ServiceRecord(
            id=str(uuid.uuid4()).replace("-", "")[:12],
            target_type="conversation",
            target_id=conversation_id,
            staff_id=staff_id,
            action="删除",
        )
        db.add(record)
        await db.flush()

    # ═══════════════ 工单 ═══════════════

    async def get_tickets(
        self, aso_type: str = None, aso_status: str = None,
        urgency: str = None, keyword: str = None,
        page: int = 1, page_size: int = 10, db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(AfterSaleOrder)
        count_query = select(func.count(AfterSaleOrder.id))

        if aso_type:
            base_query = base_query.where(AfterSaleOrder.aso_type == aso_type)
            count_query = count_query.where(AfterSaleOrder.aso_type == aso_type)
        if aso_status:
            base_query = base_query.where(AfterSaleOrder.aso_status == aso_status)
            count_query = count_query.where(AfterSaleOrder.aso_status == aso_status)
        if urgency:
            base_query = base_query.where(AfterSaleOrder.urgency == urgency)
            count_query = count_query.where(AfterSaleOrder.urgency == urgency)
        if keyword:
            from sqlalchemy import or_
            kw = f"%{keyword}%"
            base_query = base_query.outerjoin(
                Consumer, AfterSaleOrder.consumer_id == Consumer.id
            ).where(
                or_(
                    AfterSaleOrder.description.ilike(kw),
                    Consumer.nickname.ilike(kw),
                )
            )
            count_query = count_query.outerjoin(
                Consumer, AfterSaleOrder.consumer_id == Consumer.id
            ).where(
                or_(
                    AfterSaleOrder.description.ilike(kw),
                    Consumer.nickname.ilike(kw),
                )
            )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(AfterSaleOrder.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        ticket_list = list(result.scalars().all())

        # Batch resolve consumer names & handler names
        consumer_name_map: dict[str, str] = {}
        handler_name_map: dict[str, str] = {}
        if ticket_list:
            consumer_ids = list({t.consumer_id for t in ticket_list if hasattr(t, 'consumer_id') and t.consumer_id})
            handler_ids = list({t.handler_id for t in ticket_list if getattr(t, 'handler_id', None)})
            if consumer_ids:
                cons_result = await db.execute(
                    select(Consumer.id, Consumer.nickname).where(Consumer.id.in_(consumer_ids))
                )
                for row in cons_result.all():
                    cid, nickname = row
                    consumer_name_map[cid] = nickname or cid[:8]
            if handler_ids:
                staff_result = await db.execute(
                    select(CustomerServiceStaff.id, CustomerServiceStaff.name).where(
                        CustomerServiceStaff.id.in_(handler_ids)
                    )
                )
                for row in staff_result.all():
                    hid, name = row
                    handler_name_map[hid] = name

        for t in ticket_list:
            cname = consumer_name_map.get(getattr(t, 'consumer_id', ''), str(getattr(t, 'consumer_id', ''))[:8])
            handler_name = handler_name_map.get(getattr(t, 'handler_id', None), None)
            items.append({
                "id": t.id,
                "ticket_no": "TK" + t.id[:10].upper(),
                "order_id": t.order_id,
                "consumer_name": cname,
                "aso_type": t.aso_type,
                "aso_reason": t.aso_reason or "",
                "aso_status": t.aso_status,
                "urgency": t.urgency,
                "responsibility": t.responsibility,
                "assigned_to": handler_name,
                "description": t.description[:100] if t.description else "",
                "created_at": format_dt(t.created_at) or "",
                "updated_at": format_dt(t.updated_at) or "",
            })
        return items, total

    async def batch_assign_tickets(
        self, ticket_ids: list[str], staff_id: str, db: AsyncSession = None,
    ) -> dict:
        """批量分配工单给指定客服（更新 handler_id）"""
        db = db or self.db

        # 验证 staff 存在
        staff_result = await db.execute(
            select(CustomerServiceStaff).where(CustomerServiceStaff.id == staff_id)
        )
        staff = staff_result.scalar_one_or_none()
        if staff is None:
            raise HTTPException(status_code=400, detail="客服不存在")

        now = datetime.now(timezone.utc)
        updated = 0
        for tid in ticket_ids:
            result = await db.execute(
                select(AfterSaleOrder).where(AfterSaleOrder.id == tid)
            )
            t = result.scalar_one_or_none()
            if t is None:
                continue
            t.handler_id = staff_id
            t.updated_at = now
            updated += 1

        await db.flush()
        return {"assigned_count": updated, "staff_name": staff.name}

    async def get_ticket_detail(self, ticket_id: str, db: AsyncSession = None) -> dict:
        db = db or self.db
        result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return {}

        # Resolve handler name
        handler_name = None
        if t.handler_id:
            staff_result = await db.execute(
                select(CustomerServiceStaff).where(CustomerServiceStaff.id == t.handler_id)
            )
            staff = staff_result.scalar_one_or_none()
            handler_name = staff.name if staff else None

        return {
            "id": t.id,
            "order_id": t.order_id,
            "consumer_id": getattr(t, "consumer_id", ""),
            "consumer_name": str(getattr(t, "consumer_id", ""))[:12],
            "order_info": None,
            "aso_type": t.aso_type,
            "aso_reason": t.aso_reason or "",
            "description": t.description,
            "evidence_urls": t.evidence_urls or [],
            "aso_status": t.aso_status,
            "urgency": t.urgency,
            "responsibility": t.responsibility,
            "suggested_action": getattr(t, "suggested_action", ""),
            "review_opinion": t.review_opinion,
            "handler_id": t.handler_id,
            "handler_name": handler_name,
            "custom_tags": t.custom_tags or [],
            "created_at": format_dt(t.created_at) or "",
            "updated_at": format_dt(t.updated_at) or "",
            "timeline": [],
        }

    async def review_ticket(
        self, ticket_id: str, staff_id: str, result: str, opinion: str = None,
        db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        res = await db.execute(select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id))
        t = res.scalar_one_or_none()
        if t:
            t.review_opinion = opinion
            t.handler_id = staff_id
            t.updated_at = datetime.now(timezone.utc)
            if result == "通过":
                t.aso_status = "审核通过"
            elif result == "拒绝":
                t.aso_status = "已拒绝"
            await db.flush()

            # 创建消费者通知 + WebSocket 推送
            if result in ("通过", "拒绝") and hasattr(t, "consumer_id") and t.consumer_id:
                status_label = "审核通过 ✅" if result == "通过" else "已拒绝 ❌"
                notif_id = uuid.uuid4().hex
                await db.execute(
                    insert(Notification).values(
                        id=notif_id,
                        recipient_id=t.consumer_id,
                        recipient_type="consumer",
                        type="aftersale",
                        title=f"售后工单已{status_label}",
                        content=f"您提交的售后申请已被客服{status_label}。",
                        is_read=0,
                    )
                )
                try:
                    await manager.send_personal(
                        {"event": "system_notice", "data": {"type": "aftersale", "title": f"售后工单已{status_label}"}, "timestamp": None},
                        t.consumer_id,
                    )
                except Exception:
                    pass
        return {"ticket_id": ticket_id, "result": result}

    async def supplement_ticket(
        self, ticket_id: str, staff_id: str, note: str, db: AsyncSession = None,
    ):
        db = db or self.db
        # Supplement just adds a note, could be extended to notification
        pass

    async def complete_ticket(
        self, ticket_id: str, staff_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        res = await db.execute(select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id))
        t = res.scalar_one_or_none()
        if t:
            t.aso_status = "已完成"
            t.updated_at = datetime.now(timezone.utc)
            await db.flush()

            # 创建消费者通知 + WebSocket 推送
            if hasattr(t, "consumer_id") and t.consumer_id:
                notif_id = uuid.uuid4().hex
                await db.execute(
                    insert(Notification).values(
                        id=notif_id,
                        recipient_id=t.consumer_id,
                        recipient_type="consumer",
                        type="aftersale",
                        title="售后工单已完成",
                        content="您提交的售后申请已处理完成。如有疑问请联系客服。",
                        is_read=0,
                    )
                )
                try:
                    await manager.send_personal(
                        {"event": "system_notice", "data": {"type": "aftersale", "title": "售后工单已完成"}, "timestamp": None},
                        t.consumer_id,
                    )
                except Exception:
                    pass
        return {"ticket_id": ticket_id, "status": "已完成"}

    async def tag_ticket(
        self, ticket_id: str, staff_id: str, tag: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        res = await db.execute(select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id))
        t = res.scalar_one_or_none()
        if t:
            tags = list(t.custom_tags or [])
            if tag not in tags:
                tags.append(tag)
            t.custom_tags = tags
            t.updated_at = datetime.now(timezone.utc)
            await db.flush()
        return {"ticket_id": ticket_id, "tags": tags}

    # ═══════════════ 统计 ═══════════════

    async def get_category_stats(self, db: AsyncSession = None) -> list:
        db = db or self.db
        result = await db.execute(
            select(AfterSaleOrder.aso_type, func.count(AfterSaleOrder.id))
            .group_by(AfterSaleOrder.aso_type)
        )
        total = 0
        rows = []
        for rtype, cnt in result.all():
            rows.append((rtype, cnt))
            total += cnt

        stats = []
        for rtype, cnt in rows:
            stats.append({
                "category": rtype,
                "count": cnt,
                "percentage": round(cnt / total * 100, 1) if total > 0 else 0,
            })
        return stats

    async def get_performance(self, staff_id: str, db: AsyncSession = None) -> dict:
        db = db or self.db
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # 今日各维度处理量
        base_filter = (ServiceRecord.staff_id == staff_id, ServiceRecord.created_at >= today_start)
        today_handled = (await db.execute(select(func.count(ServiceRecord.id)).where(*base_filter))).scalar() or 0
        today_replies = (await db.execute(
            select(func.count(ServiceRecord.id)).where(*base_filter, ServiceRecord.action == "回复")
        )).scalar() or 0
        today_reviews = (await db.execute(
            select(func.count(ServiceRecord.id)).where(*base_filter, ServiceRecord.action == "审核")
        )).scalar() or 0

        # 全部历史累计
        total_handled = (await db.execute(
            select(func.count(ServiceRecord.id)).where(ServiceRecord.staff_id == staff_id)
        )).scalar() or 0

        # 平均响应时间（此客服处理的会话中，consumer首条→staff首条平均秒差）
        avg_time_sql = text("""
            SELECT AVG(TIMESTAMPDIFF(SECOND, first_consumer.created_at, first_staff.created_at))
            FROM (
                SELECT m1.conversation_id, MIN(m1.created_at) AS created_at
                FROM message m1
                INNER JOIN conversation c ON c.id = m1.conversation_id
                WHERE m1.sender_type = 'consumer' AND c.staff_id = :staff_id
                GROUP BY m1.conversation_id
            ) first_consumer
            INNER JOIN (
                SELECT m2.conversation_id, MIN(m2.created_at) AS created_at
                FROM message m2
                WHERE m2.sender_type = 'staff' AND m2.sender_id = :staff_id2
                GROUP BY m2.conversation_id
            ) first_staff
                ON first_staff.conversation_id = first_consumer.conversation_id
            WHERE first_staff.created_at > first_consumer.created_at
        """)
        avg_secs = (await db.execute(avg_time_sql, {"staff_id": staff_id, "staff_id2": staff_id})).scalar() or 0
        if avg_secs < 60:
            avg_response_str = f"{int(avg_secs)}秒"
        elif avg_secs < 3600:
            avg_response_str = f"{avg_secs / 60:.1f}分钟"
        else:
            avg_response_str = f"{avg_secs / 3600:.1f}小时"

        # 满意度（此客服处理过的会话的评分平均）
        sat_result = await db.execute(
            select(func.avg(SatisfactionFeedback.rating), func.count(SatisfactionFeedback.id))
            .select_from(SatisfactionFeedback)
            .join(Conversation, SatisfactionFeedback.conversation_id == Conversation.id)
            .where(Conversation.staff_id == staff_id)
        )
        sat_row = sat_result.one_or_none()
        sat_avg = float(sat_row[0]) if sat_row and sat_row[0] else 0.0
        sat_count = sat_row[1] if sat_row else 0

        # 处理过的会话数
        conv_count = (await db.execute(
            select(func.count(Conversation.id)).where(Conversation.staff_id == staff_id)
        )).scalar() or 0

        return {
            "today_handled": today_handled,
            "today_replies": today_replies,
            "today_reviews": today_reviews,
            "total_handled": total_handled,
            "total_conversations": conv_count,
            "avg_response_time": avg_response_str,
            "satisfaction_rate": round(sat_avg, 1),
            "satisfaction_count": sat_count,
        }

    async def get_operation_records(
        self, staff_id: str, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(ServiceRecord).where(ServiceRecord.staff_id == staff_id)
        count_query = select(func.count(ServiceRecord.id)).where(ServiceRecord.staff_id == staff_id)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(ServiceRecord.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for r in result.scalars().all():
            items.append({
                "id": r.id,
                "staff_id": staff_id,
                "action": r.action,
                "target_type": "conversation",
                "target_id": r.conversation_id,
                "detail": "",
                "created_at": format_dt(r.created_at) or "",
            })
        return items, total
