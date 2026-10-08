# ai — 电商售后客服与用户评价分析系统（AI 引擎）

## 项目简介

本仓库为"电商售后客服与用户评价分析系统"的 **AI 引擎层**，包含 8 大 AI 能力模块。以 Python 包形式发布，被 `backend` 通过 pip git 方式安装引用。

## 技术栈

| 技术 | 用途 |
|:---|:---|
| Python 3.11+ | 运行环境 |
| LangChain | LLM 调用编排 |
| DeepSeek API | 主力 LLM 模型 |
| 通义千问 API | 备用 LLM 模型 |
| httpx | 异步 HTTP 客户端 |

## 8 大 AI 引擎

| 引擎 | 模块 | 功能 |
|:---|:---|:---|
| LLM Gateway | `llm_gateway.py` | 统一 LLM 调用入口（多模型切换、重试、降级、限流） |
| IntentEngine | `intent_engine.py` | 意图识别（咨询/售后/投诉/闲聊 → L1/L2/L3 等级） |
| DialogManager | `dialog_manager.py` | 多轮对话管理（上下文窗口 + 会话记忆 + 追问策略） |
| RAGEngine | `rag_engine.py` | 检索增强生成（知识库检索 + 重排序 + 答案合成） |
| SentimentEngine | `sentiment_engine.py` | 情感分析（正面/中性/负面 × 紧急/非紧急） |
| ThemeEngine | `theme_engine.py` | 主题归类（关键词提取 + 聚类 + 热点识别） |
| TicketClassifyEngine | `ticket_classify_engine.py` | 工单自动分类（类型/优先级/建议分配客服） |
| EvolutionEngine | `evolution_engine.py` | Agent 自进化（会话沉淀 → 对策草稿 → 审核 → RAG 同步） |

## 安装

```bash
# 作为独立包安装（开发调试）
cd ai_engine
pip install -e .
```

## 使用示例

```python
from ai_engine.llm_gateway import LLMGateway
from ai_engine.intent_engine import IntentEngine

# 初始化
gateway = LLMGateway()
intent_engine = IntentEngine(gateway)

# 意图识别
result = await intent_engine.classify("我的订单什么时候发货？")
# result.intent = "consult", result.level = "L1", result.confidence = 0.95
```

## 目录结构

```
ai/
├── README.md
├── .gitignore
├── setup.py                    # Python 包配置
├── requirements.txt            # 依赖
├── ai_engine/
│   ├── __init__.py
│   ├── llm_gateway.py          # LLM 统一入口
│   ├── intent_engine.py        # 意图识别
│   ├── dialog_manager.py       # 多轮对话
│   ├── rag_engine.py           # 检索增强生成
│   ├── sentiment_engine.py     # 情感分析
│   ├── theme_engine.py         # 主题归类
│   ├── ticket_classify_engine.py  # 工单分类
│   └── evolution_engine.py     # 自进化
└── tests/
```

## 当前开发状态

| 引擎 | 状态 | 说明 |
|:---|:---|:---|
| LLM Gateway | ✅ 已完成 | 多模型切换 + 重试 + 降级 + Mock 模式 |
| IntentEngine | ✅ 已完成 | 关键词匹配 Mock + LLM prompt 双模式 |
| DialogManager | ✅ 已完成 | 状态机 + 追问生成 + 转人工判定 |
| RAGEngine | ✅ 已完成 | 知识检索 + Prompt 组装 + LLM/Mock 双模式 |
| SentimentEngine | ✅ 已完成 | 情感分类 + 风险识别 + 批量分析 |
| ThemeEngine | ✅ 已完成 | 六大主题多标签分类 |
| TicketClassifyEngine | ✅ 已完成 | 工单类型/紧急度/责任归属自动判定 |
| EvolutionEngine | ✅ 已完成 | 会话沉淀 + 对策草稿 + 进化报告 + FAQ 提取 |

> 所有引擎均支持 **Mock 模式**（默认开启），无需 LLM API Key 即可运行。

## 小组成员及分工

| 姓名 | 角色 | 负责模块 |
|:---|:---|:---|
| A | 全栈 | IntentEngine + RAGEngine + DialogManager |
| B | 全栈 | LLMGateway + TicketClassifyEngine + ThemeEngine |
| C | 全栈 | SentimentEngine + EvolutionEngine + WebSocket |
