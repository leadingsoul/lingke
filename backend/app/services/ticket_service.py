"""TicketService — 售后工单管理：创建 / 查询 / 审核 / 补充 / 完成 / 标签 / 统计"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aftersale_models import AfterSaleOrder
from app.models.product_models import Order, OrderDetail
from app.models.chat_models import ServiceRecord
from app.models.user_models import CustomerServiceStaff
from app.models.notification_models import Notification

# AI 引擎集成（全量 DeepSeek LLM）
from ai_engine.llm_gateway import LLMGateway
from ai_engine.ticket_classify_engine import TicketClassifyEngine


class TicketService:
    """售后工单服务 — 已集成 AI 引擎（TicketClassifyEngine，全量 LLM）"""

    _gateway: LLMGateway | None = None
    _classify_engine: TicketClassifyEngine | None = None

    @classmethod
    def _get_gateway(cls) -> LLMGateway:
        if cls._gateway is None:
            cls._gateway = LLMGateway.from_env()
        return cls._gateway

    @classmethod
    def _get_classify_engine(cls) -> TicketClassifyEngine:
        if cls._classify_engine is None:
            cls._classify_engine = TicketClassifyEngine(gateway=cls._get_gateway())
        return cls._classify_engine

    # ── 创建工单 ──────────────────────────────────────

    @staticmethod
    async def create_ticket(
        db: AsyncSession,
        consumer_id: str,
        data: dict,
    ) -> dict:
        """消费者创建售后工单"""
        order_id = data.get("order_id")
        aso_type = data.get("aso_type")
        aso_reason = data.get("aso_reason")
        description = data.get("description")
        evidence_urls = data.get("evidence_urls", [])

        # 验证订单存在且归属，同时加载商品详情
        order_result = await db.execute(
            select(Order).where(Order.id == order_id, Order.consumer_id == consumer_id)
        )
        order = order_result.scalar_one_or_none()
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在或无权操作",
            )

        # 查订单商品信息（用作 AI 分类的上下文）
        order_info = {}
        detail_result = await db.execute(
            select(OrderDetail).where(OrderDetail.order_id == order_id)
        )
        details = detail_result.scalars().all()
        if details:
            d = details[0]
            order_info = {
                "product_name": d.product_name,
                "product_image": d.product_image,
                "unit_price": float(d.unit_price) if d.unit_price else 0,
                "quantity": d.quantity,
                "total_amount": float(order.total_amount),
                "order_status": order.status,
            }

        # 检查是否已有活跃售后单
        active_result = await db.execute(
            select(func.count(AfterSaleOrder.id)).where(
                AfterSaleOrder.order_id == order_id,
                AfterSaleOrder.aso_status.in_(["待审核", "审核通过", "处理中"]),
            )
        )
        if (active_result.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该订单已有进行中的售后工单",
            )

        # AI 自动分类：工单类型/紧急度/责任归属
        try:
            classify_result = TicketService._get_classify_engine().classify_ticket(
                description=description or "",
                aso_type=aso_type,
                aso_reason=aso_reason or "",
                order_info=order_info if order_info else None,
            )
            urgency = classify_result.urgency
            responsibility = classify_result.responsibility
            suggested_action = classify_result.suggested_action
            contradiction = classify_result.has_contradiction
            contradiction_detail = classify_result.contradiction_detail
        except Exception:
            urgency = "紧急" if aso_type == "仅退款" else "普通"
            responsibility = "待定"
            suggested_action = ""
            contradiction = False
            contradiction_detail = ""

        # 矛盾检测结果写入自定义标签
        tags = []
        if contradiction:
            tags.append("矛盾检测-描述与商品不匹配")

        ticket = AfterSaleOrder(
            id=uuid.uuid4().hex,
            order_id=order_id,
            consumer_id=consumer_id,
            aso_type=aso_type,
            aso_reason=aso_reason,
            aso_status="待审核",
            description=description,
            evidence_urls=evidence_urls if evidence_urls else None,
            urgency=urgency,
            responsibility=responsibility,
            suggested_action=suggested_action,
            custom_tags=tags if tags else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ticket)
        await db.flush()

        return {
            "id": ticket.id,
            "order_id": ticket.order_id,
            "consumer_id": ticket.consumer_id,
            "aso_type": ticket.aso_type,
            "aso_reason": ticket.aso_reason,
            "aso_status": ticket.aso_status,
            "description": ticket.description,
            "evidence_urls": ticket.evidence_urls,
            "handler_id": ticket.handler_id,
            "handler_name": None,
            "review_opinion": ticket.review_opinion,
            "urgency": ticket.urgency,
            "responsibility": ticket.responsibility,
            "custom_tags": ticket.custom_tags,
            "has_contradiction": contradiction,
            "contradiction_detail": contradiction_detail,
            "created_at": str(ticket.created_at) if ticket.created_at else "",
            "updated_at": None,
            "completed_at": None,
        }

    # ── 查询工单（客服端）────────────────────────────

    @staticmethod
    async def get_tickets(
        db: AsyncSession,
        staff_id: str | None = None,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """客服端查询工单列表"""
        filters = filters or {}
        base_query = select(AfterSaleOrder)
        count_query = select(func.count(AfterSaleOrder.id))

        if staff_id:
            base_query = base_query.where(AfterSaleOrder.handler_id == staff_id)
            count_query = count_query.where(AfterSaleOrder.handler_id == staff_id)
        if filters.get("aso_type"):
            base_query = base_query.where(AfterSaleOrder.aso_type == filters["aso_type"])
            count_query = count_query.where(AfterSaleOrder.aso_type == filters["aso_type"])
        if filters.get("aso_status"):
            base_query = base_query.where(AfterSaleOrder.aso_status == filters["aso_status"])
            count_query = count_query.where(AfterSaleOrder.aso_status == filters["aso_status"])
        if filters.get("urgency"):
            base_query = base_query.where(AfterSaleOrder.urgency == filters["urgency"])
            count_query = count_query.where(AfterSaleOrder.urgency == filters["urgency"])
        if filters.get("keyword"):
            kw = filters["keyword"]
            base_query = base_query.where(AfterSaleOrder.description.ilike(f"%{kw}%"))
            count_query = count_query.where(AfterSaleOrder.description.ilike(f"%{kw}%"))

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(AfterSaleOrder.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        tickets = result.scalars().all()

        items = []
        for t in tickets:
            handler_name = None
            if t.handler_id:
                staff_result = await db.execute(
                    select(CustomerServiceStaff).where(CustomerServiceStaff.id == t.handler_id)
                )
                staff = staff_result.scalar_one_or_none()
                handler_name = staff.name if staff else None

            # 查订单商品信息
            product_name = None
            detail_row = await db.execute(
                select(OrderDetail.product_name).where(OrderDetail.order_id == t.order_id).limit(1)
            )
            pname = detail_row.scalar_one_or_none()
            if pname:
                product_name = pname

            items.append({
                "id": t.id,
                "order_id": t.order_id,
                "aso_type": t.aso_type,
                "aso_reason": t.aso_reason,
                "aso_status": t.aso_status,
                "description": t.description,
                "urgency": t.urgency,
                "handler_name": handler_name,
                "product_name": product_name,
                "created_at": str(t.created_at) if t.created_at else "",
                "completed_at": str(t.completed_at) if t.completed_at else None,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── 工单详情 ──────────────────────────────────────

    @staticmethod
    async def get_ticket_detail(
        db: AsyncSession,
        ticket_id: str,
    ) -> dict:
        """获取售后工单详情（含订单商品信息）"""
        result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在",
            )

        handler_name = None
        if ticket.handler_id:
            staff_result = await db.execute(
                select(CustomerServiceStaff).where(CustomerServiceStaff.id == ticket.handler_id)
            )
            staff = staff_result.scalar_one_or_none()
            handler_name = staff.name if staff else None

        # 查订单商品信息
        product_name = None
        product_image = None
        product_price = None
        detail_result = await db.execute(
            select(OrderDetail).where(OrderDetail.order_id == ticket.order_id)
        )
        details = detail_result.scalars().all()
        if details:
            d = details[0]
            product_name = d.product_name
            product_image = d.product_image
            product_price = float(d.unit_price) if d.unit_price else None

        return {
            "id": ticket.id,
            "order_id": ticket.order_id,
            "consumer_id": ticket.consumer_id,
            "aso_type": ticket.aso_type,
            "aso_reason": ticket.aso_reason,
            "aso_status": ticket.aso_status,
            "description": ticket.description,
            "evidence_urls": ticket.evidence_urls,
            "handler_id": ticket.handler_id,
            "handler_name": handler_name,
            "review_opinion": ticket.review_opinion,
            "urgency": ticket.urgency,
            "responsibility": ticket.responsibility,
            "custom_tags": ticket.custom_tags,
            "product_name": product_name,
            "product_image": product_image,
            "product_price": product_price,
            "created_at": str(ticket.created_at) if ticket.created_at else "",
            "updated_at": str(ticket.updated_at) if ticket.updated_at else None,
            "completed_at": str(ticket.completed_at) if ticket.completed_at else None,
        }

    # ── 撤销工单（消费者）─────────────────────────────

    @staticmethod
    async def cancel_ticket(
        db: AsyncSession,
        consumer_id: str,
        ticket_id: str,
    ) -> None:
        """消费者撤销自己的售后工单（仅限待审核状态）"""
        result = await db.execute(
            select(AfterSaleOrder).where(
                AfterSaleOrder.id == ticket_id,
                AfterSaleOrder.consumer_id == consumer_id,
            )
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在或无权操作",
            )
        if ticket.aso_status != "待审核":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅待审核状态的工单可以撤销",
            )

        ticket.aso_status = "已撤销"
        await db.flush()

    # ── 审核工单（客服）────────────────────────────

    @staticmethod
    async def review_ticket(
        db: AsyncSession,
        staff_id: str,
        ticket_id: str,
        result: str,
        opinion: str | None = None,
    ) -> dict:
        """客服审核售后工单"""
        ticket_result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在",
            )

        if result == "通过":
            ticket.aso_status = "审核通过"
        elif result == "拒绝":
            ticket.aso_status = "已拒绝"
        elif result == "需补充":
            # 保持待审核，但记录审核意见
            ticket.review_opinion = opinion

        if result in ("通过", "拒绝") and opinion:
            ticket.review_opinion = opinion

        # 首次审核记录处理人
        if ticket.handler_id is None:
            ticket.handler_id = staff_id

        # 服务记录
        record = ServiceRecord(
            id=uuid.uuid4().hex,
            staff_id=staff_id,
            action="审核",
            target_type="ticket",
            target_id=ticket.id,
            detail=f"审核结果: {result}" + (f" — {opinion}" if opinion else ""),
        )
        db.add(record)
        await db.flush()

        return await TicketService.get_ticket_detail(db, ticket_id)

    # ── 要求补充材料 ─────────────────────────────────

    @staticmethod
    async def request_supplement(
        db: AsyncSession,
        staff_id: str,
        ticket_id: str,
        note: str,
    ) -> None:
        """客服要求消费者补充材料"""
        ticket_result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在",
            )

        ticket.review_opinion = f"需补充材料：{note}"
        ticket.handler_id = staff_id

        # 创建通知给消费者
        notification = Notification(
            id=uuid.uuid4().hex,
            recipient_id=ticket.consumer_id,
            recipient_type="consumer",
            type="工单状态变更",
            title="售后工单需补充材料",
            content=note,
            link=f"/consumer/aftersale/{ticket_id}",
        )
        db.add(notification)

        # 服务记录
        record = ServiceRecord(
            id=uuid.uuid4().hex,
            staff_id=staff_id,
            action="审核",
            target_type="ticket",
            target_id=ticket.id,
            detail=f"要求补充材料: {note}",
        )
        db.add(record)
        await db.flush()

    # ── 完成工单 ──────────────────────────────────────

    @staticmethod
    async def complete_ticket(
        db: AsyncSession,
        staff_id: str,
        ticket_id: str,
    ) -> dict:
        """完成售后工单"""
        ticket_result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在",
            )

        ticket.aso_status = "已完成"
        ticket.completed_at = datetime.now(timezone.utc)

        # 服务记录
        record = ServiceRecord(
            id=uuid.uuid4().hex,
            staff_id=staff_id,
            action="审核",
            target_type="ticket",
            target_id=ticket.id,
            detail="完成售后工单",
        )
        db.add(record)
        await db.flush()

        return await TicketService.get_ticket_detail(db, ticket_id)

    # ── 添加标签 ──────────────────────────────────────

    @staticmethod
    async def add_tag(
        db: AsyncSession,
        ticket_id: str,
        tag: str,
    ) -> dict:
        """给工单添加自定义标签"""
        ticket_result = await db.execute(
            select(AfterSaleOrder).where(AfterSaleOrder.id == ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工单不存在",
            )

        current_tags = ticket.custom_tags or []
        if tag not in current_tags:
            current_tags.append(tag)
            ticket.custom_tags = current_tags

        await db.flush()
        return await TicketService.get_ticket_detail(db, ticket_id)

    # ── 分类统计 ──────────────────────────────────────

    @staticmethod
    async def get_category_stats(db: AsyncSession) -> list[dict]:
        """获取售后工单分类统计"""
        result = await db.execute(
            select(
                AfterSaleOrder.aso_type,
                func.count(AfterSaleOrder.id).label("count"),
            ).group_by(AfterSaleOrder.aso_type)
        )
        rows = result.all()

        total = sum(r.count for r in rows)
        stats = []
        for row in rows:
            stats.append({
                "category": row.aso_type,
                "count": row.count,
                "percentage": round(row.count / total * 100, 2) if total > 0 else 0,
            })
        return stats
