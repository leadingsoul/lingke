"""多轮对话管理器 — 上下文构建 + 状态管理 + LLM 追问策略"""

from typing import Optional
from dataclasses import dataclass, field
from ai_engine.llm_gateway import LLMGateway


@dataclass
class DialogState:
    session_id: str
    current_state: str = "idle"     # idle / consulting / complaining / transferring / closed
    intent_stack: list[str] = field(default_factory=list)
    question_count: int = 0
    unanswered_count: int = 0
    user_frustration_count: int = 0


class DialogManager:
    """多轮对话上下文构建与状态管理（LLM 驱动追问 + 规则状态跟踪）"""

    MAX_HISTORY_MESSAGES = 20

    FOLLOWUP_PROMPT = """你是电商售后客服助手。根据当前对话，判断是否需要追问用户以获取更多信息。

当前意图：{intent}
对话状态：{state}
最近对话：
{recent_messages}

规则：
- 如果用户已提供了足够信息（如订单号、具体问题描述），返回 "无需追问"
- 如果需要用户补充信息（如订单号、联系方式、问题截图），生成一条自然友好的追问
- 如果用户在表达不满，先安抚再引导
- 只返回追问文本，不要 JSON

你的回复："""

    FRUSTRATION_KEYWORDS = ["听不懂", "不管", "机器人", "转人工", "人工", "人呢", "回答", "怎么回事"]

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.gateway = gateway
        self.sessions: dict[str, DialogState] = {}

    def build_context(self, session_id: str, messages: list[dict]) -> list[dict]:
        """构建多轮对话上下文，取最近 N 条"""
        recent = messages[-self.MAX_HISTORY_MESSAGES:] if len(messages) > self.MAX_HISTORY_MESSAGES else messages
        return [
            {"role": "user" if m.get("sender_type") in ("consumer",) else "assistant",
             "content": m.get("content", "")}
            for m in recent
        ]

    def manage_state(self, session_id: str, intent: str, message: str) -> DialogState:
        """管理对话状态机"""
        if session_id not in self.sessions:
            self.sessions[session_id] = DialogState(session_id=session_id)

        state = self.sessions[session_id]
        state.question_count += 1
        state.intent_stack.append(intent)

        if len(state.intent_stack) > 5:
            state.intent_stack = state.intent_stack[-5:]

        # 不满检测
        if any(kw in message for kw in self.FRUSTRATION_KEYWORDS):
            state.user_frustration_count += 1
        else:
            state.user_frustration_count = max(0, state.user_frustration_count - 0.5)

        # 状态切换
        if intent in ("售后投诉", "退货退款", "换货", "维修"):
            state.current_state = "complaining"
        elif intent == "闲聊":
            state.current_state = "idle"
        else:
            state.current_state = "consulting"

        return state

    def generate_followup(self, session_id: str, current_intent: str = "", recent_messages: list[str] | None = None) -> Optional[str]:
        """LLM 驱动追问：信息不完整时引导用户补充"""
        if session_id not in self.sessions:
            return None

        state = self.sessions[session_id]

        # 如果用户连续问同一意图，可能需要追问
        recent_intents = state.intent_stack[-3:]
        if len(recent_intents) >= 2 and recent_intents[-1] != recent_intents[-2]:
            return None  # 意图在变化，不需要追问
        if state.question_count <= 1:
            return None  # 刚开始，不追问

        # 尝试 LLM 生成追问
        if self.gateway and recent_messages:
            try:
                prompt = self.FOLLOWUP_PROMPT.format(
                    intent=current_intent or recent_intents[-1] if recent_intents else "未知",
                    state=state.current_state,
                    recent_messages="\n".join(recent_messages[-5:]),
                )
                followup = self.gateway.chat_sync(prompt, temperature=0.6, max_tokens=200)
                if followup and "无需追问" not in followup:
                    return followup.strip()
            except Exception:
                pass  # 降级到规则

        # 规则降级
        followups = {
            "退货退款": "为了更好地为您处理退款，请提供您的订单号。",
            "换货": "请问您想换成哪一款商品呢？",
            "维修": "请描述一下具体的故障现象，例如：开不了机、屏幕碎了等。",
            "物流查询": "请提供您的快递单号，我帮您查询物流状态。",
            "售后投诉": "非常抱歉给您带来不便。请详细描述您遇到的问题，我们会尽快处理。",
        }
        intent = recent_intents[-1] if recent_intents else current_intent
        return followups.get(intent)

    def should_escalate(self, session_id: str) -> bool:
        """判断是否需要转人工"""
        if session_id not in self.sessions:
            return False
        state = self.sessions[session_id]
        return state.user_frustration_count >= 3 or state.unanswered_count >= 3

    def close_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].current_state = "closed"

    def mark_unanswered(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].unanswered_count += 1
