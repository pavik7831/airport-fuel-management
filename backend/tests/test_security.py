import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest

os.environ.setdefault("JWT_SECRET", "unit-test-secret-with-more-than-32-bytes")
os.environ.setdefault("CSRF_SECRET", "unit-test-csrf-secret-value-over-32")

from backend.app.config import settings  # noqa: E402
from backend.app.security import (  # noqa: E402
    create_csrf_token,
    create_token,
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
