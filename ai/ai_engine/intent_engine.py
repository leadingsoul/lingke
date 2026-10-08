"""意图识别引擎 — LLM 驱动多类别意图分类 + L1/L2/L3 分级"""

import time
import json
import re
from typing import Optional
from dataclasses import dataclass, field
from ai_engine.llm_gateway import LLMGateway


@dataclass
class IntentResult:
    primary_intent: str          # 售前咨询 / 售后投诉 / 订单追踪 / 物流查询 / 退货退款 / 换货 / 维修 / 闲聊 / 其他
    sub_intent: str | None = None
    confidence: float = 1.0
    level: str = "L1"           # L1 / L2 / L3
    level_reason: str = ""
    keywords: list[str] = field(default_factory=list)
    is_sensitive: bool = False
    processing_time_ms: int = 0


class IntentEngine:
    """意图识别引擎 — 全量 LLM 调用（异常时降级为关键词匹配）"""

    INTENT_PROMPT = """你是一个电商客服意图识别助手。请分析用户消息，输出 JSON：
{{
  "intent": "售前咨询|售后投诉|订单追踪|物流查询|退货退款|换货|维修|闲聊|其他",
  "sub_intent": "具体子类别",
  "confidence": 0.0-1.0,
  "keywords": ["关键词1", "关键词2"],
  "is_sensitive": false
}}

规则：
- 售前咨询：询问商品信息、价格、优惠、使用方法等
- 售后投诉：投诉商品质量、服务态度等
- 订单追踪：查询订单状态、发货情况
- 物流查询：查询快递/物流进度
- 退货退款：明确要求退货或退款
- 换货：要求换货
- 维修：要求维修
- 闲聊：打招呼、感谢等
- is_sensitive: 涉及 12315/工商/诈骗/假货/有毒/致癌 等风险内容

用户消息：{message}
对话历史：{context}"""

    # 关键词降级匹配（仅在 LLM 异常时使用）
    _FALLBACK_PATTERNS = {
        "退货退款": [r"退货", r"退款", r"退钱", r"不要了"],
        "换货": [r"换货", r"换个", r"换一个"],
        "维修": [r"坏了", r"维修", r"修理", r"修一下", r"不亮了", r"不工作了"],
        "物流查询": [r"到哪里了", r"物流", r"快递", r"送到了", r"还没.*到", r"怎么.*还没"],
        "订单追踪": [r"订单", r"什么时候发货", r"发货了", r"还没发货"],
        "售后投诉": [r"投诉", r"差评", r"太差", r"骗人", r"假货", r"质量差"],
        "售前咨询": [r"多少钱", r"有优惠", r"怎么用", r"能.*吗", r"有什么", r"可以.*吗"],
    }

    SENSITIVE_PATTERNS = [
        r"(投诉|举报|工商|12315|315|维权|律师|诉讼|法院|曝光|报警)",
        r"(骗子|诈骗|假货|伪劣|三无|有毒|致癌)",
    ]

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def classify(self, message: str, context: Optional[str] = None) -> IntentResult:
        """意图识别：LLM 为主，异常时降级为关键词匹配"""
        start = time.time()
        try:
            result = self._llm_classify(message, context)
        except Exception:
            result = self._fallback_classify(message)
        result.processing_time_ms = int((time.time() - start) * 1000)
        return result

    def _llm_classify(self, message: str, context: Optional[str] = None) -> IntentResult:
        prompt = self.INTENT_PROMPT.format(message=message, context=context or "无")
        response = self.gateway.chat_sync(prompt, temperature=0.3)
        data = json.loads(response)
        intent = data.get("intent", "其他")
        confidence = float(data.get("confidence", 0.5))
        return IntentResult(
            primary_intent=intent,
            sub_intent=data.get("sub_intent"),
            confidence=confidence,
            level=self._urgency_level(intent, confidence),
            level_reason="LLM 分类",
            keywords=data.get("keywords", []),
            is_sensitive=data.get("is_sensitive", False),
        )

    def _fallback_classify(self, message: str) -> IntentResult:
        """关键词降级匹配（仅在 LLM 不可用时）"""
        for intent, patterns in self._FALLBACK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    keywords = re.findall(r"[一-鿿]{2,}", message)[:5]
                    return IntentResult(
                        primary_intent=intent,
                        confidence=0.85 if len(message) > 10 else 0.75,
                        level=self._urgency_level(intent, 0.85),
                        level_reason=f"降级：关键词匹配 {pattern}",
                        keywords=keywords,
                        is_sensitive=self._check_sensitive(message),
                    )
        return IntentResult(
            primary_intent="闲聊",
            confidence=0.6,
            level="L1",
            level_reason="降级：未匹配已知意图",
            keywords=re.findall(r"[一-鿿]{2,}", message)[:5],
            is_sensitive=self._check_sensitive(message),
        )

    def detect_sensitive(self, message: str) -> bool:
        return self._check_sensitive(message)

    def _check_sensitive(self, message: str) -> bool:
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, message):
                return True
        return False

    # ═══ 意图基础分级（设定下限，信号只能升不能降） ═══
    # L1 信息查询类 — AI 全自动即可
    # L2 售后动作类 — 涉及工单/金额，AI 可生成草稿但需人工确认
    # L3 投诉风险类 — 敏感/情绪化，必须直接转人工
    INTENT_BASE_LEVEL = {
        "售后投诉": "L3",
        "退货退款": "L2",
        "换货": "L2",
        "维修": "L2",
        "售前咨询": "L1",
        "订单追踪": "L1",
        "物流查询": "L1",
        "闲聊": "L1",
        "其他": "L1",
    }

    @staticmethod
    def _urgency_level(intent: str, confidence: float) -> str:
        """旧版单维分级（保留兼容，新版用 grade_level）"""
        if intent == "售后投诉" and confidence >= 0.85:
            return "L3"
        if confidence < 0.6:
            return "L3"
        if confidence < 0.85:
            return "L2"
        return "L1"

    # ═══ 问句模式：将 "如何退款" "怎么换货" 等 how-to 查询从动作类降级为信息查询 ═══
    # 关键词："如何/怎么/怎样/什么/流程/步骤/条件" — 表明用户在咨询规则而非发起动作
    # 反例："我要退款" "帮我退货" "申请退款" — 不含问句词，是真正的动作请求 → 保持 L2
    _QUESTION_PATTERN = re.compile(
        r"如何|怎么|怎样|什么|流程|步骤|条件|可以.*吗|能.*吗|能不能|可不可以"
    )

    @staticmethod
    def pre_grade(
        intent: str,
        confidence: float,
        is_sensitive: bool,
        validation_score: float,
        query_text: str = "",
    ) -> dict:
        """预分级（不含质量维度）：意图基础级 → 信号单向升级

        核心规则：
        - 意图决定下限（L1 信息查询 / L2 售后动作 / L3 投诉风险）
        - **问句降级**：L2/L3 意图 + 问句模式 → 降为 L1 信息查询
          （"售后流程""如何投诉""退款条件"→ 用户在咨询规则/流程，不是发起动作或投诉）
        - L1 → 意图置信度低时升 L2；敏感到 L3
        - L2 → 信号极差或敏感可升 L3
        - L3 → 问句模式可降为 L1；非问句（"我要投诉""我要退款"）保持 L3

        设计要点：
        - L1 信息查询类不参考 validation_score，因为知识库未命中/不足是正常的
          （LLM 通用知识即可回答"你好""订单在哪看"等），不应因此升级。
        - L2 售后动作类才参考 validation_score，因为涉及金钱/责任需可靠知识支撑。

        在 AI 生成回复之前调用，决定走哪条处理路径。
        """
        base = IntentEngine.INTENT_BASE_LEVEL.get(intent, "L1")
        escalated = base
        reasons: list[str] = []

        # ── 问句降级：L2/L3 意图 + 问句模式 → 视为 L1 信息查询 ──
        # "售后流程""如何投诉""退款条件" → 用户在咨询规则/流程，不是发起动作或投诉
        # 必须放在 L3 硬地板之前，否则问句降级对 L3 不生效
        is_question = bool(
            query_text and IntentEngine._QUESTION_PATTERN.search(query_text)
        )
        if base in ("L2", "L3") and is_question:
            base = "L1"
            reasons.append(f"问句降级: {intent}→L1({query_text[:20]}...)")

        # ── 知识驱动降级：RAG 检索到高度相关知识时，L2/L3 可降为 L1 ──
        # Agent 自进化的核心：知识库增长 → AI 更自主，不再事事人工确认
        # 但仅对非问句做此检查（问句已在上面降级过）
        if base in ("L2", "L3") and not is_question:
            if validation_score >= 0.65:
                base = "L1"
                reasons.append(
                    f"知识驱动降级: {intent}→L1"
                    f"(知识充足,score={validation_score:.2f})"
                )

        # ── L3 意图：非问句且知识不足时不可降级 ──
        if base == "L3":
            escalated = "L3"
            if not reasons:
                reasons.append(f"意图基础级 L3({intent})，含投诉意图")

        # ── L2 意图：信号极差或敏感 → 升 L3 ──
        elif base == "L2":
            if is_sensitive:
                escalated = "L3"
                reasons.append("命中敏感词(法律/欺诈/安全)")
            elif confidence < 0.5:
                escalated = "L3"
                reasons.append(f"置信度极低({confidence:.2f})")
            elif confidence < 0.7 or validation_score < 0.3:
                # L2 本是"AI草稿+人工确认"，AI 不自信或知识不足时不降级，保持 L2
                escalated = "L2"
                if not reasons:
                    reasons.append(f"意图基础级 L2({intent})")
            else:
                escalated = "L2"
                reasons.append(f"意图基础级 L2({intent})，AI 信号达标")

        # ── L1 意图：区分「原生 L1」和「降级 L1」 ──
        # 降级来源（reasons 含"降级"）意味着用户原本是 L2/L3 动作/投诉意图，
        # 但因问句模式或知识充足而降级为信息查询。此时 is_sensitive 应节制：
        # - 原生 L1 + is_sensitive → L3（真正的敏感内容）
        # - 降级 L1 + is_sensitive → 最多 L2（不抹杀降级效果，用户确实在咨询）
        else:
            was_downgraded = any("降级" in r for r in reasons)
            if is_sensitive and not was_downgraded:
                escalated = "L3"
                reasons.append("命中敏感词(法律/欺诈/安全)")
            elif is_sensitive and was_downgraded:
                escalated = "L2"
                reasons.append("命中敏感词(但降级优先，仅升L2)")
            elif confidence < 0.7:
                # 意图不确定时，如果 RAG 有高度相关知识，仍可 AI 处理
                # LLM 可能误判意图（如"蓝牙坏了"→"闲聊"），但知识足够就能回答
                if validation_score >= 0.65:
                    escalated = "L1"
                    reasons.append(
                        f"意图置信度偏低({confidence:.2f})但知识充足({validation_score:.2f})，保持L1"
                    )
                else:
                    escalated = "L2"
                    reasons.append(f"意图置信度偏低({confidence:.2f})，升级为人工辅助")
            else:
                escalated = "L1"
                reasons.append(f"意图基础级 L1({intent})，AI 信号达标")

        return {
            "level": escalated,
            "level_reason": " | ".join(reasons),
            "level_details": {
                "intent": intent,
                "confidence": confidence,
                "is_sensitive": is_sensitive,
                "validation_score": validation_score,
                "intent_base_level": base,
            },
        }

    @staticmethod
    def grade_level(
        intent: str,
        confidence: float,
        is_sensitive: bool,
        validation_score: float,
        quality_score: float,
    ) -> dict:
        """三维综合定级（事后）：意图×检索质量×回复质量 → L1/L2/L3

        与 pre_grade() 的区别：多了 quality_score 维度（AI 已生成回复后评估）。
        同样遵循意图-floor 规则：意图决定下限，信号只能升不能降。

        - L1 信息查询类：不参考 validation/quality（知识库命中率不影响分级），
          仅看意图置信度 + 敏感词。
        - L2 售后动作类：validation/quality 参与判断，质量过低可升级为 L3。

        Returns:
            {level, level_reason, level_details}
        """
        base = IntentEngine.INTENT_BASE_LEVEL.get(intent, "L1")
        escalated = base
        reasons: list[str] = []

        # ── L3 意图：不可降级 ──
        if base == "L3":
            escalated = "L3"
            reasons.append(f"意图基础级 L3({intent})")

        # ── L2 意图：信号极差/敏感/质量过低 → 升 L3 ──
        elif base == "L2":
            l3_triggers = []
            if is_sensitive:
                l3_triggers.append("命中敏感词")
            if confidence < 0.5:
                l3_triggers.append(f"置信度过低({confidence:.2f})")
            elif quality_score < 0.4 and validation_score < 0.3:
                l3_triggers.append(f"回复质量低({quality_score:.2f})+检索不足({validation_score:.2f})")

            if l3_triggers:
                escalated = "L3"
                reasons.extend(l3_triggers)
            else:
                escalated = "L2"
                reasons.append(f"意图基础级 L2({intent})")

        # ── L1 意图：仅意图置信度低时升级（不参考 validation/quality） ──
        else:
            if is_sensitive:
                escalated = "L3"
                reasons.append("命中敏感词(法律/欺诈/安全)")
            elif confidence < 0.7:
                escalated = "L2"
                reasons.append(f"意图置信度偏低({confidence:.2f})")
            else:
                escalated = "L1"
                reasons.append(f"意图:{intent}，三维均达标")

        return {
            "level": escalated,
            "level_reason": " | ".join(reasons),
            "level_details": {
                "intent_dimension": intent,
                "intent_confidence": confidence,
                "is_sensitive": is_sensitive,
                "retrieval_sufficiency": validation_score,
                "reply_quality": quality_score,
                "intent_base_level": base,
            },
        }
