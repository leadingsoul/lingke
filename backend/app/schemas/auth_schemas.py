"""认证模块 Schema"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="用户名/手机号")
    password: str = Field(..., min_length=1, max_length=100)
    user_type: str = Field(..., pattern="^(consumer|cs_staff|admin)$")
    captcha: str | None = None


class WechatLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="微信授权临时 code")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 7200
    user: dict


class UserInfo(BaseModel):
    id: str
    username: str
    name: str
    role: str
    avatar: str | None = None
    phone: str | None = None
    status: str | None = None
    created_at: str


class LogoutResponse(BaseModel):
    message: str = "登出成功"
