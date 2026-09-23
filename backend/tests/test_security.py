import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.core.security import create_access_token, hash_password, verify_password


def test_password_can_be_verified():
    password = "SafePassword123!"
    assert verify_password(password, hash_password(password))


def test_access_token_contains_subject():
    assert create_access_token("admin@example.com")

