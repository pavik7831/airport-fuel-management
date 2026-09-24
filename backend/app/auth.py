from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AdminUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expires}, settings.secret_key, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> AdminUser:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc
    user = db.query(AdminUser).filter(AdminUser.email == email, AdminUser.is_active.is_(True)).first()
    if not user:
        raise credentials_error
    return user
