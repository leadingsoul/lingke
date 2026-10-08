"""主题归类引擎 — LLM 驱动评价文本多标签主题分类"""

import json
from typing import Optional
from dataclasses import dataclass, field
from ai_engine.llm_gateway import LLMGateway


@dataclass
class ThemeItem:
    theme: str
    confidence: float


@dataclass
class ThemeResult:
    themes: list[ThemeItem] = field(default_factory=list)
    primary_theme: str = ""


class ThemeEngine:
    """主题归类引擎 — LLM 为主，异常时降级关键词"""

    THEMES = ["商品质量", "物流服务", "包装", "客服态度", "价格", "售后服务"]

    THEME_PROMPT = """分析以下用户评价涉及哪些主题，输出 JSON：
{{
  "themes": [
    {{"theme": "商品质量|物流服务|包装|客服态度|价格|售后服务", "confidence": 0.0-1.0}},
    ...
  ],
  "primary_theme": "主主题"
}}

六个主题说明：
- 商品质量：涉及质量、材质、做工、手感、功能、效果、颜色、尺寸、色差、瑕疵、破损
- 物流服务：涉及物流、快递、发货、送货、速度
- 包装：涉及包装、盒子、包裹
- 客服态度：涉及客服、服务、态度、回复
- 价格：涉及价格、贵、便宜、性价比、优惠
- 售后服务：涉及售后、退货、退款、换货、维修、保修

评价内容：{text}"""

    THEME_KEYWORDS = {
        "商品质量": ["质量", "材质", "做工", "面料", "手感", "功能", "效果", "颜色", "尺寸", "大小", "色差", "瑕疵", "破损", "坏了"],
        "物流服务": ["物流", "快递", "发货", "送货", "速度", "很快", "顺丰", "圆通", "中通", "收到"],
        "包装": ["包装", "盒子", "袋子", "包裹", "泡沫", "纸箱", "严实", "简陋", "破损"],
        "客服态度": ["客服", "服务", "态度", "回复", "热情", "耐心", "冷淡", "不理", "敷衍"],
        "价格": ["价格", "贵", "便宜", "划算", "性价比", "值", "不值", "降价", "优惠", "折扣"],
        "售后服务": ["售后", "退货", "退款", "换货", "维修", "保修", "处理", "退换"],
    }

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def classify(self, text: str) -> ThemeResult:
        """主题归类：LLM 优先，异常时降级关键词"""
        try:
            return self._llm_classify(text)
        except Exception:
            return self._keyword_classify(text)

    def _llm_classify(self, text: str) -> ThemeResult:
        prompt = self.THEME_PROMPT.format(text=text)
        response = self.gateway.chat_sync(prompt, temperature=0.3)
        data = json.loads(response)
        themes = [
            ThemeItem(theme=t["theme"], confidence=t["confidence"])
            for t in data.get("themes", [])
        ]
        primary = data.get("primary_theme", themes[0].theme if themes else "商品质量")
        return ThemeResult(themes=themes, primary_theme=primary)

    def _keyword_classify(self, text: str) -> ThemeResult:
        """关键词降级分类"""
        themes = []
        max_confidence = 0.0
        primary = ""

        for theme, keywords in self.THEME_KEYWORDS.items():
            matched = sum(1 for kw in keywords if kw in text)
            if matched > 0:
                confidence = min(1.0, matched * 0.3 + 0.2)
                themes.append(ThemeItem(theme=theme, confidence=round(confidence, 2)))
                if confidence > max_confidence:
                    max_confidence = confidence
                    primary = theme

        if not themes:
            themes.append(ThemeItem(theme="商品质量", confidence=0.5))
            primary = "商品质量"

        return ThemeResult(themes=themes, primary_theme=primary)

    def batch_classify(self, texts: list[str]) -> list[ThemeResult]:
        return [self.classify(text) for text in texts]
