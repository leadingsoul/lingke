# group22-backend — 电商售后客服与用户评价分析系统（后端）

## 项目简介

本仓库为"电商售后客服与用户评价分析系统"的 **FastAPI 后端服务**，提供 REST API、WebSocket 实时推送、数据库 ORM 模型及业务逻辑层。

## 技术栈

| 技术 | 版本 | 用途 |
|:---|:---|:---|
| Python | 3.11+ | 运行环境 |
| FastAPI | 0.104+ | Web 框架 |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.12+ | 数据库迁移 |
| Pydantic | 2.5+ | 数据验证 |
| PyJWT | 2.8+ | JWT 鉴权 |
| bcrypt | 4.0+ | 密码哈希 |
| Redis | 7.0 | Token 黑名单 / WebSocket Pub/Sub |
| MySQL | 8.0 | 主数据库 |

## 环境要求

- Python 3.11+
- Docker & Docker Compose（启动 MySQL + Redis）
- 本仓库需配合 `group22-ai` 仓库使用（AI 引擎 Python 包）

## 安装和启动

```bash
# 1. 克隆仓库
git clone https://github.com/Daymoonlight-P/group22-backend.git
cd group22-backend

# 2. 创建虚拟环境
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # macOS/Linux

# 3. 安装依赖（含 group22-ai 包）
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库密码、JWT 密钥等

# 5. 启动 MySQL + Redis
docker compose up -d

# 6. 执行数据库迁移
alembic upgrade head

# 7. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 目录结构

```
group22-backend/
├── README.md
├── .gitignore
├── .env.example               # 环境变量模板
├── docker-compose.yml         # MySQL 8.0 + Redis 7.0
├── requirements.txt           # Python 依赖
├── alembic.ini                # Alembic 配置
├── alembic/                   # 数据库迁移
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 应用入口
│   ├── core/                  # 核心模块
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # 数据库连接
│   │   ├── security.py        # 鉴权工具
│   │   └── deps.py            # 依赖注入
│   ├── models/                # SQLAlchemy 模型（20 表）
│   ├── schemas/               # Pydantic 请求/响应 Schema（5 个 Schema 模块）
│   ├── api/
│   │   └── v1/                # API 路由
│   │       ├── router_auth.py      # 认证模块（5 接口）
│   │       ├── router_consumer.py  # 消费者模块（19 接口）
│   │       ├── router_cs.py        # 客服模块（16 接口）
│   │       └── router_admin.py     # 管理模块（43 接口）
│   ├── services/              # 业务逻辑层（13 个 Service）
│   └── websocket/             # WebSocket 连接管理
└── tests/                     # 测试
```

## 小组成员及分工

| 姓名 | 角色 | 负责模块 |
|:---|:---|:---|
| A | 全栈 | 后端 API + Docker + 消费者前端 |
| B | 全栈 | AI 引擎集成 + 客服前端 |
| C | 全栈 | 管理端前端 + WebSocket + 测试 |

## 当前开发状态

| 模块 | 状态 | 文件数 | 说明 |
|:---|:---|:---|:---|
| 数据库模型（20 表） | ✅ 已完成 | 7 | `app/models/` |
| Pydantic Schema | ✅ 已完成 | 5 | `app/schemas/` |
| 核心基础设施 | ✅ 已完成 | 4 | `app/core/` (config / database / security / deps) |
| 业务逻辑 Service | ✅ 已完成 | 13 | `app/services/` |
| API 路由（83 接口） | ✅ 已完成 | 4 | `app/api/v1/` |
| WebSocket 实时推送 | ✅ 已完成 | 1 | `app/api/v1/router_ws.py` |
| 数据库迁移 | ✅ 已完成 | 1 | `alembic/versions/001_initial_tables.py` |
| Docker Compose | ✅ 已完成 | 1 | MySQL 8.0 + Redis 7.0 |
| AI 引擎对接 | ⏳ 待对接 | — | 待 `group22-ai` 就绪后连调 |

## API 接口数量

| 模块 | 接口数 |
|:---|:---|
| 认证 Auth | 5 |
| 消费者 Consumer | 19 |
| 客服 CS | 16 |
| 管理 Admin | 43 |
| WebSocket | 5 事件 + 心跳 |
| **合计** | **83 REST + 5 WS 业务事件** |

完整接口文档见项目根目录 `接口文档\电商售后客服与用户评价分析系统-前后端对接API接口文档.md`
