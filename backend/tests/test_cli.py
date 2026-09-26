import sys
from types import SimpleNamespace

import pytest

from backend.app import cli
from backend.app.security import verify_password


@pytest.mark.asyncio
async def test_bootstrap_creates_hashed_administrator(monkeypatch):
    class Session:
        def __init__(self):
            self.added = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _query):
            return None

        def add(self, value):
            self.added = value

        async def commit(self):
            self.committed = True

    session = Session()
    monkeypatch.setattr(cli, "SessionLocal", lambda: session)
    await cli.bootstrap("new-admin", "a-bootstrap-password-long-enough")
    assert session.added.username == "new-admin"
    assert verify_password("a-bootstrap-password-long-enough", session.added.password_hash)
    assert session.committed


@pytest.mark.asyncio
async def test_bootstrap_rejects_duplicate_username(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _query):
            return object()

    monkeypatch.setattr(cli, "SessionLocal", Session)
    with pytest.raises(SystemExit, match="Administrator already exists"):
        await cli.bootstrap("existing", "a-bootstrap-password-long-enough")


@pytest.mark.asyncio
async def test_reset_password_updates_hash(monkeypatch):
    admin = SimpleNamespace(username="admin", password_hash="old-hash")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _query):
            return admin

        async def commit(self):
            self.committed = True

    monkeypatch.setattr(cli, "SessionLocal", Session)
    await cli.reset_password("admin", "a-new-password-long-enough")
    assert verify_password("a-new-password-long-enough", admin.password_hash)


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password():
    with pytest.raises(SystemExit, match="at least 12"):
        await cli.reset_password("admin", "short")


@pytest.mark.asyncio
async def test_reset_password_requires_existing_admin(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalar(self, _query):
            return None

    monkeypatch.setattr(cli, "SessionLocal", Session)
    with pytest.raises(SystemExit, match="Administrator not found"):
        await cli.reset_password("missing", "a-new-password-long-enough")


@pytest.mark.parametrize(
    ("command", "password_arg"),
    [("create-admin", None), ("reset-password", "cli-test-password-value")],
)
def test_cli_commands_dispatch_and_prompt_safely(monkeypatch, command, password_arg):
    calls = []

    async def fake_operation(username, password):
        calls.append((username, password))

    operation_name = "bootstrap" if command == "create-admin" else "reset_password"
    monkeypatch.setattr(cli, operation_name, fake_operation)
    monkeypatch.setattr(cli, "getpass", lambda _prompt: "prompted-password-value")
    sys_argv = ["afm", command, "--username", "cli-admin"]
    if password_arg:
        sys_argv.extend(["--password", password_arg])
    monkeypatch.setattr(sys, "argv", sys_argv)

    cli.main()

    expected_password = password_arg or "prompted-password-value"
    assert calls == [("cli-admin", expected_password)]
