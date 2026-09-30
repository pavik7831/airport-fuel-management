from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool


class LegacyTokenResponse(BaseModel):
    access_token: str
    user_email: EmailStr


class UserResponse(BaseModel):
    email: EmailStr
