import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .core.config import get_settings
from .core.security import create_access_token, hash_password, verify_password
from .db.session import get_db
from .models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
__all__ = ["create_access_token", "get_current_user", "get_password_hash", "verify_password"]


def get_password_hash(password: str) -> str:
    return hash_password(password)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        email = payload.get("sub")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from exc
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = db.query(User).filter(User.email == email, User.is_admin.is_(True)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
