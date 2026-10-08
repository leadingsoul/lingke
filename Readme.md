# 聆客（LingKe）— 开发工具清单

> 电商售后客服与用户评价分析系统

---

## 一、基础环境

| 工具             | 版本要求           | 用途                      | 下载                                              |
|:-------------- |:-------------- |:----------------------- |:----------------------------------------------- |
| Python         | 3.11+          | 后端 + AI 引擎运行环境          | https://www.python.org/downloads/               |
| Node.js        | 18+（推荐 20 LTS） | 三端前端构建与运行               | https://nodejs.org/                             |
| MySQL          | 8.0+           | 关系数据库                   | https://dev.mysql.com/downloads/                |
| Redis          | 7.0+           | 缓存 / 会话管理               | https://redis.io/download/ （或 Docker）           |
| Docker Desktop | 最新稳定版          | 容器化运行 Redis / MySQL（可选） | https://www.docker.com/products/docker-desktop/ |

---

## 二、开发工具

| 工具             | 用途             | 下载                             |
|:-------------- |:-------------- |:------------------------------ |
| VS Code        | 主力 IDE（推荐）     | https://code.visualstudio.com/ |
| DBeaver        | 数据库可视化管理       | https://dbeaver.io/            |
| Postman        | API 接口调试       | https://www.postman.com/       |
| Git            | 版本控制           | https://git-scm.com/           |
| GitHub Desktop | Git 图形化客户端（可选） | https://desktop.github.com/    |

---

## 三、Python 后端依赖

> 完整清单见同目录 `requirements.txt`

| 类别        | 核心包                                                                       | 版本             |
|:--------- |:------------------------------------------------------------------------- |:-------------- |
| Web 框架    | fastapi                                                                   | 0.104.1        |
| ASGI 服务器  | uvicorn                                                                   | 0.24.0         |
| ORM       | sqlalchemy                                                                | 2.0.23         |
| 数据库迁移     | alembic                                                                   | 1.12.1         |
| 数据校验      | pydantic                                                                  | 2.5.2          |
| 鉴权        | pyjwt / bcrypt                                                            | 2.8.0 / 4.1.1  |
| 加密        | cryptography                                                              | 41.0.7         |
| Redis 客户端 | redis                                                                     | 5.0.1          |
| WebSocket | websockets                                                                | 12.0           |
| HTTP 客户端  | httpx                                                                     | 0.25.2         |
| 文件解析      | python-docx / pdfplumber / python-pptx / openpyxl / beautifulsoup4 / lxml | —              |
| 测试        | pytest / pytest-asyncio                                                   | 7.4.3 / 0.23.2 |
| LLM 框架    | langchain                                                                 | ≥0.1.0         |

---

## 四、Node.js 前端依赖

### 消费者端（Vue 3 + Vant 4）

| 类别          | 核心包        | 版本    |
|:----------- |:---------- |:----- |
| 框架          | vue        | ^3.5  |
| 路由          | vue-router | ^4.6  |
| 状态管理        | pinia      | ^3.0  |
| UI 组件库      | vant       | ^4.9  |
| HTTP 客户端    | axios      | ^1.18 |
| Markdown 渲染 | marked     | ^18.0 |
| 构建工具        | vite       | ^8.0  |
| 类型检查        | typescript | ~6.0  |

### 客服端 & 管理端（React 18 + Ant Design 5）

| 类别       | 核心包                         | 版本          |
|:-------- |:--------------------------- |:----------- |
| 框架       | react / react-dom           | ^18.2       |
| UI 组件库   | antd                        | ^5.12       |
| 图标       | @ant-design/icons           | ^5.2        |
| 状态管理     | zustand                     | ^4.4        |
| HTTP 客户端 | axios                       | ^1.6        |
| 日期处理     | dayjs                       | ^1.11       |
| 图表（仅管理端） | echarts / echarts-for-react | ^5.4 / ^3.0 |
| Markdown | react-markdown + remark-gfm | —           |
| 构建工具     | vite                        | ^5.0        |
| 类型检查     | typescript                  | ^5.3        |

---

## 五、AI 服务（LLM API）

| 模型                     | 提供商                | 用途                             |
|:---------------------- |:------------------ |:------------------------------ |
| DeepSeek-V3            | DeepSeek API       | 主力 LLM：意图识别、对话生成、RAG、情感分析、会话沉淀 |
| BAAI/bge-small-zh-v1.5 | HuggingFace / 本地缓存 | Embedding 向量检索（512 维语义相似度）     |

> API Key 配置在 `.env` 文件中（`DEEPSEEK_API_KEY`），不提交到代码仓库。

---

## 六、快速安装命令

### 后端 + AI 引擎

```bash
cd group22-backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# AI 引擎安装为可编辑包（如单独使用）
cd ../group22-ai
pip install -e .
```

### 前端

```bash
cd group22-frontend/user-end   # 消费者端
npm install
npm run dev                    # → http://localhost:5173

cd ../cs-end                   # 客服端
npm install
npm run dev                    # → http://localhost:5174

cd ../admin-end                # 管理端
npm install
npm run dev                    # → http://localhost:5175
```
