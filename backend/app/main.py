"""FastAPI 应用入口 — 加载路由、中间件、异常处理"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# 必须最先：把 .env 注入 os.environ（LLMGateway.from_env 依赖此）
from dotenv import load_dotenv
load_dotenv()

from app.core.config import get_settings

settings = get_settings()

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建后台任务，关闭时取消"""
    # ── 后台任务：定时自动关闭超时会话 ──
    async def _auto_close_loop():
        """每 10 分钟扫描一次，关闭超过 24 小时未更新的非关闭会话"""
        await asyncio.sleep(30)  # 启动后先等 30s，确保所有模块加载完毕
        while True:
            try:
                from app.core.database import AsyncSessionLocal
                from app.services.evolution_service import EvolutionService
                async with AsyncSessionLocal() as db:
                    closed = await EvolutionService.auto_close_stale_conversations(
                        db, max_hours=24,
                    )
                    if closed > 0:
                        _logger.info(f"[Lifespan] Auto-closed {closed} stale conversations")
            except Exception as exc:
                _logger.error(f"[Lifespan] Auto-close task error: {exc}")

            await asyncio.sleep(600)  # 10 分钟间隔

    task = asyncio.create_task(_auto_close_loop())
    _logger.info("[Lifespan] Auto-close background task started (interval=10min, threshold=24h)")

    yield  # ── 应用运行中 ──

    # 关闭时取消后台任务
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    _logger.info("[Lifespan] Auto-close background task stopped")


app = FastAPI(
    title="电商售后客服与用户评价分析系统",
    description="E-Commerce After-Sales Service & User Review Analysis System",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"code": 500, "message": f"服务器内部错误: {str(exc)}", "data": None})


@app.get("/")
async def root():
    return {"message": "E-Commerce After-Sales API v1.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# 挂载路由
from app.api.v1.router_auth import router as auth_router
from app.api.v1.router_consumer import router as consumer_router
from app.api.v1.router_cs import router as cs_router
from app.api.v1.router_admin import router as admin_router
from app.api.v1.router_ws import router as ws_router

app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(consumer_router, prefix="/api/consumer", tags=["消费者"])
app.include_router(cs_router, prefix="/api/cs", tags=["客服"])
app.include_router(admin_router, prefix="/api/admin", tags=["管理员"])
app.include_router(ws_router, prefix="/api/ws", tags=["WebSocket"])

# 挂载静态文件服务 — 供聊天文件上传等使用
upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
