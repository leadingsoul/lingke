"""AuthService — 认证/授权/Token 管理"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_phone,
)
from app.models.user_models import Consumer, CustomerServiceStaff, Admin


class AuthService:
    """认证服务：登录 / 微信登录 / 刷新令牌 / 获取当前用户 / 令牌吊销 / 登录锁定 / 短信验证码"""

    def __init__(self, db=None):
        self.db = db

    # ── 登录 ────────────────────────────────────────────

    async def login(
        self,
        username: str,
        password: str,
        user_type: str,
        captcha: str = None,
        db: AsyncSession = None,
    ) -> dict:
        """用户名+密码登录，返回 TokenResponse 数据"""
        db = db or self.db
        user = None
        role = None

        if user_type == "consumer":
            # 账号密码登录：先用 openid 匹配，再用 nickname 匹配
            result = await db.execute(
                select(Consumer).where(
                    (Consumer.openid == username) | (Consumer.nickname == username)
                )
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                )
            if user.status == 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="账号已被禁用",
                )
            if user.password is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="该账号仅支持微信登录，请使用微信授权登录",
                )
            if not verify_password(password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                )
            role = "consumer"

        elif user_type in ("cs_staff", "admin"):
            if user_type == "cs_staff":
                result = await db.execute(
                    select(CustomerServiceStaff).where(
                        CustomerServiceStaff.username == username
                    )
                )
                user = result.scalar_one_or_none()
                role = "cs_staff"
                if user and str(user.status).lower() in ("禁用", "disabled"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="账号已被禁用",
                    )
            else:
                result = await db.execute(
                    select(Admin).where(Admin.username == username)
                )
                user = result.scalar_one_or_none()
                role = "admin"
                if user and user.status == 0:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="账号已被禁用",
                    )

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                )
            if not verify_password(password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 登录成功：客服自动设为在线（被禁用则不改为在线）
        if role == "cs_staff" and getattr(user, "status", "") not in (0, "禁用"):
            user.status = "在线"
            await db.flush()

        token_data = {
            "sub": user.id,
            "role": role,
            "username": getattr(user, "username", getattr(user, "openid", "")),
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 7200,
            "user": {
                "id": user.id,
                "username": getattr(user, "username", getattr(user, "openid", "")),
                "name": getattr(user, "name", getattr(user, "nickname", "")),
                "role": role,
                "avatar": getattr(user, "avatar", None),
                "phone": getattr(user, "phone", None),
                "status": str(getattr(user, "status", 1)),
                "created_at": str(user.created_at) if user.created_at else "",
            },
        }

    # ── 微信登录 ──────────────────────────────────────

    async def wechat_login(self, code: str, db: AsyncSession = None) -> dict:
        """微信授权码登录（当前 mock）"""
        db = db or self.db
        fake_openid = f"wx_{code[:16]}_{uuid.uuid4().hex[:8]}"

        result = await db.execute(
            select(Consumer).where(Consumer.openid == fake_openid)
        )
        consumer = result.scalar_one_or_none()

        if consumer is None:
            consumer = Consumer(
                id=uuid.uuid4().hex,
                openid=fake_openid,
                nickname=f"微信用户_{fake_openid[-6:]}",
                role="consumer",
                status=1,
                created_at=datetime.now(timezone.utc),
            )
            db.add(consumer)
            # Explicitly persist and COMMIT so subsequent requests can find this user
            # (FastAPI get_db only commits after response is sent — we need it NOW)
            await db.flush()
            await db.commit()

        if consumer.status == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用",
            )

        token_data = {
            "sub": consumer.id,
            "role": "consumer",
            "username": consumer.openid,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 7200,
            "user": {
                "id": consumer.id,
                "username": consumer.openid,
                "name": consumer.nickname or "",
                "role": "consumer",
                "avatar": consumer.avatar,
                "phone": consumer.phone,
                "status": str(consumer.status),
                "created_at": str(consumer.created_at) if consumer.created_at else "",
            },
        }

    # ── 刷新令牌 ──────────────────────────────────────

    async def refresh_token(self, refresh_token_str: str, db: AsyncSession = None) -> dict:
        """用刷新令牌换取新的访问令牌"""
        db = db or self.db
        import jwt as pyjwt

        try:
            payload = decode_token(refresh_token_str)
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已过期，请重新登录",
            )
        except pyjwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌无效",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌类型",
            )

        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌无效",
            )

        if role == "consumer":
            result = await db.execute(select(Consumer).where(Consumer.id == user_id))
            user = result.scalar_one_or_none()
        elif role == "cs_staff":
            result = await db.execute(
                select(CustomerServiceStaff).where(CustomerServiceStaff.id == user_id)
            )
            user = result.scalar_one_or_none()
        elif role == "admin":
            result = await db.execute(select(Admin).where(Admin.id == user_id))
            user = result.scalar_one_or_none()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未知角色",
            )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )

        token_data = {
            "sub": user_id,
            "role": role,
            "username": payload.get("username", ""),
        }
        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 7200,
            "user": {
                "id": user.id,
                "username": getattr(user, "username", getattr(user, "openid", "")),
                "name": getattr(user, "name", getattr(user, "nickname", "")),
                "role": role,
                "avatar": getattr(user, "avatar", None),
                "phone": getattr(user, "phone", None),
                "status": str(getattr(user, "status", 1)),
                "created_at": str(user.created_at) if user.created_at else "",
            },
        }

    # ── 获取当前用户 ──────────────────────────────────

    async def get_me(self, user_id: str, role: str, db: AsyncSession = None) -> dict:
        """获取用户详细信息"""
        db = db or self.db
        if role == "consumer":
            result = await db.execute(select(Consumer).where(Consumer.id == user_id))
            user = result.scalar_one_or_none()
        elif role == "cs_staff":
            result = await db.execute(
                select(CustomerServiceStaff).where(CustomerServiceStaff.id == user_id)
            )
            user = result.scalar_one_or_none()
        elif role == "admin":
            result = await db.execute(select(Admin).where(Admin.id == user_id))
            user = result.scalar_one_or_none()
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        return {
            "id": user.id,
            "username": getattr(user, "username", getattr(user, "openid", "")),
            "name": getattr(user, "name", getattr(user, "nickname", "")),
            "role": role,
            "avatar": getattr(user, "avatar", None),
            "phone": getattr(user, "phone", None),
            "email": getattr(user, "email", None),
            "status": str(getattr(user, "status", 1)),
            "created_at": str(user.created_at) if user.created_at else "",
            "updated_at": str(user.updated_at) if user.updated_at else "",
        }

    # ── 登出 ──────────────────────────────────────────

    async def logout(self, token: str, db: AsyncSession = None) -> None:
        """登出：黑名单 token + 客服/管理员设为离线"""
        db = db or self.db
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            role = payload.get("role")
            if role == "cs_staff" and user_id and db:
                result = await db.execute(
                    select(CustomerServiceStaff).where(CustomerServiceStaff.id == user_id)
                )
                staff = result.scalar_one_or_none()
                if staff and staff.status != "禁用":
                    staff.status = "离线"
                    await db.flush()
        except Exception:
            pass  # token 已失效也不影响登出

    # ── 吊销令牌 ──────────────────────────────────────

    async def revoke_token(self, redis, token: str) -> None:
        """将令牌加入 Redis 黑名单"""
        try:
            payload = decode_token(token)
            exp = payload.get("exp", 0)
            now = datetime.now(timezone.utc).timestamp()
            ttl = max(int(exp - now), 1)
            key = f"blacklist:token:{token[-32:]}"
            await redis.setex(key, ttl, "1")
        except Exception:
            key = f"blacklist:token:{token[-32:]}"
            await redis.setex(key, 3600, "1")

    # ── 登录锁定检查 ─────────────────────────────────

    async def check_login_lockout(self, redis, username: str) -> bool:
        """检查用户名是否被锁定（5 次失败 = 30 分钟锁）"""
        key = f"login:fail:{username}"
        count = await redis.get(key)
        if count and int(count) >= 5:
            return True
        return False

    async def _record_login_failure(self, redis, username: str) -> None:
        """记录一次登录失败"""
        key = f"login:fail:{username}"
        await redis.incr(key)
        await redis.expire(key, 1800)

    # ── 发送短信验证码 ────────────────────────────────

    async def send_sms_code(self, redis, phone: str) -> None:
        """发送短信验证码（mock — 仅日志输出）"""
        import random
        import logging

        logger = logging.getLogger(__name__)
        code = str(random.randint(100000, 999999))
        key = f"sms:code:{phone}"
        await redis.setex(key, 300, code)
        logger.info(f"[Mock SMS] To: {phone}, Code: {code}")
