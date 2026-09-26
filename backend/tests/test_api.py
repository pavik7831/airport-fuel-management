import os
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
os.environ.setdefault("CSRF_SECRET", "test-csrf-secret-value-with-32-bytes")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from backend.app.db import get_db  # noqa: E402
from backend.app.main import app, is_rate_overlap_violation  # noqa: E402
from backend.app.models import Admin, Base, FuelRate  # noqa: E402
from backend.app.security import hash_password  # noqa: E402


def test_postgres_rate_overlap_constraint_and_conflict_mapping():
    ddl = str(CreateTable(FuelRate.__table__).compile(dialect=postgresql.dialect()))
    assert "EXCLUDE USING gist" in ddl
    assert "daterange(effective_from, effective_to, '[]') WITH &&" in ddl

    class Diagnostic:
        constraint_name = "ex_rate_active_period_no_overlap"

    class DriverError(Exception):
        diag = Diagnostic()

    violation = IntegrityError("insert", {}, DriverError())
    unrelated = IntegrityError("insert", {}, RuntimeError("other constraint"))
    assert is_rate_overlap_violation(violation)
    assert not is_rate_overlap_violation(unrelated)


@pytest.fixture
async def client():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Admin(username="operator", password_hash=hash_password("long-test-password")))
        await session.commit()

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        test_client.session_factory = factory
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_authenticated_full_invoice_api_journey(client):
    assert (await client.get("/api/v1/providers")).status_code == 401
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer expired.or.forged"})
    ).status_code == 401
    invalid_login = await client.post(
        "/api/v1/auth/login", json={"username": "operator", "password": "incorrect-password"}
    )
    assert invalid_login.status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"username": "operator", "password": "long-test-password"}
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    assert (await client.get("/api/v1/auth/me")).json()["username"] == "operator"
    assert (await client.get("/api/v1/config")).json()["default_currency"] == "USD"

    provider = await client.post(
        "/api/v1/providers",
        json={"code": " jetco ", "name": " Jet Co ", "email": "  ", "active": True},
        headers=headers,
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    assert provider.json()["code"] == "JETCO"
    assert provider.json()["name"] == "Jet Co"
    assert provider.json()["email"] is None
    duplicate = await client.post(
        "/api/v1/providers", json={"code": "JETCO", "name": "Duplicate"}, headers=headers
    )
    assert duplicate.status_code == 409
    assert (await client.get("/api/v1/providers?q=Jet")).json()["total"] == 1

    airline = await client.post(
        "/api/v1/airlines", json={"code": "NORTH", "name": "Northern Air"}, headers=headers
    )
    assert airline.status_code == 201
    airline_id = airline.json()["id"]
    date_today = date.today().isoformat()
    rate = await client.post(
        "/api/v1/rates",
        json={
            "provider_id": provider_id,
            "fuel_type": " JET A-1 ",
            "rate_per_unit": "2.50000",
            "currency": "USD",
            "effective_from": "2020-01-01",
            "effective_to": None,
            "active": True,
        },
        headers=headers,
    )
    assert rate.status_code == 201
    overlap = await client.post(
        "/api/v1/rates",
        json={
            "provider_id": provider_id,
            "fuel_type": "JET A-1",
            "rate_per_unit": "3.00000",
            "currency": "USD",
            "effective_from": "2025-01-01",
            "active": True,
        },
        headers=headers,
    )
    assert overlap.status_code == 409

    invoice_data = {
        "reference": " =INV-API-001 ",
        "airline_id": airline_id,
        "provider_id": provider_id,
        "billing_month": date_today[:7] + "-01",
        "invoice_date": date_today,
        "fuel_type": "JET A-1",
        "quantity": "100.000",
        "tax_amount": "0",
        "notes": "Integration run",
    }
    no_csrf = await client.post("/api/v1/invoices", json=invoice_data)
    assert no_csrf.status_code == 403
    created = await client.post("/api/v1/invoices", json=invoice_data, headers=headers)
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]
    assert created.json()["reference"] == "=INV-API-001"
    assert created.json()["subtotal"] == "250.00"
    assert created.json()["total_amount"] == "250.00"
    assert (await client.get("/api/v1/invoices?q=INV-API")).json()["total"] == 1
    assert (await client.get(f"/api/v1/invoices/{invoice_id}")).json()["rate_per_unit"] == "2.50000"
    assert "'=INV-API-001" in (await client.get("/api/v1/invoices/export.csv")).text

    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["active_providers"] == 1
    assert dashboard["active_airlines"] == 1
    assert dashboard["total_invoices"] == 1
    assert dashboard["current_month_amounts"] == [{"currency": "USD", "total": "250.00"}]

    historical_data = {
        **invoice_data,
        "reference": "INV-API-HISTORICAL",
        "billing_month": "2024-06-01",
        "invoice_date": "2024-06-12",
        "quantity": "2.000",
    }
    historical = await client.post("/api/v1/invoices", json=historical_data, headers=headers)
    assert historical.status_code == 201
    last_twelve = (await client.get("/api/v1/dashboard?months=12")).json()
    last_thirty_six = (await client.get("/api/v1/dashboard?months=36")).json()
    assert "2024-06-01" not in [row["month"] for row in last_twelve["monthly_totals"]]
    assert "2024-06-01" in [row["month"] for row in last_thirty_six["monthly_totals"]]

    finalized = await client.post(f"/api/v1/invoices/{invoice_id}/finalize", headers=headers)
    assert finalized.json()["status"] == "FINALIZED"
    edit = await client.put(f"/api/v1/invoices/{invoice_id}", json=invoice_data, headers=headers)
    assert edit.status_code == 409
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_master_data_filters_rate_management_and_invoice_lifecycle(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "operator", "password": "long-test-password"}
    )
    csrf = login.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    assert (await client.get("/health/ready")).json() == {"status": "ready"}

    provider_response = await client.post(
        "/api/v1/providers", json={"code": "FUEL1", "name": "Fuel One"}, headers=headers
    )
    provider_id = provider_response.json()["id"]
    provider_update = await client.put(
        f"/api/v1/providers/{provider_id}",
        json={"code": "FUEL1", "name": "Fuel One Updated", "phone": "+1 555 0100"},
        headers=headers,
    )
    assert provider_update.json()["name"] == "Fuel One Updated"
    assert (await client.get("/api/v1/providers?active=true&page=1&page_size=1")).json()[
        "page_size"
    ] == 1
    assert (await client.get(f"/api/v1/providers/{provider_id}")).status_code == 200
    assert (await client.get("/api/v1/providers?page=0")).status_code == 422

    airline = await client.post(
        "/api/v1/airlines", json={"code": "AIR1", "name": "Air One"}, headers=headers
    )
    airline_id = airline.json()["id"]
    assert (await client.get("/api/v1/airlines?q=Air&active=true")).json()["total"] == 1
    assert (
        await client.put(
            f"/api/v1/airlines/{airline_id}",
            json={"code": "AIR2", "name": "Air Two"},
            headers=headers,
        )
    ).json()["code"] == "AIR2"

    rate = await client.post(
        "/api/v1/rates",
        json={
            "provider_id": provider_id,
            "fuel_type": "JET A-1",
            "rate_per_unit": "3.10000",
            "currency": "USD",
            "effective_from": "2020-01-01",
            "active": True,
        },
        headers=headers,
    )
    rate_id = rate.json()["id"]
    assert (await client.get(f"/api/v1/rates/{rate_id}")).status_code == 200
    filtered_rates = await client.get(
        "/api/v1/rates?provider_id=1&fuel_type=JET%20A-1&effective_on=2024-01-01"
    )
    assert filtered_rates.json()["total"] == 1
    updated_rate = await client.put(
        f"/api/v1/rates/{rate_id}",
        json={
            "provider_id": provider_id,
            "fuel_type": "JET A-1",
            "rate_per_unit": "3.20000",
            "currency": "USD",
            "effective_from": "2020-01-01",
            "active": True,
        },
        headers=headers,
    )
    assert updated_rate.json()["rate_per_unit"] == "3.20000"

    invoice_data = {
        "reference": "INV-LIFECYCLE-1",
        "airline_id": airline_id,
        "provider_id": provider_id,
        "billing_month": "2026-09-01",
        "invoice_date": "2026-09-25",
        "fuel_type": "JET A-1",
        "quantity": "10.000",
        "tax_amount": "1.00",
    }
    created = await client.post("/api/v1/invoices", json=invoice_data, headers=headers)
    assert created.status_code == 201
    invoice_id = created.json()["id"]
    assert created.json()["total_amount"] == "33.00"
    invoice_data["quantity"] = "20.000"
    updated = await client.put(f"/api/v1/invoices/{invoice_id}", json=invoice_data, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["total_amount"] == "65.00"
    result = await client.get(
        "/api/v1/invoices?airline_id=1&provider_id=1&billing_month=2026-09-25&status=draft&page_size=1"
    )
    assert result.json()["total"] == 1
    assert (await client.get("/api/v1/invoices?status=not-a-status")).json()["total"] == 0
    cancelled = await client.post(
        f"/api/v1/invoices/{invoice_id}/cancel",
        json={"reason": "Customer requested correction"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancel_reason"] == "Customer requested correction"
    assert (
        await client.put(f"/api/v1/invoices/{invoice_id}", json=invoice_data, headers=headers)
    ).status_code == 409
    assert (await client.get("/api/v1/invoices/9999")).status_code == 404
    assert (await client.post("/api/v1/invoices/9999/finalize", headers=headers)).status_code == 404
    assert (await client.delete(f"/api/v1/rates/{rate_id}", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/rates/{rate_id}")).json()["active"] is False
    assert (
        await client.delete(f"/api/v1/providers/{provider_id}", headers=headers)
    ).status_code == 204
    assert (await client.get("/api/v1/providers?active=false")).json()["total"] == 1
    assert (
        await client.delete(f"/api/v1/airlines/{airline_id}", headers=headers)
    ).status_code == 204


@pytest.mark.asyncio
async def test_api_validation_not_found_csrf_and_inactive_admin(client):
    login = await client.post(
        "/api/v1/auth/login", json={"username": "operator", "password": "long-test-password"}
    )
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert (await client.post("/api/v1/auth/logout")).status_code == 403
    assert (
        await client.post(
            "/api/v1/providers", json={"code": "BAD", "name": "Bad", "email": "invalid"}
        )
    ).status_code == 403
    csrf = login.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    assert (
        await client.post(
            "/api/v1/providers",
            json={"code": "BAD", "name": "Bad", "email": "invalid"},
            headers=headers,
        )
    ).status_code == 422
    assert (await client.get("/api/v1/providers/9999")).status_code == 404
    assert (
        await client.put(
            "/api/v1/providers/9999", json={"code": "MISSING", "name": "Missing"}, headers=headers
        )
    ).status_code == 404
    assert (await client.delete("/api/v1/airlines/9999", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/rates/9999")).status_code == 404
    assert (await client.delete("/api/v1/rates/9999", headers=headers)).status_code == 404
    assert (await client.put("/api/v1/rates/9999", json={}, headers=headers)).status_code == 422
    assert (await client.get("/api/v1/dashboard?months=0")).status_code == 422
    assert (
        await client.post("/api/v1/invoices/9999/cancel", json={}, headers=headers)
    ).status_code == 422

    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        admin.active = False
        await session.commit()
    assert (await client.get("/api/v1/auth/me")).status_code == 401
