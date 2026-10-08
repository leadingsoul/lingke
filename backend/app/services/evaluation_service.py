"""EvaluationService — 评价管理：创建 / 回复 / 更新 / 待评价 / 统计"""

import uuid
from datetime import datetime, date, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_models import Evaluation, EvaluationReply
from app.models.product_models import Order, OrderDetail
from app.models.user_models import Consumer

# AI 引擎集成（全量 DeepSeek LLM）
from ai_engine.llm_gateway import LLMGateway
from ai_engine.sentiment_engine import SentimentEngine
from ai_engine.theme_engine import ThemeEngine


class EvaluationService:
    """评价服务 — 已集成 AI 引擎（SentimentEngine + ThemeEngine，全量 LLM）"""

    _gateway: LLMGateway | None = None
    _sentiment_engine: SentimentEngine | None = None
    _theme_engine: ThemeEngine | None = None

    @classmethod
    def _get_gateway(cls) -> LLMGateway:
        if cls._gateway is None:
            cls._gateway = LLMGateway.from_env()
        return cls._gateway

    @classmethod
    def _get_sentiment_engine(cls) -> SentimentEngine:
        if cls._sentiment_engine is None:
            cls._sentiment_engine = SentimentEngine(gateway=cls._get_gateway())
        return cls._sentiment_engine

    @classmethod
    def _get_theme_engine(cls) -> ThemeEngine:
        if cls._theme_engine is None:
            cls._theme_engine = ThemeEngine(gateway=cls._get_gateway())
        return cls._theme_engine

    # ═══════════════════ AI 引擎封装 ═══════════════════

    @classmethod
    def _run_sentiment_analysis(cls, content: str) -> dict:
        """情感分析：走 ai_engine SentimentEngine"""
        try:
            result = cls._get_sentiment_engine().analyze(content)
            return {"sentiment": result.sentiment, "intensity": result.intensity, "risk_level": result.risk_level}
        except Exception:
            # 兜底关键词匹配
            pos = sum(1 for w in ["好", "满意", "不错", "快", "棒"] if w in content)
            neg = sum(1 for w in ["差", "烂", "慢", "投诉", "不好"] if w in content)
            if neg > pos:
                return {"sentiment": "negative", "intensity": 0.6}
            elif pos > neg:
                return {"sentiment": "positive", "intensity": 0.6}
            else:
                return {"sentiment": "neutral", "intensity": 0.5}

    @classmethod
    def _run_theme_classification(cls, content: str) -> list[str]:
        """主题归类：走 ai_engine ThemeEngine"""
        try:
            result = cls._get_theme_engine().classify(content)
            return [t.theme for t in result.themes]
        except Exception:
            return [result.primary_theme] if result.primary_theme else ["其他"]

    # ═══════════════════ 服务方法 ═══════════════════════

    @staticmethod
    async def create_evaluation(
        db: AsyncSession,
        consumer_id: str,
        data: dict,
    ) -> dict:
        """创建评价"""
        order_id = data.get("order_id")

        # 验证订单
        order_result = await db.execute(
            select(Order).where(Order.id == order_id, Order.consumer_id == consumer_id)
        )
        order = order_result.scalar_one_or_none()
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在或无权操作",
            )
        if order.status != "已完成":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅已完成订单可评价",
            )

        # 检查是否已评价
        existing_result = await db.execute(
            select(func.count(Evaluation.id)).where(
                Evaluation.order_id == order_id,
                Evaluation.consumer_id == consumer_id,
            )
        )
        if (existing_result.scalar() or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该订单已评价",
            )

        content = data.get("content", "")

        # 情感/主题分析：有文字内容走 AI，否则用评分判定
        avg_rating = (data.get("product_rating", 5) + data.get("service_rating", 5) + data.get("logistics_rating", 5)) / 3

        if content and content.strip():
            # 有文字 → AI 情感分析 + 主题归类
            try:
                sent_result = EvaluationService._run_sentiment_analysis(content)
            except Exception:
                sent_result = {"sentiment": "neutral", "intensity": 0.5}
            try:
                themes = EvaluationService._run_theme_classification(content)
            except Exception:
                themes = []
        else:
            # 纯评分 → 根据评分判定情感
            if avg_rating >= 4:
                sent_result = {"sentiment": "positive", "intensity": 0.8}
            elif avg_rating <= 2:
                sent_result = {"sentiment": "negative", "intensity": 0.7}
            else:
                sent_result = {"sentiment": "neutral", "intensity": 0.5}
            themes = []

        # 风险评估
        risk_level = "low"
        if sent_result.get("sentiment") == "negative" and (sent_result.get("intensity", 0) or 0) > 0.6:
            risk_level = "high"
        elif sent_result.get("sentiment") == "negative":
            risk_level = "medium"

        evaluation = Evaluation(
            id=uuid.uuid4().hex,
            order_id=order_id,
            consumer_id=consumer_id,
            product_rating=data.get("product_rating", 5),
            service_rating=data.get("service_rating", 5),
            logistics_rating=data.get("logistics_rating", 5),
            content=content,
            image_urls=data.get("image_urls") if data.get("image_urls") else None,
            is_anonymous=data.get("is_anonymous", 0),
            sentiment=sent_result.get("sentiment"),
            sentiment_intensity=sent_result.get("intensity"),
            themes=themes,
            risk_level=risk_level,
            created_at=datetime.now(timezone.utc),
        )
        db.add(evaluation)
        await db.flush()

        return {
            "id": evaluation.id,
            "order_id": evaluation.order_id,
            "product_rating": evaluation.product_rating,
            "service_rating": evaluation.service_rating,
            "logistics_rating": evaluation.logistics_rating,
            "content": evaluation.content,
            "sentiment": evaluation.sentiment,
            "created_at": str(evaluation.created_at) if evaluation.created_at else "",
        }

    @staticmethod
    async def add_reply(
        db: AsyncSession,
        consumer_id: str,
        evaluation_id: str,
        content: str,
        image_urls: list[str] | None = None,
    ) -> dict:
        """消费者追评"""
        # 验证评价存在且归属
        eval_result = await db.execute(
            select(Evaluation).where(
                Evaluation.id == evaluation_id,
                Evaluation.consumer_id == consumer_id,
            )
        )
        evaluation = eval_result.scalar_one_or_none()
        if evaluation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="评价不存在或无权操作",
            )

        reply = EvaluationReply(
            id=uuid.uuid4().hex,
            evaluation_id=evaluation_id,
            reply_type="consumer",
            replier_id=consumer_id,
            content=content,
            image_urls=image_urls if image_urls else None,
        )
        db.add(reply)
        await db.flush()

        return {
            "id": reply.id,
            "evaluation_id": reply.evaluation_id,
            "reply_type": reply.reply_type,
            "replier_id": reply.replier_id,
            "content": reply.content,
            "image_urls": reply.image_urls,
            "created_at": str(reply.created_at) if reply.created_at else "",
        }

    @staticmethod
    async def update_evaluation(
        db: AsyncSession,
        consumer_id: str,
        evaluation_id: str,
        data: dict,
    ) -> dict:
        """更新评价内容/评分"""
        eval_result = await db.execute(
            select(Evaluation).where(
                Evaluation.id == evaluation_id,
                Evaluation.consumer_id == consumer_id,
            )
        )
        evaluation = eval_result.scalar_one_or_none()
        if evaluation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="评价不存在或无权操作",
            )

        if "product_rating" in data:
            evaluation.product_rating = data["product_rating"]
        if "service_rating" in data:
            evaluation.service_rating = data["service_rating"]
        if "logistics_rating" in data:
            evaluation.logistics_rating = data["logistics_rating"]
        if "content" in data:
            evaluation.content = data["content"]

        # 重新分析情感
        if "content" in data and data["content"]:
            try:
                sent_result = EvaluationService._run_sentiment_analysis(data["content"])
                evaluation.sentiment = sent_result.get("sentiment")
                evaluation.sentiment_intensity = sent_result.get("intensity")
            except Exception:
                pass

        await db.flush()

        return {
            "id": evaluation.id,
            "order_id": evaluation.order_id,
            "product_rating": evaluation.product_rating,
            "service_rating": evaluation.service_rating,
            "logistics_rating": evaluation.logistics_rating,
            "content": evaluation.content,
            "sentiment": evaluation.sentiment,
            "created_at": str(evaluation.created_at) if evaluation.created_at else "",
        }

    @staticmethod
    async def get_pending_evals(
        db: AsyncSession,
        consumer_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取待评价的已完成订单"""
        # 已完成订单子查询
        completed_orders = (
            select(Order.id)
            .where(Order.consumer_id == consumer_id, Order.status == "已完成")
            .subquery()
        )

        # 已评价订单子查询
        evaluated_orders = (
            select(Evaluation.order_id)
            .where(Evaluation.consumer_id == consumer_id)
            .subquery()
        )

        # 待评价：已完成但未评价
        count_result = await db.execute(
            select(func.count(Order.id)).where(
                Order.id.in_(select(completed_orders.c.id)),
                Order.id.not_in(select(evaluated_orders.c.order_id)),
            )
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        order_result = await db.execute(
            select(Order)
            .where(
                Order.id.in_(select(completed_orders.c.id)),
                Order.id.not_in(select(evaluated_orders.c.order_id)),
            )
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        orders = order_result.scalars().all()

        items = []
        for order in orders:
            # 获取第一个产品信息
            detail_result = await db.execute(
                select(OrderDetail)
                .where(OrderDetail.order_id == order.id)
                .limit(1)
            )
            detail = detail_result.scalar_one_or_none()

            items.append({
                "order_id": order.id,
                "order_sn": order.id,
                "product_name": detail.product_name if detail else "",
                "product_image": detail.product_image if detail else None,
                "total_amount": float(order.total_amount),
                "finished_at": str(order.updated_at) if order.updated_at else str(order.created_at) if order.created_at else "",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def reply_to_evaluation(
        db: AsyncSession,
        staff_id: str,
        evaluation_id: str,
        reply_content: str,
    ) -> dict:
        """商家回复用户评价"""
        # 验证评价存在
        eval_result = await db.execute(
            select(Evaluation).where(Evaluation.id == evaluation_id)
        )
        if eval_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="评价不存在",
            )

        reply = EvaluationReply(
            id=uuid.uuid4().hex,
            evaluation_id=evaluation_id,
            reply_type="merchant",
            replier_id=staff_id,
            content=reply_content,
        )
        db.add(reply)
        await db.flush()

        return {
            "id": reply.id,
            "evaluation_id": reply.evaluation_id,
            "reply_type": reply.reply_type,
            "replier_id": reply.replier_id,
            "content": reply.content,
            "image_urls": reply.image_urls,
            "created_at": str(reply.created_at) if reply.created_at else "",
        }

    @staticmethod
    async def get_stats(
        db: AsyncSession,
        date_range: tuple[str | None, str | None] | None = None,
    ) -> dict:
        """获取评价统计"""
        base_filter = []
        if date_range and date_range[0]:
            base_filter.append(Evaluation.created_at >= date_range[0])
        if date_range and date_range[1]:
            base_filter.append(Evaluation.created_at <= date_range[1])

        # 情感分布
        sent_result = await db.execute(
            select(
                Evaluation.sentiment,
                func.count(Evaluation.id).label("count"),
            ).where(*base_filter).group_by(Evaluation.sentiment)
        )
        sentiment_dist = {}
        for row in sent_result.all():
            sentiment_dist[row.sentiment or "unknown"] = row.count

        # 评分平均
        avg_result = await db.execute(
            select(
                func.avg(Evaluation.product_rating).label("avg_product"),
                func.avg(Evaluation.service_rating).label("avg_service"),
                func.avg(Evaluation.logistics_rating).label("avg_logistics"),
            ).where(*base_filter)
        )
        avg_row = avg_result.one()

        # 主题分布（mock: 从数据库查）
        all_evals_result = await db.execute(
            select(Evaluation.themes).where(*base_filter)
        )
        theme_count = {}
        for (themes,) in all_evals_result.all():
            if themes:
                for t in themes:
                    theme_count[t] = theme_count.get(t, 0) + 1

        return {
            "sentiment_distribution": sentiment_dist,
            "avg_ratings": {
                "product": round(float(avg_row.avg_product or 0), 2),
                "service": round(float(avg_row.avg_service or 0), 2),
                "logistics": round(float(avg_row.avg_logistics or 0), 2),
            },
            "theme_distribution": theme_count,
        }
