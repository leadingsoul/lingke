"""Agent 自进化引擎 — 会话沉淀 → FAQ 提取 → 进化报告（全量 LLM）"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from ai_engine.llm_gateway import LLMGateway


@dataclass
class SessionSummary:
    id: str = ""
    conversation_id: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    review_status: str = "待审核"
    synced_to_knowledge: bool = False


@dataclass
class FAQItem:
    title: str
    type: str = "FAQ"
    tags: list[str] = field(default_factory=list)
    content: str = ""
    status: str = "启用"
    source: str = "进化同步"
    source_id: str = ""



class EvolutionEngine:
    """Agent 自进化引擎 — 全量 LLM 驱动"""

    SUMMARY_PROMPT = """请根据以下客服对话记录，生成一份高质量的会话沉淀文档（Markdown 格式）。

【会话基本信息】
- 会话ID：{conversation_id}
- 时间：{timestamp}
- 处理客服：{staff_name}
- 消息总数：{message_count} 条
- AI 意图分级：{intent_level}
- AI 意图识别：{intent}
- 用户满意度评分：{rating}

【对话记录】
{messages}

请按以下结构输出 Markdown 文档：

# 会话沉淀报告

## 基本信息
- 会话ID：{conversation_id}
- 时间：{timestamp}
- 处理客服：{staff_name}
- 意图分级：{intent_level}
- 满意度：{rating}

## 用户核心诉求
（用 2-3 句话概括用户最关心的问题是什么）

## 对话流程
（按时间线简要描述对话的关键节点，如：用户提问 → AI 应答 → 人工介入 → 问题解决）

## 最终解决方案
（描述问题最终是如何解决的，使用了哪些知识/话术）

## 可优化点
（分析本次对话中有哪些可以改进的地方，如话术不够精准、知识库覆盖不足等）

## 推荐标准话术
（从本次对话中提取 1-3 条可直接复用的回复话术模板）

请直接输出 Markdown 格式的沉淀文档，不要输出 JSON。"""

    EXTRACT_FAQS_PROMPT = """请从以下会话沉淀文档中提取可独立使用的 FAQ 条目。

【沉淀文档】
{summary_content}

请为文档中涉及的知识点提取 FAQ 条目，每条 FAQ 包含：
- title: 简短的问题标题（如"如何查询物流进度"、"退货地址是什么"）
- content: 完整的回答内容（可直接作为客服回复使用）
- type: "FAQ"
- tags: 关键词标签数组

要求：
1. 每条 FAQ 必须是独立可用的知识片段
2. 只提取有实质性内容的知识点，不要提取泛泛而谈的内容
3. 如果文档中没有值得提取的知识点，返回空数组
4. 相同的知识点只提取一次

请输出 JSON 数组：
[
  {{
    "title": "FAQ 标题",
    "content": "完整的回答内容",
    "tags": ["标签1", "标签2"]
  }}
]

只输出 JSON 数组，不要其他文字。"""

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway

    def summarize_conversation(
        self,
        messages: list[dict],
        conversation_id: str = "",
        staff_name: str = "客服",
        intent_level: str = "L1",
        intent: str = "咨询",
        rating: str = "未评分",
        feedback: str = "",
        message_count: int = 0,
    ) -> SessionSummary:
        """LLM 全流程对话复盘 → MD 沉淀文档"""
        try:
            return self._llm_summarize(
                messages, conversation_id, staff_name,
                intent_level, intent, rating, feedback, message_count,
            )
        except Exception:
            return self._fallback_summarize(messages, conversation_id, staff_name, intent_level, intent, rating)

    def _llm_summarize(
        self, messages: list[dict], conversation_id: str, staff_name: str,
        intent_level: str, intent: str, rating: str, feedback: str, message_count: int,
    ) -> SessionSummary:
        msgs_text = "\n".join([
            f"[{m.get('sender_type', 'unknown')}]: {m.get('content', '')}"
            for m in messages[-40:]
        ])
        rating_display = str(rating) if rating else "未评分"
        if feedback:
            rating_display += f"（用户反馈：{feedback}）"

        prompt = self.SUMMARY_PROMPT.format(
            conversation_id=conversation_id,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            staff_name=staff_name,
            message_count=message_count or len(messages),
            intent_level=intent_level or "未知",
            intent=intent or "未知",
            rating=rating_display,
            messages=msgs_text,
        )
        content = self.gateway.chat_sync(prompt, temperature=0.5, max_tokens=2048)
        tags = self._extract_tags(content)
        return SessionSummary(conversation_id=conversation_id, content=content, tags=tags)

    def _fallback_summarize(
        self, messages: list[dict], conversation_id: str, staff_name: str,
        intent_level: str = "", intent: str = "", rating: str = "",
    ) -> SessionSummary:
        """降级沉淀（LLM 不可用时）"""
        user_msgs = [m for m in messages if m.get("sender_type") in ("consumer",)]
        staff_msgs = [m for m in messages if m.get("sender_type") in ("ai", "staff")]
        user_content = "；".join([m.get("content", "")[:100] for m in user_msgs[:5]])
        tags = self._extract_tags(" ".join([m.get("content", "") for m in messages]))

        md_content = f"""# 会话沉淀报告

## 基本信息
- 会话ID：{conversation_id}
- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 处理客服：{staff_name}
- 意图分级：{intent_level or '未知'}
- 满意度：{rating or '未评分'}

## 用户核心诉求
{user_content[:200]}

## 对话流程
用户发起咨询，总共 {len(messages)} 条消息。{'AI自动处理为主' if len(staff_msgs) > len(user_msgs) else '以人工介入为主'}。

## 最终解决方案
基于{'知识库检索' if staff_msgs else '人工判断'}给出回复，{'已解决' if len(staff_msgs) >= len(user_msgs) else '部分解决'}。

## 可优化点
{'用户问题属于常见咨询类型，可通过FAQ快速响应' if staff_msgs else '需加强知识库对应场景覆盖'}

## 推荐标准话术
- 将用户高频问题及回复整理为FAQ条目，纳入知识库管理"""
        return SessionSummary(conversation_id=conversation_id, content=md_content, tags=tags)

    def extract_faqs_from_summary(self, summary: SessionSummary) -> list[FAQItem]:
        """LLM 从沉淀文档提取多条独立 FAQ 条目"""
        try:
            prompt = self.EXTRACT_FAQS_PROMPT.format(summary_content=summary.content[:6000])
            response = self.gateway.chat_sync(prompt, temperature=0.4, max_tokens=2048)
            data = json.loads(response)
            if not isinstance(data, list):
                return []
            faqs = []
            for item in data:
                title = item.get("title", "").strip()
                content = item.get("content", "").strip()
                if not title or not content or len(content) < 20:
                    continue
                faqs.append(FAQItem(
                    title=title[:200],
                    content=content[:2000],
                    tags=item.get("tags", summary.tags),
                    source_id=summary.conversation_id,
                ))
            return faqs
        except Exception:
            # LLM 不可用时用规则兜底提取
            return self._rule_extract_faqs(summary)

    def _rule_extract_faqs(self, summary: SessionSummary) -> list[FAQItem]:
        """规则兜底：从沉淀文档中简单提取 FAQ"""
        import re
        content = summary.content or ""
        faqs = []

        # 尝试匹配"推荐标准话术"段落中的话术
        if "推荐标准话术" in content:
            section = content.split("推荐标准话术")[1]
            lines = section.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    text = line[2:].strip()
                    if len(text) > 10:
                        faqs.append(FAQItem(
                            title=text[:80],
                            content=text[:500],
                            tags=summary.tags,
                            source_id=summary.conversation_id,
                        ))

        # 兜底：从"用户核心诉求"提取
        if not faqs and "用户核心诉求" in content:
            section = content.split("用户核心诉求")[1].split("##")[0] if "##" in content.split("用户核心诉求")[1] else content.split("用户核心诉求")[1]
            line = section.strip().split("\n")[0].strip().lstrip("- ").lstrip("* ")
            if len(line) > 5:
                faqs.append(FAQItem(
                    title=line[:100],
                    content=f"关于您的问题「{line[:80]}」，建议参考对应FAQ条目或联系客服进一步了解。",
                    tags=summary.tags,
                    source_id=summary.conversation_id,
                ))

        return faqs

    DEDUP_MERGE_PROMPT = """你是知识库去重助手。已有知识库中有若干条目，新提取的 FAQ 来自会话沉淀。

请逐一判断每条新 FAQ 是否与已有知识条目**语义重合**（≥80% 含义相同，标题措辞不同也算重合）。

【已有知识条目】（ID + 标题 + 摘要）
{existing_summary}

【新 FAQ 条目】（编号 + 标题 + 内容）
{new_faqs}

判断标准：
- "duplicate"：内容高度重叠，可以合并（标题略有不同但核心意思相同也算）
- "new"：内容不同，属于全新知识点
- 不要为了去重而把语义不同的条目强行匹配

输出 JSON 数组（每条新 FAQ 一个判断）：
[
  {{"index": 0, "judgement": "duplicate", "match_id": "已有条目的ID", "merge_note": "新内容中可补充的要点（2句话以内）"}},
  {{"index": 1, "judgement": "new", "match_id": null, "merge_note": ""}},
  ...
]

只输出 JSON 数组，不要其他文字。"""

    def dedup_faqs(
        self,
        new_faqs: list[FAQItem],
        existing_items: list[dict],
    ) -> list[dict]:
        """LLM 语义去重：判断新 FAQ 是否与已有知识条目重合，返回去重决策列表

        existing_items: [{"id":..., "title":..., "content":...}, ...]
        返回：[{"index":0, "judgement":"duplicate"|"new", "match_id":"...", "merge_note":"..."}, ...]
        """
        if not new_faqs:
            return []
        if not existing_items:
            return [{"index": i, "judgement": "new", "match_id": None, "merge_note": ""} for i in range(len(new_faqs))]

        try:
            existing_summary = "\n".join(
                f"ID={item['id']} | {item['title']} | {item.get('content','')[:120]}"
                for item in existing_items
            )
            new_faqs_text = "\n".join(
                f"[{i}] {faq.title}\n  {faq.content[:200]}"
                for i, faq in enumerate(new_faqs)
            )
            prompt = self.DEDUP_MERGE_PROMPT.format(
                existing_summary=existing_summary[:4000],
                new_faqs=new_faqs_text[:4000],
            )
            response = self.gateway.chat_sync(prompt, temperature=0.2, max_tokens=1024)
            data = json.loads(response)
            if isinstance(data, list):
                return data
            return [{"index": i, "judgement": "new", "match_id": None, "merge_note": ""} for i in range(len(new_faqs))]
        except Exception:
            # LLM 不可用时用关键词重叠兜底
            return self._rule_dedup_faqs(new_faqs, existing_items)

    @staticmethod
    def _rule_dedup_faqs(new_faqs: list[FAQItem], existing_items: list[dict]) -> list[dict]:
        """规则兜底去重：基于标题关键词 Jaccard 相似度"""
        import re

        def _tokenize(s: str) -> set[str]:
            return set(re.findall(r"[一-鿿\w]{2,}", s.lower()))

        decisions = []
        for i, faq in enumerate(new_faqs):
            faq_tokens = _tokenize(faq.title)
            if not faq_tokens:
                decisions.append({"index": i, "judgement": "new", "match_id": None, "merge_note": ""})
                continue

            best_match = None
            best_score = 0.0
            for item in existing_items:
                item_tokens = _tokenize(item["title"])
                if not item_tokens:
                    continue
                intersection = len(faq_tokens & item_tokens)
                union = len(faq_tokens | item_tokens)
                score = intersection / union if union > 0 else 0
                if score > best_score:
                    best_score = score
                    best_match = item

            if best_score >= 0.7 and best_match:
                decisions.append({
                    "index": i,
                    "judgement": "duplicate",
                    "match_id": best_match["id"],
                    "merge_note": f"关键词相似度 {best_score:.0%}，建议合并",
                })
            else:
                decisions.append({"index": i, "judgement": "new", "match_id": None, "merge_note": ""})
        return decisions

    def _extract_tags(self, text: str) -> list[str]:
        """从文本中提取主题标签"""
        themes = ["商品质量", "物流服务", "包装", "客服态度", "价格", "售后服务"]
        tags = [t for t in themes if t in text]
        return tags if tags else ["未分类"]
