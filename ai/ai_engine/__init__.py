"""
AI 引擎层 — 电商售后客服与用户评价分析系统

8 大核心引擎模块：
- LLMGateway: 统一 LLM 调用入口（DeepSeek）
- IntentEngine: 意图识别
- DialogManager: 多轮对话管理
- RAGEngine: 检索增强生成
- SentimentEngine: 情感分析
- ThemeEngine: 主题归类
- TicketClassifyEngine: 工单自动分类
- EvolutionEngine: Agent 自进化

所有引擎统一通过 LLMGateway 调用 DeepSeek LLM API。
"""
