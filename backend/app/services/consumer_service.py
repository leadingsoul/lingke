"""ConsumerService — 消费者端服务：订单 / 个人资料"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import encrypt_phone, mask_phone
from app.models.product_models import Order, OrderDetail, Product
from app.models.aftersale_models import AfterSaleOrder
from app.models.evaluation_models import Evaluation, EvaluationReply
from app.models.user_models import Consumer
from app.models.chat_models import Conversation, Message, SatisfactionFeedback


class ConsumerService:
    """消费者服务：订单查询 / 个人资料 / 手机绑定 / 平台关联"""

    def __init__(self, db=None):
        self.db = db

    # ── 订单列表 ──────────────────────────────────────

    async def get_orders(
        self,
        consumer_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        base_query = (
            select(Order)
            .options(selectinload(Order.details))
            .where(Order.consumer_id == consumer_id)
        )
        count_query = (
            select(func.count(Order.id))
            .where(Order.consumer_id == consumer_id)
        )

        if status:
            base_query = base_query.where(Order.status == status)
            count_query = count_query.where(Order.status == status)

        if keyword:
            sub = (
                select(OrderDetail.order_id)
                .where(OrderDetail.product_name.ilike(f"%{keyword}%"))
                .distinct()
                .subquery()
            )
            base_query = base_query.where(Order.id.in_(select(sub.c.order_id)))
            count_query = count_query.where(Order.id.in_(select(sub.c.order_id)))

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(Order.created_at.desc()).offset(offset).limit(page_size)
        )
        orders = result.unique().scalars().all()

        items = []
        for order in orders:
            first_detail = order.details[0] if order.details else None
            product_name = first_detail.product_name if first_detail else ""
            product_image = first_detail.product_image if first_detail else None
            aso_result = await db.execute(
                select(func.count(AfterSaleOrder.id)).where(
                    AfterSaleOrder.order_id == order.id,
                    AfterSaleOrder.aso_status.in_(["待审核", "审核通过", "处理中"]),
                )
            )
            active_aso_count = aso_result.scalar() or 0
            can_aftersale = order.status not in ("待付款", "已关闭") and active_aso_count == 0

            items.append({
                "id": order.id,
                "order_no": order.id,
                "product_name": product_name,
                "product_image": product_image,
                "price": float(first_detail.unit_price) if first_detail else 0,
                "quantity": first_detail.quantity if first_detail else 0,
                "total_amount": float(order.total_amount),
                "status": order.status,
                "status_text": order.status,
                "platform": None,
                "shop_name": None,
                "created_at": str(order.created_at) if order.created_at else "",
                "can_aftersale": can_aftersale,
            })

        return items, total

    # ── 订单详情 ──────────────────────────────────────

    async def get_order_detail(
        self, consumer_id: str, order_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.details))
            .where(Order.id == order_id, Order.consumer_id == consumer_id)
        )
        order = result.unique().scalar_one_or_none()

        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在或无权访问")
        if not order.details:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单详情缺失")

        first_detail = order.details[0]

        aso_result = await db.execute(
            select(AfterSaleOrder)
            .where(AfterSaleOrder.order_id == order_id)
            .order_by(AfterSaleOrder.created_at.desc())
            .limit(1)
        )
        aso = aso_result.scalar_one_or_none()

        eval_result = await db.execute(
            select(func.count(Evaluation.id)).where(
                Evaluation.order_id == order_id, Evaluation.consumer_id == consumer_id,
            )
        )
        has_eval = (eval_result.scalar() or 0) > 0

        active_aso = aso and aso.aso_status not in ("已撤销", "已完成", "已拒绝")

        return {
            "id": order.id,
            "order_no": order.id,
            "platform": None,
            "shop_name": None,
            "product_name": first_detail.product_name,
            "product_image": first_detail.product_image,
            "product_spec": None,
            "price": float(first_detail.unit_price),
            "quantity": first_detail.quantity,
            "total_amount": float(order.total_amount),
            "discount_amount": 0.0,
            "payment_amount": float(order.total_amount),
            "status": order.status,
            "status_text": order.status,
            "logistics": {
                "company": order.logistics_company,
                "tracking_no": order.logistics_no,
                "status": order.status,
                "status_text": order.status,
                "delivery_time": None,
            },
            "aftersale_status": aso.aso_status if aso else None,
            "aftersale_id": aso.id if aso else None,
            "can_aftersale": order.status not in ("待付款", "已关闭") and not active_aso,
            "can_evaluate": order.status == "已完成" and not has_eval,
            "created_at": str(order.created_at) if order.created_at else "",
            "completed_at": None,
        }

    # ── 个人资料 ──────────────────────────────────────

    async def get_profile(self, consumer_id: str, db: AsyncSession = None) -> dict:
        db = db or self.db
        result = await db.execute(select(Consumer).where(Consumer.id == consumer_id))
        consumer = result.scalar_one_or_none()
        if consumer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        phone_display = None
        if consumer.phone:
            try:
                from app.core.security import decrypt_phone
                raw_phone = decrypt_phone(consumer.phone)
                phone_display = mask_phone(raw_phone)
            except Exception:
                phone_display = None

        platforms = []
        if consumer.platform_account:
            try:
                import json
                platforms = json.loads(consumer.platform_account) if isinstance(consumer.platform_account, str) else [consumer.platform_account]
            except Exception:
                platforms = [str(consumer.platform_account)]

        return {
            "id": consumer.id,
            "nickname": consumer.nickname,
            "avatar": consumer.avatar,
            "phone": phone_display,
            "platform_account": consumer.platform_account,
            "level": "普通用户",
            "platforms": platforms,
            "created_at": str(consumer.created_at) if consumer.created_at else "",
        }

    # ── 更新资料 ──────────────────────────────────────

    async def update_profile(
        self, consumer_id: str, nickname: str = None, avatar: str = None,
        db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(select(Consumer).where(Consumer.id == consumer_id))
        consumer = result.scalar_one_or_none()
        if consumer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        if nickname is not None:
            consumer.nickname = nickname
        if avatar is not None:
            consumer.avatar = avatar

        await db.flush()
        return await self.get_profile(consumer_id=consumer_id, db=db)

    # ── 绑定手机 ──────────────────────────────────────

    async def bind_phone(
        self, consumer_id: str, phone: str, sms_code: str,
        db: AsyncSession = None,
    ) -> None:
        db = db or self.db
        # Mock: skip SMS verification for now
        result = await db.execute(select(Consumer).where(Consumer.id == consumer_id))
        consumer = result.scalar_one_or_none()
        if consumer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        consumer.phone = encrypt_phone(phone)
        await db.flush()

    # ── 关联平台账号 ──────────────────────────────────

    async def link_platform(
        self, consumer_id: str, platform: str, account: str,
        db: AsyncSession = None,
    ) -> None:
        db = db or self.db
        result = await db.execute(select(Consumer).where(Consumer.id == consumer_id))
        consumer = result.scalar_one_or_none()
        if consumer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        consumer.platform_account = f"{platform}:{account}"
        await db.flush()

    # ── 创建会话（进页面即创建，不等发消息）──────────

    async def create_conversation(
        self, consumer_id: str, order_id: str | None = None,
        db: AsyncSession = None,
    ) -> dict:
        """创建新的咨询会话（如已有同一订单的活跃会话则复用），返回 session_id"""
        db = db or self.db

        # 同一消费者 + 同一订单 → 复用已有活跃会话
        if order_id:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.consumer_id == consumer_id,
                    Conversation.order_id == order_id,
                    Conversation.status.notin_(["已关闭", "已删除"]),
                ).order_by(Conversation.created_at.desc()).limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return {"session_id": existing.id, "is_existing": True}

        conv = Conversation(
            id=uuid.uuid4().hex,
            consumer_id=consumer_id,
            order_id=order_id,
            status="AI进行中",
            priority="普通",
            message_count=0,
        )
        db.add(conv)
        await db.flush()
        return {"session_id": conv.id, "is_existing": False}

    # ── 查询消费者的会话列表 ──────────────────────────

    async def get_my_conversations(
        self, consumer_id: str, page: int = 1, page_size: int = 20,
        db: AsyncSession = None,
    ):
        """查询某个消费者的所有咨询会话，含商品/订单信息"""
        db = db or self.db
        count_result = await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.consumer_id == consumer_id,
                Conversation.status != "已删除",
            )
        )
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size

        conv_result = await db.execute(
            select(Conversation)
            .where(
                Conversation.consumer_id == consumer_id,
                Conversation.status != "已删除",
            )
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .offset(offset).limit(page_size)
        )
        convs = list(conv_result.scalars().all())

        items = []
        for c in convs:
            # 商品名
            product_name = ""
            if c.order_id:
                od_result = await db.execute(
                    select(OrderDetail).where(OrderDetail.order_id == c.order_id).limit(1)
                )
                detail = od_result.scalar_one_or_none()
                if detail:
                    product_name = detail.product_name

            # 最后一条消息
            last_msg = ""
            last_msg_result = await db.execute(
                select(Message.content)
                .where(Message.conversation_id == c.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            row = last_msg_result.scalar()
            if row:
                last_msg = row[:80]

            items.append({
                "id": c.id,
                "order_id": c.order_id,
                "product_name": product_name,
                "status": c.status,
                "intent_level": getattr(c, "intent_level", None),
                "priority": getattr(c, "priority", "普通"),
                "last_message": last_msg,
                "message_count": c.message_count or 0,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            })

        return items, total

    async def delete_my_conversation(
        self, consumer_id: str, session_id: str, db: AsyncSession = None,
    ):
        """消费者删除自己的某个咨询会话（软删除：标记状态）"""
        db = db or self.db
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == session_id,
                Conversation.consumer_id == consumer_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在或无权操作")
        # 标记为已删除（前端过滤掉）
        conv.status = "已删除"
        await db.flush()

    async def rate_conversation(
        self, consumer_id: str, session_id: str,
        rating: int, feedback: str = None, db: AsyncSession = None,
    ) -> dict:
        """消费者对已关闭的会话进行满意度评分（1-5 星）"""
        db = db or self.db
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == session_id,
                Conversation.consumer_id == consumer_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在或无权操作")
        if conv.status != "已关闭":
            raise HTTPException(status_code=400, detail="只能对已关闭的会话进行评分")

        # 检查是否已评分（同一会话只能评一次）
        existing = await db.execute(
            select(SatisfactionFeedback).where(
                SatisfactionFeedback.conversation_id == session_id,
                SatisfactionFeedback.consumer_id == consumer_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="您已对此会话进行过评分")

        sf = SatisfactionFeedback(
            id=uuid.uuid4().hex,
            conversation_id=session_id,
            consumer_id=consumer_id,
            rating=rating,
            feedback=feedback,
        )
        db.add(sf)
        await db.flush()
        return {"message": "评分成功", "rating": rating}

    # ── 发送咨询消息 ──────────────────────────────────

    async def send_chat_message(
        self, consumer_id: str, session_id: str = None, order_id: str = None,
        content: str = "", image_urls: list = None,
        db: AsyncSession = None,
    ) -> dict:
        """委托 ChatService 全量 AI 管线处理（IntentEngine → RAGEngine → 回复生成）"""
        db = db or self.db
        from app.services.chat_service import ChatService

        result = await ChatService.send_message(
            db=db,
            consumer_id=consumer_id,
            session_id=session_id,
            order_id=order_id,
            content=content,
            image_urls=image_urls,
        )
        return {
            "message_id": result["message_id"],
            "session_id": result["session_id"],
            "ai_reply": result["ai_reply"],
            "suggestions": result.get("suggestions", []),
            "intent": result.get("intent", ""),
            "intent_level": result.get("intent_level", ""),
            "is_transferred": result.get("transfer_status") == "pending",
            "created_at": result["created_at"],
        }

    # ── 查询会话历史 ──────────────────────────────────

    async def get_chat_history(
        self, session_id: str, consumer_id: str, page: int = 1, page_size: int = 20,
        db: AsyncSession = None,
    ):
        """委托 ChatService.get_history 查询会话消息"""
        db = db or self.db
        from app.services.chat_service import ChatService
        result = await ChatService.get_history(db=db, session_id=session_id, page=page, page_size=page_size)
        return result["items"], result["total"]

    # ── 转接人工客服 ──────────────────────────────────

    async def transfer_to_human(
        self, session_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(select(Conversation).where(Conversation.id == session_id))
        conv = result.scalar_one_or_none()
        if conv:
            conv.status = "待客服接手"
            conv.updated_at = datetime.now(timezone.utc)
            await db.flush()
        return {"session_id": session_id, "status": "transferred"}

    # ── 创建售后工单 ──────────────────────────────────

    async def create_aftersale(
        self, consumer_id: str, order_id: str, aso_type: str,
        aso_reason: str, description: str = None,
        evidence_urls: list = None, db: AsyncSession = None,
    ) -> dict:
        """委托 TicketService 创建工单并触发 AI 自动分类"""
        db = db or self.db
        from app.services.ticket_service import TicketService
        result = await TicketService.create_ticket(
            db=db,
            consumer_id=consumer_id,
            data={
                "order_id": order_id,
                "aso_type": aso_type,
                "aso_reason": aso_reason,
                "description": description,
                "evidence_urls": evidence_urls or [],
            },
        )
        await db.flush()
        return {"id": result["id"], "aso_status": result["aso_status"]}

    # ── 查询售后工单列表 ──────────────────────────────

    async def get_aftersales(
        self, consumer_id: str, aso_status: str = None,
        page: int = 1, page_size: int = 10, db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(AfterSaleOrder).where(AfterSaleOrder.consumer_id == consumer_id)
        count_query = select(func.count(AfterSaleOrder.id)).where(AfterSaleOrder.consumer_id == consumer_id)

        if aso_status:
            base_query = base_query.where(AfterSaleOrder.aso_status == aso_status)
            count_query = count_query.where(AfterSaleOrder.aso_status == aso_status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(AfterSaleOrder.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for a in result.scalars().all():
            items.append({
                "id": a.id,
                "order_id": a.order_id,
                "aso_type": a.aso_type,
                "aso_reason": a.aso_reason or "",
                "aso_status": a.aso_status,
                "urgency": a.urgency,
                "responsibility": a.responsibility,
                "review_opinion": a.review_opinion,
                "description": a.description[:100] if a.description else "",
                "created_at": str(a.created_at) if a.created_at else "",
            })
        return items, total

    # ── 查询售后工单详情 ──────────────────────────────

    async def get_aftersale_detail(
        self, consumer_id: str, aftersale_id: str, db: AsyncSession = None,
    ) -> dict:
        db = db or self.db
        result = await db.execute(
            select(AfterSaleOrder).where(
                AfterSaleOrder.id == aftersale_id,
                AfterSaleOrder.consumer_id == consumer_id,
            )
        )
        a = result.scalar_one_or_none()
        if a is None:
            return {}
        return {
            "id": a.id,
            "order_id": a.order_id,
            "aso_type": a.aso_type,
            "aso_reason": a.aso_reason,
            "aso_status": a.aso_status,
            "description": a.description,
            "evidence_urls": a.evidence_urls or [],
            "urgency": a.urgency,
            "responsibility": a.responsibility,
            "review_opinion": a.review_opinion,
            "created_at": str(a.created_at) if a.created_at else "",
            "updated_at": str(a.updated_at) if a.updated_at else "",
            "timeline": [],
        }

    # ── 撤销售后工单 ──────────────────────────────────

    async def cancel_aftersale(
        self, consumer_id: str, aftersale_id: str, db: AsyncSession = None,
    ):
        db = db or self.db
        result = await db.execute(
            select(AfterSaleOrder).where(
                AfterSaleOrder.id == aftersale_id,
                AfterSaleOrder.consumer_id == consumer_id,
            )
        )
        a = result.scalar_one_or_none()
        if a:
            a.aso_status = "已撤销"
            await db.flush()

    # ── 创建评价 ──────────────────────────────────────

    async def create_evaluation(
        self, consumer_id: str, order_id: str, product_rating: int,
        service_rating: int, logistics_rating: int, content: str = None,
        image_urls: list = None, is_anonymous: int = 0,
        db: AsyncSession = None,
    ) -> dict:
        """委托 EvaluationService 创建评价并触发 AI 情感/主题分析"""
        db = db or self.db
        from app.services.evaluation_service import EvaluationService
        result = await EvaluationService.create_evaluation(
            db=db,
            consumer_id=consumer_id,
            data={
                "order_id": order_id,
                "product_rating": product_rating,
                "service_rating": service_rating,
                "logistics_rating": logistics_rating,
                "content": content,
                "image_urls": image_urls or [],
                "is_anonymous": is_anonymous,
            },
        )
        await db.flush()
        return {"id": result["id"], "message": "评价提交成功"}

    # ── 查询评价列表 ──────────────────────────────────

    async def get_evaluations(
        self, consumer_id: str, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        base_query = select(Evaluation).where(Evaluation.consumer_id == consumer_id)
        count_query = select(func.count(Evaluation.id)).where(Evaluation.consumer_id == consumer_id)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(Evaluation.created_at.desc()).offset(offset).limit(page_size)
        )
        evaluations = result.scalars().all()  # 先收集到列表，避免多次迭代消耗
        # 批量收集 order_id，按需 JOIN OrderDetail + Order
        order_ids = [e.order_id for e in evaluations if e.order_id]
        order_info_map = {}
        if order_ids:
            # 查 OrderDetail 获取商品信息
            detail_result = await db.execute(
                select(OrderDetail).where(OrderDetail.order_id.in_(order_ids))
            )
            detail_map = {}
            for d in detail_result.scalars().all():
                if d.order_id not in detail_map:
                    detail_map[d.order_id] = {
                        "product_name": d.product_name or "",
                        "product_image": d.product_image or "",
                    }
            # 查 Order 获取金额
            order_result = await db.execute(
                select(Order).where(Order.id.in_(order_ids))
            )
            for o in order_result.scalars().all():
                detail = detail_map.get(o.id, {})
                order_info_map[o.id] = {
                    "order_id": o.id,
                    "product_name": detail.get("product_name", ""),
                    "product_image": detail.get("product_image", ""),
                    "total_amount": float(o.total_amount) if o.total_amount else 0,
                }

        items = []
        for e in evaluations:
            items.append({
                "id": e.id,
                "order_id": e.order_id,
                "product_rating": e.product_rating,
                "service_rating": e.service_rating,
                "logistics_rating": e.logistics_rating,
                "content": e.content,
                "image_urls": e.image_urls or [],
                "sentiment": e.sentiment,
                "themes": e.themes or [],
                "order_info": order_info_map.get(e.order_id, {}),
                "created_at": str(e.created_at) if e.created_at else "",
            })
        return items, total

    # ── 追评 ──────────────────────────────────────────

    async def reply_evaluation(
        self, evaluation_id: str, consumer_id: str, content: str = "",
        image_urls: list = None, db: AsyncSession = None,
    ):
        db = db or self.db
        reply = EvaluationReply(
            id=uuid.uuid4().hex,
            evaluation_id=evaluation_id,
            reply_type="consumer",
            replier_id=consumer_id,
            content=content,
            image_urls=image_urls or [],
        )
        db.add(reply)
        await db.flush()

    # ── 修改评价 ──────────────────────────────────────────

    async def update_evaluation(
        self, evaluation_id: str, consumer_id: str,
        product_rating: int | None = None,
        service_rating: int | None = None,
        logistics_rating: int | None = None,
        content: str | None = None,
        db: AsyncSession = None,
    ) -> dict:
        """CON012：修改已提交的评价（仅限 7 天内）"""
        db = db or self.db
        result = await db.execute(
            select(Evaluation).where(
                Evaluation.id == evaluation_id,
                Evaluation.consumer_id == consumer_id,
            )
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            raise HTTPException(status_code=404, detail="评价不存在")
        # 7 天限制
        created = ev.created_at.replace(tzinfo=timezone.utc) if ev.created_at and ev.created_at.tzinfo is None else ev.created_at
        if created is None:
            created = datetime.now(timezone.utc)
        age = (datetime.now(timezone.utc) - created).days
        if age > 7:
            raise HTTPException(status_code=400, detail="评价已超过 7 天，无法修改")
        if product_rating is not None:
            ev.product_rating = product_rating
        if service_rating is not None:
            ev.service_rating = service_rating
        if logistics_rating is not None:
            ev.logistics_rating = logistics_rating
        if content is not None:
            ev.content = content
        ev.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return {"evaluation_id": ev.id, "updated_at": str(ev.updated_at)}

    # ── 查询待评价订单 ────────────────────────────────

    async def get_pending_evaluations(
        self, consumer_id: str, page: int = 1, page_size: int = 10,
        db: AsyncSession = None,
    ):
        db = db or self.db
        # Return completed orders without evaluations
        sub = select(Evaluation.order_id).where(Evaluation.consumer_id == consumer_id).subquery()
        base_query = (
            select(Order)
            .where(
                Order.consumer_id == consumer_id,
                Order.status == "已完成",
                Order.id.notin_(select(sub.c.order_id)),
            )
        )
        count_query = select(func.count(Order.id)).where(
            Order.consumer_id == consumer_id,
            Order.status == "已完成",
            Order.id.notin_(select(sub.c.order_id)),
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base_query.order_by(Order.created_at.desc()).offset(offset).limit(page_size)
        )
        items = []
        for o in result.scalars().all():
            # 获取 OrderDetail 中的商品信息
            detail_result = await db.execute(
                select(OrderDetail).where(OrderDetail.order_id == o.id).limit(1)
            )
            first_detail = detail_result.scalar_one_or_none()

            items.append({
                "order_id": o.id,
                "order_sn": o.id,
                "product_name": first_detail.product_name if first_detail else "",
                "product_image": first_detail.product_image if first_detail else None,
                "total_amount": float(o.total_amount),
                "finished_at": str(o.updated_at) if o.updated_at else str(o.created_at) if o.created_at else "",
            })
        return items, total

    # ── 反馈 ──────────────────────────────────────────

    async def submit_feedback(
        self, consumer_id: str, content: str, feedback_type: str = "建议",
        db: AsyncSession = None,
    ):
        db = db or self.db
        # Store as satisfaction feedback
        fb = SatisfactionFeedback(
            id=uuid.uuid4().hex,
            conversation_id="",  # not tied to a specific conversation
            consumer_id=consumer_id,
            rating=0,
            feedback=f"[{feedback_type}] {content}",
        )
        db.add(fb)
        await db.flush()

# trigger reload
