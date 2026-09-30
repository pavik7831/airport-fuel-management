import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

os.environ.setdefault("JWT_SECRET", "unit-test-secret-with-more-than-32-bytes")
os.environ.setdefault("CSRF_SECRET", "unit-test-csrf-secret-value-over-32")

from backend.app.config import settings  # noqa: E402
from backend.app.security import (  # noqa: E402
    create_csrf_token,
    create_token,
    current_admin,
    hash_password,
    valid_csrf_token,
    verify_password,
)


def test_password_hash_uses_one_way_argon2id_verification():
    encoded = hash_password("a-unique-long-password")
    assert encoded != "a-unique-long-password"
    assert encoded.startswith("$argon2id$")
    assert verify_password("a-unique-long-password", encoded)
    assert not verify_password("incorrect-password", encoded)


def test_access_token_claim_and_expiration_validation():
    token = create_token(17)
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert claims["sub"] == "17"
    expired = jwt.encode(
        {"sub": "17", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def test_csrf_double_submit_token_is_signed_and_tamper_evident():
    token = create_csrf_token()
    assert valid_csrf_token(token)
    assert not valid_csrf_token("forged")
    assert not valid_csrf_token(token[:-1] + ("0" if token[-1] != "0" else "1"))


def make_request(method="GET", cookies=None, headers=None):
    request_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        request_headers.append((b"cookie", cookie_header.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/v1/test",
            "headers": request_headers,
            "query_string": b"",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


class AdminLookup:
    def __init__(self, admin):
        self.admin = admin

    async def get(self, _model, _admin_id):
        return self.admin


@pytest.mark.asyncio
async def test_current_admin_rejects_missing_invalid_expired_and_inactive_sessions():
    admin = SimpleNamespace(id=17, active=True)
    db = AdminLookup(admin)
    with pytest.raises(HTTPException) as missing:
        await current_admin(make_request(), None, db)
    assert missing.value.status_code == 401

    for token in (
        "invalid-token",
        jwt.encode({}, settings.jwt_secret, algorithm=settings.jwt_algorithm),
    ):
        with pytest.raises(HTTPException) as invalid:
            await current_admin(make_request(cookies={"afm_access": token}), None, db)
        assert invalid.value.status_code == 401

    expired_token = jwt.encode(
        {"sub": "17", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException) as expired:
        await current_admin(make_request(cookies={"afm_access": expired_token}), None, db)
    assert expired.value.status_code == 401

    with pytest.raises(HTTPException) as missing_admin:
        await current_admin(
            make_request(),
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_token(17)),
            AdminLookup(None),
        )
    assert missing_admin.value.status_code == 401

    with pytest.raises(HTTPException) as inactive_admin:
        await current_admin(
            make_request(),
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_token(17)),
            AdminLookup(SimpleNamespace(id=17, active=False)),
        )
    assert inactive_admin.value.status_code == 401


@pytest.mark.asyncio
async def test_current_admin_validates_csrf_only_for_cookie_mutations():
    admin = SimpleNamespace(id=17, active=True)
    db = AdminLookup(admin)
    access_token = create_token(admin.id)
    csrf_token = create_csrf_token()
    cookies = {"afm_access": access_token, "afm_csrf": csrf_token}

    assert await current_admin(make_request("GET", cookies), None, db) is admin
    with pytest.raises(HTTPException) as missing_csrf:
        await current_admin(make_request("POST", cookies), None, db)
    assert missing_csrf.value.status_code == 403

    invalid_request = make_request("POST", cookies, headers={"X-CSRF-Token": "forged-token"})
    with pytest.raises(HTTPException) as invalid_csrf:
        await current_admin(invalid_request, None, db)
    assert invalid_csrf.value.status_code == 403

    valid_request = make_request("POST", cookies, headers={"X-CSRF-Token": csrf_token})
    assert await current_admin(valid_request, None, db) is admin
