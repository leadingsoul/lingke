"""情感分析引擎 — LLM 驱动评价文本情感分类 + 风险识别"""

import time
import json
from typing import Optional
from dataclasses import dataclass, field
from ai_engine.llm_gateway import LLMGateway


@dataclass
class SentimentResult:
    sentiment: str              # positive / neutral / negative
    intensity: float            # 情感强度 0-1
    keywords: list[str] = field(default_factory=list)
    risk_level: str = "low"     # low / medium / high
    processing_time_ms: int = 0


class SentimentEngine:
    """情感分析引擎 — LLM 为主，异常时降级为关键词分析"""

    SENTIMENT_PROMPT = """分析以下用户评价的情感倾向，输出 JSON：
{{
  "sentiment": "positive|neutral|negative",
  "intensity": 0.0-1.0,
  "keywords": ["关键词1", "关键词2"],
  "risk_level": "low|medium|high"
}}

规则：
- positive: 满意、好评、喜欢
- neutral: 中性评价
- negative: 不满意、差评、投诉
- intensity: 情感强烈程度
- risk_level: low(无风险)/medium(需关注)/high(高风险，含投诉/举报意图)

评价内容：{text}"""

    POSITIVE_KEYWORDS = [
        "好", "满意", "不错", "喜欢", "赞", "棒", "快", "推荐", "好评",
        "质量好", "性价比高", "好用", "漂亮", "完美", "值得", "开心",
        "很快", "非常好", "特别好", "给力", "良心", "优秀",
    ]
    NEGATIVE_KEYWORDS = [
        "差", "烂", "慢", "垃圾", "坑", "骗", "失望", "不行", "太差",
        "质量差", "坏了", "破损", "假货", "不好用", "难用",
        "投诉", "退款", "退货", "太慢了", "不值", "后悔",
    ]
    INTENSIFIERS = ["非常", "太", "特别", "极其", "超级", "真的", "实在", "完全"]

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def analyze(self, text: str) -> SentimentResult:
        """情感分析：LLM 优先，异常时降级关键词"""
        start = time.time()
        try:
            result = self._llm_analyze(text)
        except Exception:
            result = self._keyword_analyze(text)
        result.processing_time_ms = int((time.time() - start) * 1000)
        return result

    def _llm_analyze(self, text: str) -> SentimentResult:
        prompt = self.SENTIMENT_PROMPT.format(text=text)
        response = self.gateway.chat_sync(prompt, temperature=0.3)
        data = json.loads(response)
        return SentimentResult(
            sentiment=data.get("sentiment", "neutral"),
            intensity=float(data.get("intensity", 0.5)),
            keywords=data.get("keywords", []),
            risk_level=data.get("risk_level", "low"),
        )

    def _keyword_analyze(self, text: str) -> SentimentResult:
        """关键词降级分析"""
        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

        all_keywords = [kw for kw in self.POSITIVE_KEYWORDS + self.NEGATIVE_KEYWORDS if kw in text]

        intensity = min(1.0, (pos_count + neg_count) * 0.25)
        for intensifier in self.INTENSIFIERS:
            if intensifier in text:
                intensity += 0.15
        intensity = min(1.0, intensity)

        if neg_count > pos_count:
            sentiment = "negative"
            intensity = max(intensity, 0.5)
        elif pos_count > neg_count:
            sentiment = "positive"
        else:
            sentiment = "neutral"
            intensity = max(intensity, 0.1)

        return SentimentResult(
            sentiment=sentiment,
            intensity=round(intensity, 2),
            keywords=all_keywords[:10],
            risk_level=self._calc_risk_level(sentiment, intensity),
        )

    def _calc_risk_level(self, sentiment: str, intensity: float) -> str:
        if sentiment == "negative" and intensity >= 0.7:
            return "high"
        if sentiment == "negative" and intensity >= 0.4:
            return "medium"
        return "low"

    def batch_analyze(self, texts: list[str]) -> list[SentimentResult]:
        return [self.analyze(text) for text in texts]

    def detect_high_risk(self, text: str, sentiment_result: SentimentResult) -> bool:
        if sentiment_result.risk_level == "high":
            return True
        sensitive = ["投诉", "举报", "报警", "工商", "12315", "315", "维权", "律师", "诉讼"]
        return any(s in text for s in sensitive)
