from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, get_current_admin
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    user: Annotated[User, Depends(get_current_admin)],
) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, email=user.email, is_admin=user.is_admin)
