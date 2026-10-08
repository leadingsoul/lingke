"""认证路由 — 登录 / 登出 / Token 刷新 / 当前用户"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, security
from app.core.database import get_db
from app.schemas.auth_schemas import (
    LoginRequest,
    WechatLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    LogoutResponse,
    UserInfo,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=dict, summary="账号密码登录")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    service: AuthService = Depends(),
):
    """用户名/手机号 + 密码登录，返回 access/refresh token 与用户信息"""
    result = await service.login(
        username=request.username,
        password=request.password,
        user_type=request.user_type,
        captcha=request.captcha,
        db=db,
    )
    return {"code": 200, "message": "登录成功", "data": result}


@router.post("/wechat-login", response_model=dict, summary="微信授权登录")
async def wechat_login(
    request: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
    service: AuthService = Depends(),
):
    """微信临时 code 换取 token"""
    result = await service.wechat_login(code=request.code, db=db)
    return {"code": 200, "message": "登录成功", "data": result}


@router.post("/logout", response_model=dict, summary="登出")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    service: AuthService = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """将当前 access token 加入黑名单，客服/管理员设为离线"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    await service.logout(token=credentials.credentials, db=db)
    return {"code": 200, "message": "登出成功", "data": None}


@router.post("/refresh", response_model=dict, summary="刷新 Token")
async def refresh(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    service: AuthService = Depends(),
):
    """使用 refresh_token 获取新的 access_token + refresh_token"""
    result = await service.refresh_token(refresh_token_str=request.refresh_token, db=db)
    return {"code": 200, "message": "Token 刷新成功", "data": result}


@router.get("/me", response_model=dict, summary="获取当前用户信息")
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: AuthService = Depends(),
):
    """根据 Bearer Token 返回当前登录用户详情"""
    result = await service.get_me(user_id=current_user["id"], role=current_user["role"], db=db)
    return {"code": 200, "message": "查询成功", "data": result}
