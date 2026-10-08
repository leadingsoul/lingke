"""应用配置中心 — 所有配置从 .env 读取，通过 Pydantic Settings 统一管理"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # ── 应用基础 ──
    APP_NAME: str = "E-Commerce After-Sales Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENV: str = "development"

    # ── 服务端口 ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── JWT ──
    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── 数据库 ──
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_NAME: str = "ecommerce_service"

    # ── Redis ──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ── LLM ──
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 3

    # ── AES ──
    AES_KEY: str = "change-me-32byte-aes-key-here!!"
    AES_IV: str = "change-me-16byte"

    # ── CORS ──
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    # ── 速率限制 ──
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── 文件上传 ──
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png"

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
