from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()
DbSession = Annotated[Session, Depends(get_db)]


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials, get_settings().secret_key, algorithms=[ALGORITHM]
        )
        email = payload.get("sub")
    except jwt.PyJWTError:
        email = None

    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

