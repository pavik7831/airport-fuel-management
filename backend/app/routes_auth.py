from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, verify_password
from .database import get_db
from .models import AdminUser
from .schemas import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AdminUser).filter(AdminUser.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.email), user_email=user.email)


@router.get("/me", response_model=UserResponse)
def me(user: AdminUser = Depends(get_current_user)):
    return UserResponse(email=user.email)
