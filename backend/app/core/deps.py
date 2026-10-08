"""FastAPI 依赖注入 — 当前用户获取 + 角色权限校验"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user_models import Consumer, CustomerServiceStaff, Admin

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取当前登录用户（所有角色通用）"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Token 类型")
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

        # 从对应表中查询用户是否存在且未被禁用
        if role == "consumer":
            result = await db.execute(select(Consumer).where(Consumer.id == user_id))
            user = result.scalar_one_or_none()
        elif role == "cs_staff":
            result = await db.execute(select(CustomerServiceStaff).where(CustomerServiceStaff.id == user_id))
            user = result.scalar_one_or_none()
        elif role == "admin":
            result = await db.execute(select(Admin).where(Admin.id == user_id))
            user = result.scalar_one_or_none()
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未知角色")

        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
        user_status = str(getattr(user, "status", "")).lower()
        if user_status in ("0", "disabled", "禁用"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

        return {"id": user_id, "role": role, "username": payload.get("username"), "name": getattr(user, "name", "")}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")


async def get_current_consumer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "consumer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅消费者可访问")
    return current_user


async def get_current_cs_staff(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "cs_staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅客服可访问")
    return current_user


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")
    return current_user


async def get_current_cs_or_admin(current_user: dict = Depends(get_current_user)):
    """客服和管理员均可访问"""
    if current_user["role"] not in ("cs_staff", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅客服或管理员可访问")
    return current_user
