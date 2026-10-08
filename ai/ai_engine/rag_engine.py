"""RAG 检索增强生成引擎 — 向量语义检索 + Prompt 组装 + LLM 生成"""

import re
import numpy as np
from typing import Optional
from dataclasses import dataclass, field
from ai_engine.llm_gateway import LLMGateway


@dataclass
class KnowledgeFragment:
    id: str
    title: str
    content: str
    source: str = "knowledge_base"
    relevance_score: float = 1.0


@dataclass
class ValidationResult:
    """结果校验结果"""
    is_sufficient: bool          # 检索到的知识是否足以回答
    sufficiency_score: float     # 充分性评分 0-1
    reason: str = ""             # 校验理由
    missing_aspects: list[str] = field(default_factory=list)  # 缺失的方面


@dataclass
class RagResponse:
    reply: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class QualityAssessment:
    """质量自评结果"""
    overall_score: float         # 综合质量分 0-1
    accuracy: float              # 准确性 0-1
    completeness: float          # 完整性 0-1
    helpfulness: float           # 有帮助性 0-1
    is_acceptable: bool          # 是否合格（≥0.6 为合格）
    issues: list[str] = field(default_factory=list)   # 发现的问题
    suggestion: str = ""         # 改进建议


class RAGEngine:
    """RAG 引擎 — embedding 向量语义检索 + LLM 生成"""

    RAG_PROMPT = """你是一个专业的电商售后客服。请根据以下知识库内容回答用户问题。

【知识库内容】
{fragments}

【对话历史】
{history}

【用户问题】
{query}

【回答要求】
1. 如果知识库中有确切答案，请引用具体内容
2. 如果不确定或知识库没有相关信息，请坦诚说明
3. 回答要友好、专业、简洁
4. 在回复末尾标注信息来源
5. 可以用 **粗体** 强调关键信息（如金额、时效），用 - 或 1. 列条目
6. 禁止使用 # 标题、代码块、表格，也不要输出 JSON 格式

请直接回复用户的问题。"""

    GENERAL_KNOWLEDGE_PROMPT = """你是一个专业的电商售后客服助手。当前知识库中没有找到与用户问题直接匹配的内容，请运用你的通用知识来回答。

【对话历史】
{history}

【用户问题】
{query}

【回答要求】
1. 基于你的通用电商售后知识给出有帮助的回答
2. 如果不确定，请坦诚说明并建议转人工
3. 回答要友好、专业、简洁
4. **必须**在回复末尾添加提示：「💡 以上回复基于通用知识，非官方知识库内容，仅供参考。如需准确信息，请回复"转人工"。」
5. 可以用 **粗体** 强调关键信息，用 - 或数字列条目
6. 禁止使用 # 标题、代码块、表格，也不要输出 JSON 格式

请直接回复用户的问题。"""

    VALIDATE_PROMPT = """你是电商售后知识检索的质量审核员。请判断以下检索到的知识片段是否足以回答用户问题。

【用户问题】
{query}

【检索到的知识片段】（共 {count} 条）
{fragments_summary}

【判断标准】
1. 知识片段是否与用户问题直接相关？
2. 知识片段是否包含具体的操作步骤/政策说明？
3. 是否有遗漏的关键方面（如退款金额、时效、条件等）？

请输出 JSON：
{{
  "is_sufficient": true/false,
  "sufficiency_score": 0.0-1.0,
  "reason": "简要说明判断理由",
  "missing_aspects": ["缺失方面1", "缺失方面2"]
}}

只输出 JSON，不要其他文字。"""

    ASSESS_QUALITY_PROMPT = """你是电商客服AI回复的质量审核员。请对以下AI生成的回复进行质量自评。

【用户问题】
{query}

【AI生成的回复】
{reply}

【可参考的知识】
{fragments_summary}

【评分标准】（每项 0.0-1.0）
1. 准确性(accuracy)：回复内容是否事实正确、无编造
2. 完整性(completeness)：是否覆盖了用户问题的所有关键方面
3. 有帮助性(helpfulness)：是否对用户解决实际问题有帮助

请输出 JSON：
{{
  "accuracy": 0.0-1.0,
  "completeness": 0.0-1.0,
  "helpfulness": 0.0-1.0,
  "issues": ["发现的问题"],
  "suggestion": "改进建议（若无需改进则为空）"
}}

只输出 JSON，不要其他文字。"""

    SUGGEST_REPLY_PROMPT = """你是电商客服的智能助手。请根据当前对话上下文，为人工客服生成 3 条推荐的回复话术。

【会话意图】{intent_level}
【会话优先级】{priority}
【订单上下文】{order_context}

【最近对话】
{recent_messages}

【生成要求】
1. 每条推荐回复应贴合对话上下文，针对用户的具体问题
2. 回复风格专业、友好、有同理心
3. 如果对话涉及投诉/售后，优先安抚情绪并给出处理路径
4. 如果已知用户购买的商品名称，可以自然提及；**严禁**在回复中出现订单号
5. **禁止**使用模板化的句式如「针对您提到的…问题」，每条回复的语言风格应自然多样
6. 每条回复控制在 1-3 句话，直接可用

请输出 JSON 数组（恰好 3 条）：
[
  "推荐回复1",
  "推荐回复2",
  "推荐回复3"
]

只输出 JSON 数组，不要其他文字。"""

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.gateway = gateway
        self._knowledge_items: list[dict] = []
        # 向量检索缓存：预计算的 embedding 矩阵 + 对齐的 ID 列表
        self._item_vectors: np.ndarray | None = None
        self._item_ids: list[str] = []

    def load_knowledge_items(self, items: list[dict]):
        """加载知识库条目并预计算 embedding 向量

        每次调用都会重新编码所有条目。如果 gateway 不可用则跳过向量化，
        retrieve() 将降级为 n-gram 关键词匹配。
        """
        self._knowledge_items = items

        if not items or self.gateway is None:
            self._item_vectors = None
            self._item_ids = []
            return

        # 拼接 title + content 作为编码文本
        texts = [
            f"{item.get('title', '')} {item.get('content', '')[:500]}"
            for item in items
        ]
        try:
            vectors = self.gateway.embed(texts)
            self._item_vectors = np.array(vectors, dtype=np.float32)
            self._item_ids = [str(item.get("id", "")) for item in items]
        except Exception:
            # embedding 失败时降级为 n-gram 关键词检索
            self._item_vectors = None
            self._item_ids = []

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """从中文文本中提取关键词（2-4 gram 滑动窗口）"""
        cleaned = re.findall(r"[一-鿿\w]+", text.lower())
        keywords = set()
        for chunk in cleaned:
            if re.match(r"^\w+$", chunk) and not re.match(r"^[一-鿿]", chunk):
                keywords.add(chunk)
                continue
            for n in (2, 3, 4):
                for i in range(len(chunk) - n + 1):
                    keywords.add(chunk[i:i + n])
        return keywords

    def retrieve(self, query: str, top_k: int = 5, knowledge_type: Optional[str] = None) -> list[KnowledgeFragment]:
        """向量语义检索：query embedding × 知识库向量 → cosine 相似度排序

        与旧 n-gram 关键词匹配的根本区别：
        - "屏幕不亮" 能匹配到 "显示故障" 类知识（语义相近，但无共同字）
        - 自动处理同义词、近义词、不同表述方式
        - 不受分词/断句影响

        降级链：向量检索 → n-gram 关键词匹配（gateway 不可用或编码失败时）
        """
        if not self._knowledge_items:
            return []

        # ── 主路径：embedding 向量检索 ──
        if self._item_vectors is not None and len(self._item_vectors) > 0:
            try:
                query_vec = np.array(self.gateway.embed([query])[0], dtype=np.float32)

                # 归一化向量直接点积 = cosine 相似度
                scores = np.dot(self._item_vectors, query_vec)
                score_mean = float(np.mean(scores))
                score_std = float(np.std(scores))

                # 动态阈值：显著高于均值的才算语义相关
                # "屏幕不亮了" vs 知识库均值≈0.34，max≈0.39，全部过滤
                # "我想退货" vs 知识库均值≈0.46，max≈0.67，相关条目高于均值+1σ=0.58
                # 基线 0.42 过滤同领域噪声（"屏幕不亮"vs"退换货政策"≈0.40），
                # 均值+0.5σ 在相关查询中提升阈值（"退款"均值≈0.46→阈值≈0.53）
                dynamic_threshold = max(0.42, score_mean + score_std * 0.5)

                top_indices = np.argsort(scores)[::-1]
                results = []
                for idx in top_indices:
                    score = float(scores[idx])
                    if score < dynamic_threshold and len(results) >= 1:
                        break  # 低于动态阈值且已有结果，停止
                    if score < dynamic_threshold and len(results) == 0:
                        # 第一条都低于阈值 → 确实没有相关内容
                        break
                    if len(results) >= top_k:
                        break
                    item = self._knowledge_items[idx]
                    if knowledge_type and item.get("type") and item["type"] != knowledge_type:
                        continue
                    results.append(KnowledgeFragment(
                        id=str(item.get("id", "")),
                        title=str(item.get("title", "")),
                        content=str(item.get("content", "")),
                        relevance_score=score,
                    ))
                if results:
                    return results
                # 无结果说明知识库没有相关内容，走 LLM 通用知识兜底
                # 不降级到 n-gram（向量结果比 n-gram 更可靠）
            except Exception:
                pass  # 向量检索异常 → 降级到 n-gram

        # ── 降级路径：n-gram 关键词匹配 ──
        return self._keyword_retrieve(query, top_k)

    def _keyword_retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeFragment]:
        """n-gram 关键词检索（embedding 不可用时的降级方案）"""
        results = []
        query_keywords = self._extract_keywords(query)

        for item in self._knowledge_items:
            content = item.get("content", "") + item.get("title", "")
            content_keywords = self._extract_keywords(content)
            overlap = len(query_keywords & content_keywords)

            if overlap > 0:
                score = overlap / max(len(query_keywords), 1)
                results.append(KnowledgeFragment(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    relevance_score=score,
                ))

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def validate_retrieval(self, query: str, fragments: list[KnowledgeFragment]) -> ValidationResult:
        """结果校验：LLM 判断检索到的知识片段是否足以回答用户问题（检索后、生成前）

        注意：无知识片段时 sufficiency_score 返回 0.5（中性"未知"），而非 0.0（"确定不足"）。
        "无匹配"对闲聊/一般咨询是正常的，GLM 通用知识兜底即可，不应触发分级升级。
        """
        if not fragments:
            return ValidationResult(
                is_sufficient=False,
                sufficiency_score=0.5,
                reason="未检索到任何相关知识片段，将使用通用知识回答",
                missing_aspects=["所有方面"],
            )
        if self.gateway is None:
            # 无 LLM 时使用规则降级：高相关性+多条结果=充分
            avg_score = sum(f.relevance_score for f in fragments) / len(fragments)
            is_sufficient = avg_score >= 0.3 and len(fragments) >= 2
            return ValidationResult(
                is_sufficient=is_sufficient,
                sufficiency_score=avg_score,
                reason="规则降级校验",
            )
        try:
            return self._llm_validate(query, fragments)
        except Exception:
            # LLM 故障时保守判断为可能不够
            return ValidationResult(
                is_sufficient=len(fragments) >= 2,
                sufficiency_score=0.5,
                reason="LLM 校验异常，规则兜底",
            )

    def _llm_validate(self, query: str, fragments: list[KnowledgeFragment]) -> ValidationResult:
        """LLM 质量校验：判断知识片段是否充分"""
        import json as _json
        fragments_summary = "\n".join(
            f"{i+1}. [{f.title}] (相关性:{f.relevance_score:.2f}) {f.content[:150]}..."
            for i, f in enumerate(fragments[:5])
        )
        prompt = self.VALIDATE_PROMPT.format(
            query=query,
            count=len(fragments),
            fragments_summary=fragments_summary,
        )
        response = self.gateway.chat_sync(prompt, temperature=0.2, max_tokens=300)
        data = _json.loads(response)
        return ValidationResult(
            is_sufficient=data.get("is_sufficient", True),
            sufficiency_score=float(data.get("sufficiency_score", 0.7)),
            reason=data.get("reason", ""),
            missing_aspects=data.get("missing_aspects", []),
        )

    def assess_quality(self, query: str, reply: str, fragments: list[KnowledgeFragment] | None = None) -> QualityAssessment:
        """质量自评：LLM 对已生成的回复进行准确/完整/有帮助三维评分"""
        if self.gateway is None:
            return QualityAssessment(
                overall_score=0.7, accuracy=0.7, completeness=0.7, helpfulness=0.7,
                is_acceptable=True, issues=[], suggestion="规则降级自评",
            )
        try:
            return self._llm_assess_quality(query, reply, fragments or [])
        except Exception:
            # LLM 故障时保守通过
            return QualityAssessment(
                overall_score=0.65, accuracy=0.65, completeness=0.65, helpfulness=0.65,
                is_acceptable=True, issues=[], suggestion="LLM 自评异常，保守通过",
            )

    def _llm_assess_quality(self, query: str, reply: str, fragments: list[KnowledgeFragment]) -> QualityAssessment:
        """LLM 质量自评"""
        import json as _json
        fragments_summary = "无"
        if fragments:
            fragments_summary = "\n".join(
                f"{i+1}. [{f.title}] {f.content[:200]}"
                for i, f in enumerate(fragments[:3])
            )
        prompt = self.ASSESS_QUALITY_PROMPT.format(
            query=query,
            reply=reply,
            fragments_summary=fragments_summary,
        )
        response = self.gateway.chat_sync(prompt, temperature=0.2, max_tokens=300)
        data = _json.loads(response)
        accuracy = float(data.get("accuracy", 0.7))
        completeness = float(data.get("completeness", 0.7))
        helpfulness = float(data.get("helpfulness", 0.7))
        overall = round((accuracy + completeness + helpfulness) / 3, 2)
        is_acceptable = overall >= 0.6
        return QualityAssessment(
            overall_score=overall,
            accuracy=accuracy,
            completeness=completeness,
            helpfulness=helpfulness,
            is_acceptable=is_acceptable,
            issues=data.get("issues", []),
            suggestion=data.get("suggestion", ""),
        )

    # 常见订单号格式，用于生成后过滤（避免 LLM 从对话历史中复述）
    _ORDER_NO_PATTERN = re.compile(
        r'(?:订单号|订单编号|order[_ ]?(id|no|sn)?)\s*[：:]\s*[A-Za-z0-9\-]+|'
        r'(?:#|No\.)\s*[A-Z]{2,4}\d{6,}|'
        r'\bORD\d{8,}\b|'
        r'\b[A-Z]{2,4}\d{10,}\b'
    )

    @classmethod
    def _strip_order_numbers(cls, text: str) -> str:
        """移除回复中可能出现的订单号"""
        return cls._ORDER_NO_PATTERN.sub('', text).strip()

    def suggest_replies(
        self,
        recent_messages: list[str],
        intent_level: str = "L1",
        priority: str = "普通",
        order_context: str = "",
    ) -> list[str]:
        """上下文推荐回复生成：根据最近对话 + 意图 + 优先级 + 订单上下文，为人工客服生成 3 条推荐回复"""
        if self.gateway is None:
            return self._fallback_suggestions(intent_level)
        try:
            results = self._llm_suggest_replies(recent_messages, intent_level, priority, order_context)
            return [self._strip_order_numbers(r) for r in results]
        except Exception:
            return self._fallback_suggestions(intent_level)

    def _llm_suggest_replies(
        self,
        recent_messages: list[str],
        intent_level: str,
        priority: str,
        order_context: str = "",
    ) -> list[str]:
        """LLM 生成上下文相关推荐回复"""
        import json as _json
        prompt = self.SUGGEST_REPLY_PROMPT.format(
            intent_level=intent_level,
            priority=priority,
            order_context=order_context or "无",
            recent_messages="\n".join(recent_messages[-10:]),
        )
        response = self.gateway.chat_sync(prompt, temperature=0.6, max_tokens=400)
        data = _json.loads(response)
        if isinstance(data, list) and len(data) >= 1:
            return data[:3]
        return self._fallback_suggestions(intent_level)

    def _fallback_suggestions(self, intent_level: str = "L1") -> list[str]:
        """降级：按意图级别返回固定推荐话术"""
        fallbacks = {
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
        return fallbacks.get(intent_level, fallbacks["L1"])

    def generate_reply(
        self,
        query: str,
        context: list[KnowledgeFragment],
        intent_result=None,
        conversation_history: Optional[list[dict]] = None,
    ) -> RagResponse:
        """LLM 生成回复：知识库命中 → RAG 增强回复；未命中 → LLM 通用知识兜底"""
        if not context:
            # 知识库无匹配 → 尝试 LLM 通用知识兜底
            if self.gateway is not None:
                try:
                    return self._generate_general_reply(query, conversation_history)
                except Exception:
                    pass
            return RagResponse(
                reply="抱歉，我暂时没有找到相关的信息来回答您的问题。建议您联系人工客服获取帮助。如需转人工，请回复「转人工」。",
                sources=[],
                confidence=0.3,
            )

        if self.gateway is None:
            return self._fallback_generate(query, context)

        try:
            return self._llm_generate(query, context, conversation_history)
        except Exception:
            return self._fallback_generate(query, context)

    def _llm_generate(
        self,
        query: str,
        fragments: list[KnowledgeFragment],
        conversation_history: Optional[list[dict]] = None,
    ) -> RagResponse:
        fragments_text = "\n\n---\n\n".join(
            f"[{f.title}]\n{f.content}" for f in fragments
        )
        history_text = ""
        if conversation_history:
            history_text = "\n".join(
                f"{h['role']}: {h['content']}" for h in conversation_history[-5:]
            )

        prompt = self.RAG_PROMPT.format(
            fragments=fragments_text,
            history=history_text or "无",
            query=query,
        )
        reply = self.gateway.chat_sync(prompt, temperature=0.5)
        sources = [f.title for f in fragments[:3]]
        return RagResponse(reply=reply, sources=sources, confidence=0.8)

    def _generate_general_reply(
        self,
        query: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> RagResponse:
        """LLM 通用知识兜底回复（知识库无匹配时）— 低置信度 + 免责声明"""
        history_text = ""
        if conversation_history:
            history_text = "\n".join(
                f"{h['role']}: {h['content']}" for h in conversation_history[-5:]
            )
        prompt = self.GENERAL_KNOWLEDGE_PROMPT.format(
            history=history_text or "无",
            query=query,
        )
        reply = self.gateway.chat_sync(prompt, temperature=0.5)
        return RagResponse(reply=reply, sources=[], confidence=0.45)

    def _fallback_generate(self, query: str, fragments: list[KnowledgeFragment]) -> RagResponse:
        """降级：直接拼接知识片段（LLM 不可用时）"""
        best = fragments[0]
        sources = [f.title for f in fragments[:3]]
        reply = f"您好！关于您的问题，根据我们的知识库：\n\n{best.content}\n\n"
        if len(fragments) > 1:
            reply += "此外，您可能还想了解：\n"
            for f in fragments[1:3]:
                reply += f"• {f.title}\n"
        reply += f"\n信息来源：{'、'.join(sources)}"
        return RagResponse(reply=reply, sources=sources, confidence=best.relevance_score)

    def build_prompt(self, query: str, fragments: list[KnowledgeFragment], intent: str) -> str:
        """构建 RAG Prompt 模板"""
        fragments_text = "\n\n---\n\n".join(f"[{f.title}]\n{f.content}" for f in fragments)
        return self.RAG_PROMPT.format(fragments=fragments_text, history="无", query=query)
