import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models import Admin

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return passwords.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return passwords.verify(password, encoded)


def create_token(admin_id: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(admin_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_csrf_token() -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(settings.csrf_secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def valid_csrf_token(token: str) -> bool:
    try:
        nonce, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(settings.csrf_secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


async def current_admin(
    request: Request, credentials=Depends(bearer), db: AsyncSession = Depends(get_db)
) -> Admin:
    token = credentials.credentials if credentials else request.cookies.get("afm_access")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        admin_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc
    admin = await db.get(Admin, admin_id)
    if not admin or not admin.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator account is inactive")
    if request.cookies.get("afm_access"):
        csrf = request.headers.get("x-csrf-token")
        expected = request.cookies.get("afm_csrf")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and (
            not csrf or csrf != expected or not valid_csrf_token(csrf)
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    return admin
