"""用户域模型：Consumer / CustomerServiceStaff / Admin"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Consumer(Base):
    __tablename__ = "consumer"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    openid: Mapped[str] = mapped_column(String(100), unique=True, nullable=True, comment="微信 OpenID（账号密码登录时可为 NULL）")
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="昵称")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像 URL")
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="AES-256 加密存储")
    platform_account: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="电商平台关联账号")
    password: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="bcrypt 密码（账号登录用）")
    role: Mapped[str] = mapped_column(String(20), default="consumer", comment="角色标识")
    status: Mapped[int] = mapped_column(default=1, comment="1 正常 / 0 禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class CustomerServiceStaff(Base):
    __tablename__ = "customer_service_staff"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 加密")
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="普通客服", comment="普通客服 / 客服主管")
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="AES-256 加密")
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="离线", comment="在线 / 离线 / 禁用")
    max_concurrent: Mapped[int] = mapped_column(default=5, comment="最大同时接待数")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())


class Admin(Base):
    __tablename__ = "admin"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 加密")
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="admin", comment="超级管理员 / 普通管理员")
    status: Mapped[int] = mapped_column(default=1, comment="1 正常 / 0 禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())
