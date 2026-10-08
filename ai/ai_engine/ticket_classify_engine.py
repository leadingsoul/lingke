"""工单智能分类引擎 — LLM 驱动售后工单类型/紧急度/责任归属判定"""

import json
from typing import Optional
from dataclasses import dataclass
from ai_engine.llm_gateway import LLMGateway


@dataclass
class TicketClassifyResult:
    ticket_type: str            # 仅退款 / 退货退款 / 换货 / 维修
    urgency: str                # 普通 / 紧急
    responsibility: str         # 商家 / 物流 / 用户 / 待定
    suggested_action: str = ""  # AI 建议处理方案
    confidence: float = 1.0
    has_contradiction: bool = False       # 是否检测到描述与商品矛盾
    contradiction_detail: str = ""         # 矛盾详情


class TicketClassifyEngine:
    """工单分类引擎 — LLM 为主，异常时降级规则"""

    CLASSIFY_PROMPT = """分析以下售后工单，输出 JSON：
{{
  "ticket_type": "仅退款|退货退款|换货|维修",
  "urgency": "普通|紧急",
  "responsibility": "商家|物流|用户|待定",
  "suggested_action": "建议的处理方案",
  "has_contradiction": true/false,
  "contradiction_detail": "矛盾说明（无矛盾则为空）"
}}

工单信息：
- 售后类型：{aso_type}
- 售后原因：{aso_reason}
- 问题描述：{description}
- 订单信息：{order_info}

【紧急度判定规则 — 必须严格遵守】

"紧急"（满足任意一条即判）：
  - 涉及人身安全 / 健康 / 食品安全（如"吃了拉肚子""过敏""触电""烧伤"）
  - 涉及假货 / 欺诈 / 诈骗（如"收到假货""被骗了""虚假宣传"）
  - 涉及隐私泄露 / 数据安全（如"信息被泄露""账号被盗"）
  - 金额重大且有明确损失（如"损失几千块"）
  - 用户明确表示涉及法律 / 12315 / 媒体曝光
  - 用户情绪激动，使用了"急""马上""立刻""赶紧""快"等催促词
  - 用户明确表示要投诉 / 差评 / 曝光 / 维权
  - 问题已严重影响使用（如"根本用不了""完全坏了""打不开"）
  - 涉及时间敏感场景（如"明天就要用""赶着"）
  - 多次联系未解决 / 反复出现问题

"普通"：不满足以上任何条件的常规售后请求（咨询、一般退货退款、换货、维修等）

【矛盾检测规则】
1. 如果问题描述与订单商品类型明显不匹配（如用户描述"耳机声音有问题"但订单商品是"食品礼盒"），标记 has_contradiction=true
2. 如果发现矛盾，suggested_action 必须以「⚠️ 矛盾警告：」开头，说明描述与商品不匹配，建议客服核实
3. 若无矛盾，正常给出建议处理方案"""

    URGENCY_KEYWORDS = {
        "紧急": ["假货", "欺诈", "诈骗", "有毒", "过敏", "触电", "烧伤", "泄露", "安全", "健康",
                 "食品", "吃坏", "拉肚子", "虚假宣传", "被骗", "12315", "法律", "起诉",
                 "急", "马上", "立刻", "赶紧", "快", "投诉", "差评", "曝光", "维权",
                 "根本用不了", "打不开", "完全坏了", "反复", "多次", "再这样", "明天就要",
                 "严重", "损失"],
    }

    RESPONSIBILITY_KEYWORDS = {
        "商家": ["发错", "质量问题", "描述不符", "瑕疵", "破损", "少了", "缺"],
        "物流": ["物流", "快递", "运输", "损坏", "压坏", "摔坏", "延迟", "没送到"],
        "用户": ["买错了", "不想要", "七天无理由", "拍错", "重复下单"],
    }

    SUGGESTIONS = {
        "仅退款": "请核实订单和退款原因，确认后办理退款。",
        "退货退款": "请告知用户退货地址和注意事项，确认收到退货后办理退款。",
        "换货": "请核实库存情况，为用户办理换货手续。",
        "维修": "请告知用户维修流程和预估时间，安排售后维修。",
    }

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def classify_ticket(
        self,
        description: str,
        aso_type: str,
        aso_reason: str = "",
        order_info: Optional[dict] = None,
    ) -> TicketClassifyResult:
        """工单分类：LLM 优先，异常时降级规则"""
        try:
            return self._llm_classify(description, aso_type, aso_reason, order_info)
        except Exception:
            return self._fallback_classify(description, aso_type, aso_reason)

    def _llm_classify(
        self,
        description: str,
        aso_type: str,
        aso_reason: str,
        order_info: Optional[dict] = None,
    ) -> TicketClassifyResult:
        prompt = self.CLASSIFY_PROMPT.format(
            aso_type=aso_type,
            aso_reason=aso_reason,
            description=description,
            order_info=json.dumps(order_info or {}, ensure_ascii=False),
        )
        response = self.gateway.chat_sync(prompt, temperature=0.3)
        data = json.loads(response)
        return TicketClassifyResult(
            ticket_type=data.get("ticket_type", aso_type),
            urgency=data.get("urgency", "普通"),
            responsibility=data.get("responsibility", "待定"),
            suggested_action=data.get("suggested_action", ""),
            confidence=0.85,
            has_contradiction=data.get("has_contradiction", False),
            contradiction_detail=data.get("contradiction_detail", ""),
        )

    def _fallback_classify(self, description: str, aso_type: str, aso_reason: str) -> TicketClassifyResult:
        """规则降级分类"""
        urgency = "紧急" if any(kw in description for kw in self.URGENCY_KEYWORDS.get("紧急", [])) else "普通"

        responsibility = "待定"
        for party, keywords in self.RESPONSIBILITY_KEYWORDS.items():
            if any(kw in description or kw in aso_reason for kw in keywords):
                responsibility = party
                break

        return TicketClassifyResult(
            ticket_type=aso_type or "退货退款",
            urgency=urgency,
            responsibility=responsibility,
            suggested_action=self.SUGGESTIONS.get(aso_type, "请按标准流程处理。"),
            confidence=0.8,
        )
