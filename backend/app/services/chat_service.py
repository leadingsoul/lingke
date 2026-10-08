"""ChatService — 智能咨询：发送消息 / 历史消息 / 转人工 / 客服端会话管理"""

import asyncio
import uuid
import re
from datetime import datetime, timezone
from app.utils import format_dt

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_models import Conversation, Message, ServiceRecord
from app.models.user_models import Consumer, CustomerServiceStaff
from app.models.knowledge_models import KnowledgeItem

# AI 引擎集成（全量 DeepSeek LLM）
from ai_engine.llm_gateway import LLMGateway
from ai_engine.intent_engine import IntentEngine
from ai_engine.dialog_manager import DialogManager
from ai_engine.rag_engine import RAGEngine


class ChatService:
    """咨询会话服务 — 已集成 AI 引擎（IntentEngine + DialogManager + RAGEngine，全量 LLM）"""

    # 全局 AI 引擎实例（懒加载）
    _gateway: LLMGateway | None = None
    _intent_engine: IntentEngine | None = None
    _dialog_manager: DialogManager | None = None
    _rag_engine: RAGEngine | None = None

    @classmethod
    def _get_gateway(cls) -> LLMGateway:
        if cls._gateway is None:
            cls._gateway = LLMGateway.from_env()
        return cls._gateway

    @classmethod
    def _get_intent_engine(cls) -> IntentEngine:
        if cls._intent_engine is None:
            cls._intent_engine = IntentEngine(gateway=cls._get_gateway())
        return cls._intent_engine

    @classmethod
    def _get_dialog_manager(cls) -> DialogManager:
        if cls._dialog_manager is None:
            cls._dialog_manager = DialogManager(gateway=cls._get_gateway())
        return cls._dialog_manager

    @classmethod
    def _get_rag_engine(cls) -> RAGEngine:
        if cls._rag_engine is None:
            cls._rag_engine = RAGEngine(gateway=cls._get_gateway())
        return cls._rag_engine

    # ═══════════════════ AI 引擎封装 ═══════════════════

    @classmethod
    def _run_intent_engine(cls, content: str, context: str = None) -> dict:
        """意图识别：优先走 ai_engine LLM，异常时降级到硬编码规则"""
        try:
            engine = cls._get_intent_engine()
            result = engine.classify(content, context)
            return {
                "intent": result.primary_intent,
                "level": result.level,
                "confidence": result.confidence,
                "keywords": result.keywords,
                "is_sensitive": result.is_sensitive,
            }
        except Exception:
            # 最终兜底：硬编码关键词匹配（仅在 LLM 完全不可用时触发）
            if any(kw in content for kw in ["退款", "投诉", "退货", "换货", "坏了", "质量"]):
                return {"intent": "投诉", "level": "L3", "confidence": 0.95}
            elif "?" in content or "怎么" in content or "如何" in content or "什么" in content:
                return {"intent": "咨询", "level": "L1", "confidence": 0.85}
            else:
                # 默认保守为 L1 信息查询，避免简单打招呼误升级
                return {"intent": "闲聊", "level": "L1", "confidence": 0.80}

    @classmethod
    async def _run_rag_engine(cls, db: AsyncSession, content: str) -> list[dict]:
        """RAG 检索：先同步 ai_engine 知识库，再走引擎检索"""
        try:
            # 从 DB 加载启用状态的知识库到 RAG 引擎的内存索引
            result = await db.execute(
                select(KnowledgeItem).where(KnowledgeItem.status == "启用").limit(200)
            )
            knowledge_items = result.scalars().all()
            rag = cls._get_rag_engine()
            rag.load_knowledge_items([
                {"id": item.id, "title": item.title, "content": item.content, "type": item.type}
                for item in knowledge_items
            ])
            fragments = rag.retrieve(content, top_k=15)  # 粗召回 15 条，后续 LLM 语义精排
            # RAG 命中计数：给被匹配到的知识条目 +1
            if fragments:
                hit_ids = [f.id for f in fragments[:3]]
                await db.execute(
                    select(KnowledgeItem).where(KnowledgeItem.id.in_(hit_ids))
                )
                for k in knowledge_items:
                    if k.id in hit_ids:
                        k.hit_count = (k.hit_count or 0) + 1
                await db.flush()
            return [
                {"id": f.id, "title": f.title, "content": f.content[:500], "relevance_score": f.relevance_score}
                for f in fragments
            ]
        except Exception:
            # 降级：直接 SQL LIKE 查询
            try:
                # 使用 ai_engine 的 n-gram 关键词提取
                from ai_engine.rag_engine import RAGEngine
                keywords = list(RAGEngine._extract_keywords(content))
                if not keywords:
                    return []
                conditions = []
                for kw in keywords[:3]:
                    conditions.append(KnowledgeItem.content.ilike(f"%{kw}%"))
                    conditions.append(KnowledgeItem.title.ilike(f"%{kw}%"))
                from sqlalchemy import or_
                result = await db.execute(
                    select(KnowledgeItem)
                    .where(KnowledgeItem.status == "启用", or_(*conditions))
                    .limit(5)
                )
                items = result.scalars().all()
                return [
                    {"id": item.id, "title": item.title, "content": item.content[:500], "type": item.type}
                    for item in items
                ]
            except Exception:
                return []

    @classmethod
    def _run_ai_reply_generation(cls, content: str, intent: dict, knowledge_items: list[dict]) -> tuple[str, float]:
        """AI 回复生成：优先走 RAGEngine.generate_reply，异常时降级
        返回 (reply_text, confidence)
        """
        try:
            rag = cls._get_rag_engine()
            from ai_engine.rag_engine import KnowledgeFragment as KF
            fragments = [
                KF(id=ki.get("id", ""), title=ki.get("title", ""), content=ki.get("content", ""),
                   relevance_score=ki.get("relevance_score", 0.8))
                for ki in knowledge_items
            ]
            response = rag.generate_reply(query=content, context=fragments)
            reply = cls._clean_markdown_artifacts(response.reply)
            return reply, response.confidence
        except Exception:
            # 降级：直接拼接知识库内容
            level = intent.get("level", "L2")
            if level == "L3":
                return "您的问题已记录，正在为您转接人工客服，请稍候...", 0.3
            if knowledge_items:
                top = knowledge_items[0]
                return f"您好！关于「{top['title']}」，以下是相关信息：\n{top['content'][:300]}\n\n还有其他可以帮助您的吗？", 0.6
            return f"您好！已收到您的咨询，我们会尽快为您处理。如需人工协助，请回复「转人工」。", 0.3

    @staticmethod
    def _clean_markdown_artifacts(text: str) -> str:
        """清洗 LLM 输出的 Markdown 残留符号，确保前端渲染干净。

        保留：有效的 **粗体**、- 列表项、1. 编号列表
        清除：孤立/不成对的 *、# 标题、``` 代码块
        """
        if not text:
            return text

        # 1. 去掉 Markdown 标题符号（# ## ### 在行首的）
        text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)

        # 2. 去掉代码块标记 ```
        text = re.sub(r'```[a-z]*\n?', '', text)

        # 3. 修复孤立/不成对的 ** — 如果 ** 个数是奇数，删掉多余的
        def _fix_bold_pairs(s: str) -> str:
            parts = s.split('**')
            if len(parts) % 2 == 0:
                return s  # 偶数段，配对正确
            # 奇数段 → 最后一个 ** 是孤立的，去掉它（找最后出现的 ** 位置）
            last = s.rfind('**')
            if last >= 0:
                s = s[:last] + s[last+2:]
            return s
        text = _fix_bold_pairs(text)

        # 4. 去掉孤立的 * 字符（非列表，非粗体的剩余 *）
        #    *word* 斜体 → 去 * 留 word
        text = re.sub(r'\*([^*\n]+?)\*', r'\1', text)
        #    行首孤立 * （不属于列表的）
        text = re.sub(r'^[ ]*\*(?!\s)', '', text, flags=re.MULTILINE)

        return text.strip()

    @classmethod
    def _run_suggestions(cls, content: str, intent: dict, knowledge_items: list[dict]) -> list[str]:
        """生成建议问题：优先 LLM 动态生成（上下文感知），异常时降级"""
        try:
            rag = cls._get_rag_engine()
            gateway = cls._get_gateway()
            if gateway is not None:
                import json as _json
                kb_hint = ""
                if knowledge_items:
                    titles = [k.get("title", "") for k in knowledge_items[:3]]
                    kb_hint = f"\n知识库参考：{titles}"
                prompt = f"""你是电商客服助手。用户刚发送了以下消息，请根据消息内容生成 3-5 个用户可能想继续追问的问题。

用户消息：{content}
意图：{intent.get('intent', '未知')}
置信度：{intent.get('confidence', 0)}{kb_hint}

要求：
1. 问题要紧贴用户当前的实际需求，不要千篇一律
2. 用用户的语气（第一人称），如"我的订单什么时候发货？"
3. 每个问题不超过 20 字
4. 输出 JSON 字符串数组

只输出 JSON 数组，不要其他文字。"""
                response = gateway.chat_sync(prompt, temperature=0.7, max_tokens=200)
                data = _json.loads(response)
                if isinstance(data, list) and len(data) >= 1:
                    return data[:5]
        except Exception:
            pass

        # 降级：按意图级别返回固定建议
        suggestions = []
        level = intent.get("level", "L1")
        if level == "L1":
            suggestions = ["如何查看物流信息？", "如何申请退款？", "商品有问题怎么办？"]
        elif level == "L2":
            suggestions = ["如何联系人工客服？", "售后政策是什么？", "如何评价订单？"]
        else:
            suggestions = ["转人工客服", "查看订单状态", "取消退款申请"]
        if knowledge_items:
            for item in knowledge_items[1:]:
                suggestions.insert(0, item.get("title", ""))
        return suggestions[:5]

    # ═══════════════════ 错别字纠正 + 语义检索 ═══════════════════

    @classmethod
    def _correct_typos(cls, content: str) -> tuple[str, bool]:
        """LLM 错别字纠正：修正用户消息中的错别字，不改变语义

        返回 (修正后文本, 是否有修正)。
        仅在 AI 管线内部使用，不影响用户原始消息存储。
        """
        if not content or len(content.strip()) < 2:
            return content, False
        try:
            gateway = cls._get_gateway()
            prompt = (
                "你是中文错别字纠正助手。请检查以下用户消息是否有错别字，"
                "如果有错别字请修正后输出，如果没有就原样输出。\n\n"
                "规则：\n"
                "1. 只修正明显的错别字（同音字、形近字、拼音输入错误）\n"
                "2. 不要改变原意、不要添加内容、不要改写句式\n"
                "3. 方言、口语、网络用语属于正常表达，不需要\"纠正\"\n\n"
                f"用户消息：{content}\n\n"
                "只输出修正后的文本，不要任何解释。"
            )
            corrected = gateway.chat_sync(prompt, temperature=0.1, max_tokens=200)
            corrected = corrected.strip()
            was_corrected = corrected != content.strip()
            return corrected, was_corrected
        except Exception:
            return content, False

    @classmethod
    def _semantic_rerank_and_validate(
        cls,
        query: str,
        candidates: list[dict],
    ) -> dict:
        """LLM 语义重排序 + 充分性判断：从粗召回候选中精选最相关的条目

        一次 LLM 调用完成两件事：
        1. 语义筛选 — 理解用户消息含义，选出真正相关的知识条目
        2. 充分性判断 — 判断选出的知识是否足以回答用户问题

        替代原来的 n-gram 单一匹配 + 独立 validate_retrieval()。
        """
        if not candidates:
            return {
                "selected_ids": [],
                "is_sufficient": False,
                "sufficiency_score": 0.5,
                "reason": "粗召回无结果，将使用通用知识回答",
                "missing_aspects": ["所有方面"],
            }
        try:
            gateway = cls._get_gateway()
            candidates_summary = "\n".join(
                f"[ID:{c['id']}] {c['title']} — {c.get('content', '')[:120]}"
                for c in candidates[:15]
            )
            prompt = (
                "你是电商客服知识检索助手。请根据用户消息的语义，"
                "从候选知识条目中选出最相关的，并判断是否足以回答用户问题。\n\n"
                f"【用户消息】\n{query}\n\n"
                f"【候选知识条目】（共 {len(candidates)} 条）\n"
                f"{candidates_summary}\n\n"
                "【任务】\n"
                "1. 选出与用户消息语义相关的条目（最多 5 条），按相关度排序。"
                "需理解语义而非字面匹配，例如「屏幕不亮」应匹配「显示故障」类知识。\n"
                "2. 判断这些知识是否足以回答用户问题。\n\n"
                "请输出 JSON：\n"
                '{{"selected_ids":["id1","id2"],"is_sufficient":true/false,'
                '"sufficiency_score":0.0-1.0,"reason":"理由","missing_aspects":["缺失方面"]}}\n\n'
                "只输出 JSON，不要其他文字。"
            )
            response = gateway.chat_sync(prompt, temperature=0.2, max_tokens=400)
            import json as _json
            data = _json.loads(response)
            return data
        except Exception:
            # 降级：按 n-gram 相关度取前 5 条，保守判断
            sorted_candidates = sorted(
                candidates,
                key=lambda c: c.get("relevance_score", 0),
                reverse=True,
            )
            return {
                "selected_ids": [c["id"] for c in sorted_candidates[:5]],
                "is_sufficient": len(candidates) >= 2,
                "sufficiency_score": 0.5,
                "reason": "语义检索异常，规则兜底",
                "missing_aspects": [],
            }

    # ═══════════════════ 消费者端 ═══════════════════════

    @staticmethod
    async def send_message(
        db: AsyncSession,
        consumer_id: str,
        session_id: str | None,
        order_id: str | None,
        content: str,
        image_urls: list[str] | None = None,
    ) -> dict:
        """消费者发送咨询消息

        新流程（错别字纠正 + 语义检索 + 先分级再分叉）：
        0. 错别字纠正 → 1 次 LLM（修正文本仅用于 AI 理解）
        1. 意图识别 → RAG 粗召回(n-gram) → 语义精排+充分性判断(1 次 LLM)
        2. 预分级（意图×敏感词×检索充分性） → 分叉：
           L1: AI 生成回复 → 质量自评 → 直接发给用户
           L2: AI 生成草稿 → 仅客服可见，用户看到"客服处理中"占位
           L3: 跳过生成 → 直接转人工，用户看到"已转人工"提示

        LLM 调用次数：L1=5 / L2=4 / L3=3（含错别字纠正）
        """
        if image_urls is None:
            image_urls = []

        # 1. 获取或创建会话
        if session_id:
            conv_result = await db.execute(
                select(Conversation).where(
                    Conversation.id == session_id,
                    Conversation.consumer_id == consumer_id,
                )
            )
            conversation = conv_result.scalar_one_or_none()
            if conversation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="会话不存在或无权访问",
                )
        else:
            conversation = Conversation(
                id=uuid.uuid4().hex,
                consumer_id=consumer_id,
                order_id=order_id,
                status="AI进行中",
                priority="普通",
                message_count=0,
            )
            db.add(conversation)
            await db.flush()

        # 2. 保存用户消息
        user_msg_id = uuid.uuid4().hex
        user_msg_created_at = datetime.now(timezone.utc)
        user_msg = Message(
            id=user_msg_id,
            conversation_id=conversation.id,
            sender_type="consumer",
            sender_id=consumer_id,
            msg_type="text",
            content=content,
            image_urls=image_urls if image_urls else None,
            created_at=user_msg_created_at,
        )
        db.add(user_msg)

        # ── 判断是否需要 AI 介入 ──
        skip_ai = conversation.status != "AI进行中"

        if skip_ai:
            conversation.message_count = (conversation.message_count or 0) + 1
            await db.flush()

            import logging
            logging.getLogger(__name__).info(
                f"[ChatService] skip_ai: status={conversation.status}, "
                f"staff_id={conversation.staff_id}, consumer_id={consumer_id}"
            )

            return {
                "message_id": user_msg_id,
                "session_id": conversation.id,
                "content": content,
                "ai_reply": None,
                "intent": None,
                "intent_level": None,
                "confidence": None,
                "suggestions": [],
                "transfer_status": None,
                "is_transferred": False,
                "created_at": format_dt(user_msg_created_at),
            }

        # ── AI 管线（仅 "AI进行中" 状态执行） ──
        #
        # 优化策略（v2）：减少关键路径上的串行 LLM 调用
        #   旧: typo(1) → intent(1) → RAG(0) → rerank(1) → pre_grade(0) → suggestions(1) → generate(1) → quality(1)
        #       关键路径 = 6 次串行 LLM ≈ 6-12s
        #   新: typo(跳过短消息) → parallel(intent(1), RAG(0)) → rerank(跳过高置信度) → pre_grade(0)
        #        → parallel(generate(1), suggestions(1)) → quality(跳过L2/L3)
        #       关键路径 = 2-3 次串行 LLM ≈ 2-4s

        # 3. 错别字纠正（短消息跳过，embedding 检索 + LLM 生成对错别字有天然容错）
        ai_query = content
        if len(content) > 20:
            try:
                ai_query, was_corrected = ChatService._correct_typos(content)
            except Exception:
                ai_query = content

        # 4. 并行：意图识别(LLM) + RAG检索(embedding)，互不依赖 → 节省 ~1.5s
        try:
            intent_future = asyncio.to_thread(ChatService._run_intent_engine, ai_query)
            rag_future = ChatService._run_rag_engine(db, ai_query)
            intent_raw, knowledge_items = await asyncio.gather(
                intent_future, rag_future, return_exceptions=True,
            )
            intent = intent_raw if not isinstance(intent_raw, Exception) else \
                {"intent": "咨询", "level": "L1", "confidence": 0.5}
            knowledge_items = knowledge_items if not isinstance(knowledge_items, Exception) else []
        except Exception:
            try:
                intent = ChatService._run_intent_engine(ai_query)
            except Exception:
                intent = {"intent": "咨询", "level": "L1", "confidence": 0.5}
            try:
                knowledge_items = await ChatService._run_rag_engine(db, ai_query)
            except Exception:
                knowledge_items = []

        # 5. 语义精排：仅 embedding 低置信度时触发 LLM 精排（节省 ~1s，~70% 场景可跳过）
        top_emb_score = max((k.get("relevance_score", 0) for k in knowledge_items), default=0)
        if top_emb_score > 0.55 and len(knowledge_items) >= 1:
            # embedding 高置信度 → 直接信任向量检索结果
            reranked_items = sorted(
                knowledge_items, key=lambda k: k.get("relevance_score", 0), reverse=True
            )[:5]
            sufficiency = {
                "is_sufficient": len(reranked_items) >= 1,
                "sufficiency_score": min(0.8, top_emb_score),
                "reason": f"embedding 高置信度(top={top_emb_score:.2f})，跳过语义精排",
                "missing_aspects": [],
            }
        else:
            # embedding 不够自信或无结果 → LLM 精排兜底
            rerank_result = ChatService._semantic_rerank_and_validate(ai_query, knowledge_items)
            selected_ids = set(rerank_result.get("selected_ids", []))
            reranked_items = [k for k in knowledge_items if k["id"] in selected_ids]
            if not reranked_items:
                reranked_items = knowledge_items[:5]
            sufficiency = {
                "is_sufficient": rerank_result.get("is_sufficient", len(reranked_items) >= 2),
                "sufficiency_score": rerank_result.get("sufficiency_score", 0.5),
                "reason": rerank_result.get("reason", ""),
                "missing_aspects": rerank_result.get("missing_aspects", []),
            }

        # 6. ⭐ 预分级（不含质量维度，在生成回复之前分叉）
        try:
            grade = IntentEngine.pre_grade(
                intent=intent.get("intent", "咨询"),
                confidence=intent.get("confidence", 0.5),
                is_sensitive=intent.get("is_sensitive", False),
                validation_score=sufficiency["sufficiency_score"],
                query_text=content,
            )
            final_level = grade["level"]
            level_reason = grade["level_reason"]
        except Exception as e:
            final_level = intent.get("level", "L1")
            level_reason = "预分级异常，回退为意图分级"

        # ── 分叉处理 ──
        ai_confidence = 0.0
        quality_data = None
        suggestions: list[str] = []

        if final_level == "L3":
            # ═══ L3：完全转人工，不调用生成 LLM ═══
            ai_reply_text = "您的问题已转接人工客服，请稍候，客服将尽快为您处理。"
            ai_confidence = 0.0
            ai_sender_type = "system"
            conversation.status = "待客服接手"
            conversation.priority = "紧急"
            transfer_status = "pending"
            conversation.intent_level = "L3"

            # 系统提示消息
            ai_msg = Message(
                id=uuid.uuid4().hex,
                conversation_id=conversation.id,
                sender_type="system",
                sender_id=None,
                msg_type="system_notice",
                content=ai_reply_text,
                ai_metadata={
                    "intent": intent,
                    "knowledge": reranked_items,
                    "validation": {
                        "is_sufficient": sufficiency["is_sufficient"],
                        "sufficiency_score": sufficiency["sufficiency_score"],
                        "reason": sufficiency["reason"],
                    },
                    "level": "L3",
                    "level_reason": level_reason,
                },
                created_at=datetime.now(timezone.utc),
            )

        elif final_level == "L2":
            # ═══ L2：AI 生成草稿（仅客服可见），用户看到占位消息 ═══
            try:
                draft_text, draft_confidence = ChatService._run_ai_reply_generation(ai_query, intent, reranked_items)
            except Exception:
                draft_text = "您好！已收到您的消息，客服正在查看中..."
                draft_confidence = 0.3
            ai_confidence = draft_confidence

            # 消费者看到的占位消息
            consumer_placeholder = "客服正在为您处理中，请稍候..."

            # AI 草稿存为 ai_draft（对消费者不可见）
            draft_msg = Message(
                id=uuid.uuid4().hex,
                conversation_id=conversation.id,
                sender_type="ai_draft",
                sender_id=None,
                msg_type="text",
                content=draft_text,
                ai_metadata={
                    "intent": intent,
                    "knowledge": reranked_items,
                    "reply_confidence": draft_confidence,
                    "validation": {
                        "is_sufficient": sufficiency["is_sufficient"],
                        "sufficiency_score": sufficiency["sufficiency_score"],
                        "reason": sufficiency["reason"],
                    },
                    "level": "L2",
                    "level_reason": level_reason,
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(draft_msg)

            # 消费者看到的系统消息
            ai_msg = Message(
                id=uuid.uuid4().hex,
                conversation_id=conversation.id,
                sender_type="system",
                sender_id=None,
                msg_type="system_notice",
                content=consumer_placeholder,
                ai_metadata={
                    "intent": intent,
                    "level": "L2",
                    "level_reason": level_reason,
                },
                created_at=datetime.now(timezone.utc),
            )
            ai_reply_text = consumer_placeholder
            ai_sender_type = "system"
            conversation.status = "待客服确认"
            conversation.priority = "重要"
            transfer_status = "pending_approval"
            conversation.intent_level = "L2"

        else:
            # ═══ L1：AI 全自动回复 ═══
            # 并行：AI 回复生成 + 建议追问（互不依赖 → 节省 ~1s）
            try:
                reply_fut = asyncio.to_thread(
                    ChatService._run_ai_reply_generation, ai_query, intent, reranked_items
                )
                sugg_fut = asyncio.to_thread(
                    ChatService._run_suggestions, ai_query, intent, reranked_items
                )
                (ai_reply_text, ai_confidence), suggestions = await asyncio.gather(
                    reply_fut, sugg_fut, return_exceptions=True,
                )
                if isinstance((ai_reply_text, ai_confidence), Exception):
                    raise Exception(str(ai_reply_text))
                if isinstance(suggestions, Exception) or not suggestions:
                    suggestions = ChatService._run_suggestions(ai_query, intent, reranked_items)
            except Exception:
                try:
                    ai_reply_text, ai_confidence = ChatService._run_ai_reply_generation(
                        ai_query, intent, reranked_items
                    )
                except Exception:
                    ai_reply_text = "您好！已收到您的消息，我们会尽快处理。"
                    ai_confidence = 0.3
                suggestions = ChatService._run_suggestions(ai_query, intent, reranked_items)

            # 质量自评：不阻塞关键路径，降级时静默跳过
            # （L1 全自动回复场景可用满意度评分替代自评，节省 1 次 LLM ≈ 2s）
            quality_data = None

            ai_msg = Message(
                id=uuid.uuid4().hex,
                conversation_id=conversation.id,
                sender_type="ai",
                sender_id=None,
                msg_type="text",
                content=ai_reply_text,
                ai_metadata={
                    "intent": intent,
                    "knowledge": reranked_items,
                    "reply_confidence": ai_confidence,
                    "validation": {
                        "is_sufficient": sufficiency["is_sufficient"],
                        "sufficiency_score": sufficiency["sufficiency_score"],
                        "reason": sufficiency["reason"],
                        "missing_aspects": sufficiency["missing_aspects"],
                    },
                    "quality": quality_data,
                    "level": "L1",
                    "level_reason": level_reason,
                },
                created_at=datetime.now(timezone.utc),
            )
            ai_sender_type = "ai"
            conversation.status = "AI进行中"
            conversation.priority = "普通"
            transfer_status = None
            conversation.intent_level = "L1"

        # 更新会话
        conversation.message_count = (conversation.message_count or 0) + 2
        db.add(ai_msg)
        await db.flush()

        return {
            "message_id": user_msg_id,
            "session_id": conversation.id,
            "content": content,
            "ai_reply": ai_reply_text,
            "intent": intent.get("intent"),
            "intent_level": final_level,
            "intent_level_reason": level_reason,
            "confidence": intent.get("confidence"),
            "suggestions": suggestions,
            "transfer_status": transfer_status,
            "quality_score": (quality_data or {}).get("overall_score"),
            "quality_acceptable": (quality_data or {}).get("is_acceptable"),
            "created_at": format_dt(user_msg_created_at),
        }

    @staticmethod
    async def get_history(
        db: AsyncSession,
        session_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """获取会话历史消息"""
        # 验证会话存在
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        if conv_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )

        # 查询消息计数（排除 ai_draft）
        count_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == session_id,
                Message.sender_type != "ai_draft",
            )
        )
        total = count_result.scalar() or 0

        # 查询消息（排除 ai_draft 草稿，消费者不可见）
        offset = (page - 1) * page_size
        msg_result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == session_id,
                Message.sender_type != "ai_draft",
            )
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        messages = msg_result.scalars().all()

        items = []
        for m in messages:
            items.append({
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type,
                "content": m.content,
                "image_urls": m.image_urls,
                "ai_metadata": m.ai_metadata,
                "created_at": format_dt(m.created_at) or "",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def transfer_to_human(
        db: AsyncSession,
        session_id: str,
    ) -> dict:
        """消费者请求转接人工"""
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )

        conversation.status = "待客服接手"
        conversation.priority = "紧急"
        if not conversation.intent_level:
            conversation.intent_level = "L3"

        # 添加系统消息
        sys_msg = Message(
            id=uuid.uuid4().hex,
            conversation_id=conversation.id,
            sender_type="system",
            sender_id=None,
            msg_type="system_notice",
            content="用户请求转接人工客服",
            created_at=datetime.now(timezone.utc),
        )
        db.add(sys_msg)
        await db.flush()

        return {
            "message": "已转接人工客服",
            "session_id": session_id,
            "transfer_status": "pending",
        }

    # ═══════════════════ 客服端 ═══════════════════════

    @staticmethod
    async def get_conversations(
        db: AsyncSession,
        staff_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """客服端获取会话列表（含消费者信息）"""
        base_query = select(Conversation)
        count_query = select(func.count(Conversation.id))

        if staff_id:
            base_query = base_query.where(Conversation.staff_id == staff_id)
            count_query = count_query.where(Conversation.staff_id == staff_id)
        if status:
            base_query = base_query.where(Conversation.status == status)
            count_query = count_query.where(Conversation.status == status)
        if priority:
            base_query = base_query.where(Conversation.priority == priority)
            count_query = count_query.where(Conversation.priority == priority)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await db.execute(
            base_query.order_by(Conversation.updated_at.desc().nullslast(), Conversation.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        conversations = result.scalars().all()

        items = []
        for conv in conversations:
            # 获取消费者信息
            consumer_result = await db.execute(
                select(Consumer).where(Consumer.id == conv.consumer_id)
            )
            consumer = consumer_result.scalar_one_or_none()

            # 获取最后一条消息
            last_msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg = last_msg_result.scalar_one_or_none()

            items.append({
                "id": conv.id,
                "consumer_name": consumer.nickname if consumer else None,
                "consumer_avatar": consumer.avatar if consumer else None,
                "last_message": last_msg.content[:100] if last_msg else None,
                "status": conv.status,
                "intent_level": conv.intent_level,
                "priority": conv.priority,
                "message_count": conv.message_count or 0,
                "unread_count": 0,
                "created_at": format_dt(conv.created_at) or "",
                "updated_at": format_dt(conv.updated_at),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def get_conversation_detail(
        db: AsyncSession,
        conversation_id: str,
    ) -> dict:
        """获取会话详情（含消息历史 + AI 建议回复）"""
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )

        # 消费者信息
        consumer_result = await db.execute(
            select(Consumer).where(Consumer.id == conversation.consumer_id)
        )
        consumer = consumer_result.scalar_one_or_none()

        # 消息历史（含 ai_draft，客服需要看到待审批草稿）
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        message_items = []
        pending_draft = None
        for m in messages:
            # ai_draft 单独提取，不在消息流中展示
            if m.sender_type == "ai_draft":
                pending_draft = {
                    "id": m.id,
                    "content": m.content,
                    "ai_metadata": m.ai_metadata,
                    "created_at": format_dt(m.created_at) or "",
                }
                continue
            message_items.append({
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type,
                "content": m.content,
                "image_urls": m.image_urls,
                "ai_metadata": m.ai_metadata,
                "created_at": format_dt(m.created_at) or "",
            })

        # 生成 AI 推荐回复（走 ai_engine 上下文动态生成）
        try:
            recent_messages = [
                f"[{m.sender_type}] {m.content}" for m in messages[-10:]
            ]
            # 注入订单上下文
            order_context = ""
            if conversation.order_id:
                try:
                    from app.models.product_models import Order, OrderDetail
                    ord_result = await db.execute(
                        select(Order).where(Order.id == conversation.order_id)
                    )
                    order = ord_result.scalar_one_or_none()
                    if order:
                        detail_result = await db.execute(
                            select(OrderDetail).where(OrderDetail.order_id == order.id).limit(1)
                        )
                        detail = detail_result.scalar_one_or_none()
                        order_context = f"用户购买的商品是「{detail.product_name if detail else ''}」"
                except Exception:
                    pass
            rag = ChatService._get_rag_engine()
            ai_suggestions = rag.suggest_replies(
                recent_messages=recent_messages,
                intent_level=conversation.intent_level or "L1",
                priority=conversation.priority or "普通",
                order_context=order_context,
            )
        except Exception:
            # 降级：按意图等级返回固定话术
            try:
                ai_suggestions = ChatService._get_rag_engine()._fallback_suggestions(conversation.intent_level or "L1")
            except Exception:
                ai_suggestions = [
                    "您好，关于您反映的问题，我们非常重视。请提供一下您的订单号，我们马上为您查询处理。",
                    "已为您登记了售后申请，预计1-3个工作日内会有专人联系您核实处理。",
                    "非常抱歉给您带来了不便，我们会立即为您协调处理。如需其他帮助请随时告知。",
                ]

        return {
            "id": conversation.id,
            "consumer_id": conversation.consumer_id,
            "consumer_name": consumer.nickname if consumer else None,
            "consumer_avatar": consumer.avatar if consumer else None,
            "order_id": conversation.order_id,
            "status": conversation.status,
            "intent_level": conversation.intent_level,
            "priority": conversation.priority,
            "messages": message_items,
            "pending_draft": pending_draft,
            "ai_suggestions": ai_suggestions,
            "created_at": format_dt(conversation.created_at) or "",
        }

    @staticmethod
    async def staff_reply(
        db: AsyncSession,
        conversation_id: str,
        staff_id: str,
        content: str,
    ) -> dict:
        """客服发送回复"""
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )

        # 更新会话状态
        if conversation.status in ("待客服接手", "AI进行中", "待客服确认"):
            conversation.status = "客服处理中"
        if conversation.staff_id is None:
            conversation.staff_id = staff_id
        conversation.message_count = (conversation.message_count or 0) + 1

        # 保存消息（显式 created_at 用 UTC，与 AI/consumer 消息时间基准一致）
        msg = Message(
            id=uuid.uuid4().hex,
            conversation_id=conversation.id,
            sender_type="staff",
            sender_id=staff_id,
            msg_type="text",
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)

        # 创建服务记录
        record = ServiceRecord(
            id=uuid.uuid4().hex,
            staff_id=staff_id,
            action="回复",
            target_type="conversation",
            target_id=conversation.id,
            detail=content[:200],
        )
        db.add(record)
        await db.flush()

        return {
            "id": msg.id,
            "sender_type": msg.sender_type,
            "sender_id": msg.sender_id,
            "msg_type": msg.msg_type,
            "content": msg.content,
            "image_urls": msg.image_urls,
            "ai_metadata": msg.ai_metadata,
            "created_at": format_dt(msg.created_at) or "",
        }

    @staticmethod
    async def close_conversation(
        db: AsyncSession,
        conversation_id: str,
        staff_id: str,
    ) -> dict:
        """关闭会话"""
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在",
            )

        conversation.status = "已关闭"
        conversation.staff_id = staff_id
        conversation.closed_at = datetime.now(timezone.utc)

        # 添加系统消息
        sys_msg = Message(
            id=uuid.uuid4().hex,
            conversation_id=conversation.id,
            sender_type="system",
            sender_id=None,
            msg_type="system_notice",
            content=f"会话已由客服关闭",
            created_at=datetime.now(timezone.utc),
        )
        db.add(sys_msg)

        # 服务记录
        record = ServiceRecord(
            id=uuid.uuid4().hex,
            staff_id=staff_id,
            action="关闭",
            target_type="conversation",
            target_id=conversation.id,
            detail="关闭会话",
        )
        db.add(record)
        await db.flush()

        # 尝试触发进化分析（mock）
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[EvolutionEngine] Mock summarize for conversation {conversation_id}")
        except Exception:
            pass

        return {
            "status": "已关闭",
            "conversation_id": conversation_id,
            "closed_at": format_dt(datetime.now(timezone.utc)),
        }
