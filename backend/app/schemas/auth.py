from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class RegisterRequest(AuthRequest):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)


class LoginRequest(AuthRequest):
    username: str = Field(min_length=1, max_length=50)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: EmailStr
    avatar_url: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
