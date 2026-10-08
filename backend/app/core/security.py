"""鉴权工具 — JWT 签发/验证 + bcrypt 密码哈希 + AES 手机号加解密"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from cryptography.fernet import Fernet
import base64
import hashlib
from app.core.config import get_settings

settings = get_settings()


# ═══════════════ 密码 ═══════════════

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ═══════════════ JWT ═══════════════

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ═══════════════ AES 手机号加密 ═══════════════

def _get_aes_cipher() -> Fernet:
    key = hashlib.sha256(settings.AES_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_phone(phone: str) -> str:
    cipher = _get_aes_cipher()
    return cipher.encrypt(phone.encode()).decode()


def decrypt_phone(encrypted: str) -> str:
    cipher = _get_aes_cipher()
    return cipher.decrypt(encrypted.encode()).decode()


def mask_phone(phone: str) -> str:
    """手机号脱敏显示：138****8000"""
    if len(phone) >= 11:
        return phone[:3] + "****" + phone[-4:]
    return phone[:3] + "****" + phone[-2:] if len(phone) >= 5 else "****"
