from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, verify_password
from .db.session import get_db
from .models.user import User
from .schemas.auth import LegacyTokenResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=LegacyTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return LegacyTokenResponse(access_token=create_access_token(user.email), user_email=user.email)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(email=user.email)
