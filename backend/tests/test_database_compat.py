import asyncio
import runpy
from contextlib import contextmanager
from pathlib import Path

import pytest

from backend.app import database
from backend.app import db as async_database
from backend.app.config import Settings


class FakeConnection:
    columns = {
        "fuel_providers": {"email", "phone"},
        "airlines": {"email", "phone"},
        "fuel_rates": {"rate_per_litre", "effective_from"},
        "invoices": {
            "invoice_number",
            "fuel_provider_id",
            "fuel_quantity_litres",
            "rate_per_litre",
        },
    }

    def __init__(self):
        self.statements = []

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        for table, columns in self.columns.items():
            if f"table_name = '{table}'" in sql:
                return [(column,) for column in columns]
        return []


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def begin(self):
        yield self.connection


def test_compatibility_migration_adds_and_copies_legacy_columns(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(database, "engine", FakeEngine(connection))

    database.run_compatibility_migrations()

    statements = "\n".join(connection.statements)
    assert "ADD COLUMN IF NOT EXISTS contact_email" in statements
    assert "UPDATE fuel_providers SET contact_email = email" in statements
    assert "UPDATE airlines SET contact_phone = phone" in statements
    assert "UPDATE fuel_rates SET rate = rate_per_litre" in statements
    assert "UPDATE fuel_rates SET effective_date = effective_from" in statements
    assert "UPDATE invoices SET reference_number = invoice_number" in statements
    assert "UPDATE invoices SET provider_id = fuel_provider_id" in statements
    assert "UPDATE invoices SET fuel_quantity = fuel_quantity_litres" in statements
    assert "UPDATE invoices SET fuel_rate = rate_per_litre" in statements


def test_sync_database_dependency_closes_session(monkeypatch):
    closed = []
    session = type("Session", (), {"close": lambda self: closed.append(True)})()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)
    assert closed == [True]


@pytest.mark.asyncio
async def test_async_database_dependency_closes_session(monkeypatch):
    closed = []
    session = object()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            closed.append(True)

    monkeypatch.setattr(async_database, "SessionLocal", SessionContext)
    dependency = async_database.get_db()

    assert await anext(dependency) is session
    with pytest.raises(StopAsyncIteration):
        await anext(dependency)
    assert closed == [True]


def test_settings_normalize_sync_postgresql_url_and_preserve_other_drivers():
    common = {"jwt_secret": "j" * 32, "csrf_secret": "c" * 32}
    postgres = Settings(database_url="postgresql://user:pass@localhost/afm", **common)
    sqlite = Settings(database_url="sqlite+aiosqlite:///afm.db", **common)

    assert postgres.database_url == "postgresql+asyncpg://user:pass@localhost/afm"
    assert sqlite.database_url == "sqlite+aiosqlite:///afm.db"


def test_standalone_async_database_module_initializes():
    namespace = runpy.run_path(str(Path(database.__file__).with_name("db.py")))
    assert namespace["engine"] is not None
    assert namespace["SessionLocal"] is not None
    asyncio.run(namespace["engine"].dispose())


@pytest.mark.asyncio
async def test_standalone_async_database_dependency_closes_session():
    namespace = runpy.run_path(str(Path(database.__file__).with_name("db.py")))
    closed = []
    session = object()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            closed.append(True)

    namespace["get_db"].__globals__["SessionLocal"] = SessionContext
    dependency = namespace["get_db"]()
    assert await anext(dependency) is session
    with pytest.raises(StopAsyncIteration):
        await anext(dependency)
    assert closed == [True]
    await namespace["engine"].dispose()
