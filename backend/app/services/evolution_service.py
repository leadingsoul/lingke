"""EvolutionService — AI 进化引擎（集成 EvolutionEngine 自进化闭环，全量 LLM）"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_models import Conversation, SessionSummary, Message, SatisfactionFeedback
from app.models.user_models import CustomerServiceStaff

# AI 引擎集成（全量 DeepSeek LLM）
from ai_engine.llm_gateway import LLMGateway
from ai_engine.evolution_engine import EvolutionEngine


class EvolutionService:
    """进化引擎服务 — 已集成 AI 引擎（EvolutionEngine，全量 LLM）"""

    _gateway: LLMGateway | None = None
    _evolution_engine: EvolutionEngine | None = None

    @classmethod
    def _get_gateway(cls) -> LLMGateway:
        if cls._gateway is None:
            cls._gateway = LLMGateway.from_env()
        return cls._gateway

    @classmethod
    def _get_evolution_engine(cls) -> EvolutionEngine:
        if cls._evolution_engine is None:
            cls._evolution_engine = EvolutionEngine(gateway=cls._get_gateway())
        return cls._evolution_engine

    @classmethod
    async def generate_session_summary(
        cls,
        db: AsyncSession,
        conversation_id: str,
        staff_name: str = "客服",
    ) -> SessionSummary | None:
        """为单个已关闭会话生成 LLM 沉淀文档（G3 修复）"""
        import logging
        logger = logging.getLogger(__name__)

        # 检查是否已有 summary
        existing = await db.execute(
            select(SessionSummary).where(SessionSummary.conversation_id == conversation_id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"[Evolution] Summary already exists for {conversation_id}, skipping")
            return None

        # 获取会话消息
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        if not messages:
            logger.warning(f"[Evolution] No messages found for {conversation_id}")
            return None

        msg_dicts = [
            {"sender_type": m.sender_type, "content": m.content, "created_at": str(m.created_at)}
            for m in messages
        ]

        # 获取会话的意图分级（从 Conversation 记录）
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        intent_level = getattr(conv, 'intent_level', None) or "L1"

        # 获取 AI 意图识别结果（从最后一条 AI 消息的 ai_metadata）
        intent = "咨询"
        for m in reversed(messages):
            if m.sender_type == "ai" and m.ai_metadata:
                intent = m.ai_metadata.get("intent", "咨询")
                break

        # 获取用户满意度评分
        rating = "未评分"
        feedback = ""
        sat_result = await db.execute(
            select(SatisfactionFeedback)
            .where(SatisfactionFeedback.conversation_id == conversation_id)
            .order_by(SatisfactionFeedback.created_at.desc())
            .limit(1)
        )
        sat = sat_result.scalar_one_or_none()
        if sat:
            rating = f"{sat.rating}/5 星"
            feedback = sat.feedback or ""

        engine = cls._get_evolution_engine()

        # LLM 生成沉淀文档
        try:
            session_summary = engine.summarize_conversation(
                messages=msg_dicts,
                conversation_id=conversation_id,
                staff_name=staff_name,
                intent_level=intent_level,
                intent=intent,
                rating=rating,
                feedback=feedback,
                message_count=len(messages),
            )
            summary_content = session_summary.content
            tags = session_summary.tags
        except Exception as e:
            logger.warning(f"[Evolution] LLM summary failed, using fallback: {e}")
            summary_content = cls._mock_summary_content_for_id(conversation_id, messages)
            tags = ["AI生成"]

        summary = SessionSummary(
            id=uuid.uuid4().hex,
            conversation_id=conversation_id,
            content=summary_content,
            tags=tags,
            review_status="待审核",
            synced_to_knowledge=False,
        )
        db.add(summary)
        await db.flush()

        logger.info(f"[Evolution] Summary generated for {conversation_id}")
        return summary

    @classmethod
    async def trigger_evolution_analysis(cls, db: AsyncSession) -> None:
        """批量触发进化分析（对最近关闭的会话调用 generate_session_summary）"""
        import logging
        logger = logging.getLogger(__name__)

        result = await db.execute(
            select(Conversation)
            .where(Conversation.status == "已关闭")
            .order_by(Conversation.closed_at.desc())
            .limit(10)
        )
        conversations = result.scalars().all()

        for conv in conversations:
            await cls.generate_session_summary(db, conv.id, staff_name="客服")

        logger.info(f"[EvolutionEngine] Analysis complete. Processed {len(conversations)} conversations.")

    @classmethod
    async def auto_close_stale_conversations(
        cls, db: AsyncSession, max_hours: int = 24,
    ) -> int:
        """自动关闭超过 max_hours 小时未更新的非关闭会话，并生成沉淀文档

        每轮扫描由 lifespan 后台任务触发（默认每 10 分钟）。
        只关闭 updated_at（或 created_at 兜底）早于截止时间的会话，
        正常活跃的会话不受影响。

        Returns:
            int: 本轮关闭的会话数量
        """
        import logging
        logger = logging.getLogger(__name__)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)

        # 查询所有非关闭状态且超过时限的会话
        # updated_at 优先；created_at 兜底（新建会话 updated_at 为 NULL）
        result = await db.execute(
            select(Conversation).where(
                Conversation.status != "已关闭",
                (
                    (Conversation.updated_at < cutoff)
                    | (
                        (Conversation.updated_at == None)
                        & (Conversation.created_at < cutoff)
                    )
                ),
            )
        )
        stale_convs = result.scalars().all()

        closed_count = 0
        for conv in stale_convs:
            try:
                staff_name = "系统自动"
                if conv.staff_id:
                    staff_result = await db.execute(
                        select(CustomerServiceStaff).where(
                            CustomerServiceStaff.id == conv.staff_id
                        )
                    )
                    staff = staff_result.scalar_one_or_none()
                    if staff and staff.name:
                        staff_name = f"{staff.name}(系统自动)"

                # 关闭会话（先标记，generate_session_summary 内部的 flush
                # 会一起把 conv 状态变更刷进 DB，保证事务原子性）
                conv.status = "已关闭"
                conv.closed_at = datetime.now(timezone.utc)
                conv.updated_at = datetime.now(timezone.utc)

                # 生成沉淀文档（成功时内部会 flush，失败则 expunge 跳过）
                await cls.generate_session_summary(
                    db=db,
                    conversation_id=conv.id,
                    staff_name=staff_name,
                )
                closed_count += 1
                logger.info(
                    f"[AutoClose] Closed stale conversation {conv.id} "
                    f"(staff_id={conv.staff_id or 'none'})"
                )
            except Exception as exc:
                logger.warning(
                    f"[AutoClose] Failed to close {conv.id}: {exc}"
                )
                # 从 session 中移除该对象，防止 commit 时意外写入半截状态
                db.expunge(conv)

        if closed_count > 0:
            await db.commit()
            logger.info(f"[AutoClose] Round complete: closed {closed_count} stale conversations")
        else:
            logger.debug(f"[AutoClose] No stale conversations found (cutoff: {cutoff.isoformat()})")

        return closed_count

    @staticmethod
    def _mock_summary_content(conv, messages) -> str:
        """兜底：硬编码摘要（兼容旧接口，传入 ORM 对象）"""
        return EvolutionService._mock_summary_content_for_id(conv.id, messages)

    @staticmethod
    def _mock_summary_content_for_id(conversation_id: str, messages) -> str:
        """兜底：硬编码摘要（仅需 conversation_id）"""
        first_user_msg = ""
        for m in messages:
            if m.sender_type == "consumer":
                first_user_msg = m.content[:100]
                break
        return (
            f"# 会话摘要\n\n"
            f"- 会话 ID：{conversation_id}\n"
            f"- 消息总数：{len(messages)}条\n"
            f"- 用户首问：{first_user_msg}\n\n"
            f"## 要点\n\n"
            f"本条会话由 AI 进化引擎自动生成摘要。用户咨询了售后服务相关问题，"
            f"系统通过智能问答和人工协助完成了处理。"
        )

