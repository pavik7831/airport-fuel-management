import os
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable
from starlette.requests import Request

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
os.environ.setdefault("CSRF_SECRET", "test-csrf-secret-value-with-32-bytes")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from backend.app import main  # noqa: E402
from backend.app.db import get_db  # noqa: E402
from backend.app.main import app, is_rate_overlap_violation, safe_csv_cell  # noqa: E402
from backend.app.models import Admin, Airline, Base, FuelRate, Provider  # noqa: E402
from backend.app.schemas import CancelIn, EntityIn, InvoiceIn, LoginIn, RateIn  # noqa: E402
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
    filtered_export = await client.get(
        "/api/v1/invoices/export.csv",
        params={
            "q": "INV-API",
            "airline_id": airline_id,
            "provider_id": provider_id,
            "billing_month": date_today,
            "status": "DRAFT",
        },
    )
    assert "'=INV-API-001" in filtered_export.text
    empty_export = await client.get("/api/v1/invoices/export.csv", params={"q": "no-match"})
    assert "'=INV-API-001" not in empty_export.text

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
    assert finalized.json()["payment_status"] == "UNPAID"
    assert finalized.json()["balance_due"] == "250.00"
    payment_data = {
        "amount": "100.00",
        "payment_date": date_today,
        "reference": "BANK-TRANSFER-1",
        "notes": "First installment",
    }
    assert (
        await client.post(f"/api/v1/invoices/{invoice_id}/payments", json=payment_data)
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/invoices/9999/payments",
            json=payment_data,
            headers=headers,
        )
    ).status_code == 404
    partial_payment = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments", json=payment_data, headers=headers
    )
    assert partial_payment.status_code == 201
    assert partial_payment.json()["paid_amount"] == "100.00"
    assert partial_payment.json()["balance_due"] == "150.00"
    assert partial_payment.json()["payment_status"] == "PARTIALLY_PAID"
    assert partial_payment.json()["payments"][0]["reference"] == "BANK-TRANSFER-1"
    receivables = (await client.get("/api/v1/dashboard")).json()["outstanding_receivables"]
    assert receivables == [{"currency": "USD", "balance_due": "150.00", "invoice_count": 1}]
    payment_list = await client.get("/api/v1/invoices?q=INV-API-001")
    assert payment_list.json()["items"][0]["paid_amount"] == "100.00"
    assert payment_list.json()["items"][0]["balance_due"] == "150.00"
    payment_export = await client.get("/api/v1/invoices/export.csv", params={"q": "INV-API-001"})
    assert "100.00,150.00,PARTIALLY_PAID" in payment_export.text
    excessive_payment = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "150.01", "payment_date": date_today},
        headers=headers,
    )
    assert excessive_payment.status_code == 409
    completed_payment = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": "150.00", "payment_date": date_today},
        headers=headers,
    )
    assert completed_payment.status_code == 201
    assert completed_payment.json()["balance_due"] == "0.00"
    assert completed_payment.json()["payment_status"] == "PAID"
    assert (await client.get("/api/v1/dashboard")).json()["outstanding_receivables"] == []
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        with pytest.raises(HTTPException) as paid_invoice:
            await main.post_invoice_payment(
                invoice_id=invoice_id,
                data=main.InvoicePaymentIn(amount=Decimal("0.01")),
                db=session,
                admin=admin,
            )
    assert paid_invoice.value.status_code == 409
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
    immutable_rate = await client.put(
        f"/api/v1/rates/{rate_id}",
        json={
            "provider_id": provider_id,
            "fuel_type": "JET A-1",
            "rate_per_unit": "3.30000",
            "currency": "USD",
            "effective_from": "2020-01-01",
            "active": True,
        },
        headers=headers,
    )
    assert immutable_rate.status_code == 409
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


@pytest.mark.asyncio
async def test_health_headers_and_readiness_failure(client):
    live = await client.get("/health/live", headers={"X-Request-ID": "request-123"})
    assert live.json() == {"status": "ok"}
    assert live.headers["X-Request-ID"] == "request-123"
    assert live.headers["X-Content-Type-Options"] == "nosniff"
    assert live.headers["X-Frame-Options"] == "DENY"
    assert live.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert live.headers["Cache-Control"] == "no-cache"

    previous_dependency = app.dependency_overrides[get_db]

    class UnavailableDatabase:
        async def execute(self, _statement):
            raise RuntimeError("database unavailable")

    async def unavailable_db():
        yield UnavailableDatabase()

    app.dependency_overrides[get_db] = unavailable_db
    try:
        response = await client.get("/health/ready")
    finally:
        app.dependency_overrides[get_db] = previous_dependency

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


@pytest.mark.asyncio
async def test_payment_endpoint_rejects_missing_invoice(client):
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        with pytest.raises(HTTPException) as missing:
            await main.post_invoice_payment(
                invoice_id=9999,
                data=main.InvoicePaymentIn(amount=Decimal("1.00")),
                db=session,
                admin=admin,
            )
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_app_lifespan_disposes_database_engine(monkeypatch):
    from backend.app import main

    disposed = []

    class DisposableEngine:
        async def dispose(self):
            disposed.append(True)

    monkeypatch.setattr(main, "engine", DisposableEngine())
    async with app.router.lifespan_context(app):
        pass
    assert disposed == [True]


@pytest.mark.asyncio
async def test_rate_limited_login_handler_and_dashboard_aggregation(client):
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        response = Response()
        login_result = await main.login.__wrapped__(
            request,
            LoginIn(username="operator", password="long-test-password"),
            response,
            session,
        )
        assert login_result["username"] == "operator"
        assert response.headers.getlist("set-cookie")

        dashboard_result = await main.dashboard(months=12, db=session, _=admin)
        assert dashboard_result["active_providers"] == 0
        assert dashboard_result["active_airlines"] == 0
        assert dashboard_result["active_rates"] == 0
        assert dashboard_result["total_invoices"] == 0
        assert dashboard_result["monthly_totals"] == []
        assert dashboard_result["recent_invoices"] == []

        with pytest.raises(HTTPException) as invalid_login:
            await main.login.__wrapped__(
                request,
                LoginIn(username="missing", password="incorrect"),
                Response(),
                session,
            )
        assert invalid_login.value.status_code == 401


@pytest.mark.asyncio
async def test_main_entity_and_rate_handler_branches(client):
    def request(path, method="GET"):
        return Request(
            {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [],
                "query_string": b"",
                "server": ("test", 80),
                "client": ("127.0.0.1", 1234),
                "scheme": "http",
            }
        )

    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        provider_request = request("/api/v1/providers", "POST")
        provider_payload = EntityIn(code="DIRECT1", name="Direct Fuel")
        provider = await main.create_entity(provider_request, provider_payload, session, admin)
        provider_id = provider.id
        assert provider.code == "DIRECT1"
        with pytest.raises(HTTPException) as duplicate_provider:
            await main.create_entity(provider_request, provider_payload, session, admin)
        assert duplicate_provider.value.status_code == 409

        second_provider = await main.create_entity(
            provider_request, EntityIn(code="DIRECT2", name="Other Fuel"), session, admin
        )
        second_provider_id = second_provider.id
        with pytest.raises(HTTPException) as duplicate_update:
            await main.update_entity(
                request(f"/api/v1/providers/{second_provider_id}", "PUT"),
                second_provider_id,
                EntityIn(code="DIRECT1", name="Duplicate Fuel"),
                session,
                admin,
            )
        assert duplicate_update.value.status_code == 409
        updated = await main.update_entity(
            request(f"/api/v1/providers/{provider_id}", "PUT"),
            provider_id,
            EntityIn(code="DIRECT1", name="Updated Direct Fuel"),
            session,
            admin,
        )
        assert updated.name == "Updated Direct Fuel"
        listed = await main.list_entities(
            request("/api/v1/providers"), "Direct", True, 1, 20, session, admin
        )
        assert listed["total"] == 2
        assert (
            await main.get_entity(
                request(f"/api/v1/providers/{provider_id}"), provider_id, session, admin
            )
        ).id == provider_id
        with pytest.raises(HTTPException) as bad_kind:
            await main.list_entities(request("/api/v1/unknown"), "", None, 1, 20, session, admin)
        assert bad_kind.value.status_code == 404
        with pytest.raises(HTTPException) as missing_entity:
            await main.get_entity(request("/api/v1/providers/999"), 999, session, admin)
        assert missing_entity.value.status_code == 404
        with pytest.raises(HTTPException) as missing_update:
            await main.update_entity(
                request("/api/v1/providers/999", "PUT"), 999, provider_payload, session, admin
            )
        assert missing_update.value.status_code == 404
        await main.deactivate_entity(
            request(f"/api/v1/providers/{second_provider_id}", "DELETE"),
            second_provider_id,
            session,
            admin,
        )
        with pytest.raises(HTTPException) as missing_deactivate:
            await main.deactivate_entity(
                request("/api/v1/providers/999", "DELETE"), 999, session, admin
            )
        assert missing_deactivate.value.status_code == 404

        rate_data = RateIn(
            provider_id=provider.id,
            fuel_type="JET A-1",
            rate_per_unit="2.5",
            currency="USD",
            effective_from="2026-01-01",
        )
        rate = await main.create_rate(rate_data, session, admin)
        rate_id = rate.id
        assert rate.rate_per_unit == Decimal("2.5")
        with pytest.raises(HTTPException) as missing_provider:
            await main.create_rate(
                rate_data.model_copy(update={"provider_id": 999}), session, admin
            )
        assert missing_provider.value.status_code == 422
        with pytest.raises(HTTPException) as overlapping_create:
            await main.create_rate(
                rate_data.model_copy(update={"effective_from": date(2026, 2, 1)}), session, admin
            )
        assert overlapping_create.value.status_code == 409
        rates = await main.list_rates(
            provider.id, "JET A-1", True, date(2026, 3, 1), 1, 20, session, admin
        )
        assert rates["total"] == 1
        updated_rate = await main.update_rate(rate_id, rate_data, session, admin)
        assert updated_rate.id == rate_id
        with pytest.raises(HTTPException) as missing_rate:
            await main.update_rate(999, rate_data, session, admin)
        assert missing_rate.value.status_code == 404
        with pytest.raises(HTTPException) as missing_rate_get:
            await main.get_rate(999, session, admin)
        assert missing_rate_get.value.status_code == 404
        await main.deactivate_rate(rate_id, session, admin)
        with pytest.raises(HTTPException) as missing_rate_deactivate:
            await main.deactivate_rate(999, session, admin)
        assert missing_rate_deactivate.value.status_code == 404

        with pytest.raises(HTTPException) as unsupported_entity:
            await main.create_entity(
                request("/api/v1/unknown", "POST"), provider_payload, session, admin
            )
        assert unsupported_entity.value.status_code == 404


@pytest.mark.asyncio
async def test_main_entity_write_failures_are_rolled_back(client):
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        provider = Provider(id=99, code="FAILURE", name="Failure Provider")
        payload = EntityIn(code="FAILURE", name="Failure Provider")

        class FailingSession:
            def __init__(self, message):
                self.message = message
                self.rollback_count = 0

            async def get(self, _model, _item_id):
                return provider

            def add(self, _item):
                pass

            async def commit(self):
                raise RuntimeError(self.message)

            async def rollback(self):
                self.rollback_count += 1

        duplicate = FailingSession("unique constraint violation")
        with pytest.raises(HTTPException) as create_conflict:
            await main.create_entity(
                Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/api/v1/providers",
                        "headers": [],
                        "query_string": b"",
                        "server": ("test", 80),
                        "client": ("127.0.0.1", 1234),
                        "scheme": "http",
                    }
                ),
                payload,
                duplicate,
                admin,
            )
        assert create_conflict.value.status_code == 409
        assert duplicate.rollback_count == 1

        create_failure = FailingSession("database unavailable")
        with pytest.raises(RuntimeError, match="database unavailable"):
            await main.create_entity(
                Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "path": "/api/v1/providers",
                        "headers": [],
                        "query_string": b"",
                        "server": ("test", 80),
                        "client": ("127.0.0.1", 1234),
                        "scheme": "http",
                    }
                ),
                payload,
                create_failure,
                admin,
            )
        assert create_failure.rollback_count == 1

        update_failure = FailingSession("database unavailable")
        with pytest.raises(RuntimeError, match="database unavailable"):
            await main.update_entity(
                Request(
                    {
                        "type": "http",
                        "method": "PUT",
                        "path": "/api/v1/providers/99",
                        "headers": [],
                        "query_string": b"",
                        "server": ("test", 80),
                        "client": ("127.0.0.1", 1234),
                        "scheme": "http",
                    }
                ),
                99,
                payload,
                update_failure,
                admin,
            )
        assert update_failure.rollback_count == 1


@pytest.mark.asyncio
async def test_main_rate_overlap_conflicts_and_integrity_errors(client):
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        provider = Provider(id=50, code="RATE-FAIL", name="Rate Failure", active=True)
        rate = FuelRate(
            id=60,
            provider_id=provider.id,
            fuel_type="JET A-1",
            rate_per_unit=Decimal("2.5"),
            currency="USD",
            effective_from=date(2026, 1, 1),
            active=True,
        )
        payload = RateIn(
            provider_id=provider.id,
            fuel_type="JET A-1",
            rate_per_unit="2.5",
            currency="USD",
            effective_from="2026-01-01",
        )

        class Diagnostic:
            constraint_name = "ex_rate_active_period_no_overlap"

        class DriverError(Exception):
            diag = Diagnostic()

        class UnrelatedDriverError(Exception):
            pass

        class RateFailureDatabase:
            def __init__(self, values, error=None):
                self.values = list(values)
                self.error = error
                self.rollback_count = 0

            async def get(self, model, _item_id):
                if getattr(self, "missing", False):
                    return None
                return provider if model is Provider else rate

            async def scalar(self, _statement):
                return self.values.pop(0)

            def add(self, _item):
                pass

            async def commit(self):
                if self.error:
                    raise self.error

            async def rollback(self):
                self.rollback_count += 1

            async def refresh(self, _item):
                return None

        overlap_error = IntegrityError("insert", {}, DriverError())
        create_overlap = RateFailureDatabase([None], overlap_error)
        with pytest.raises(HTTPException) as create_conflict:
            await main.create_rate(payload, create_overlap, admin)
        assert create_conflict.value.status_code == 409
        assert create_overlap.rollback_count == 1

        unrelated_error = IntegrityError("insert", {}, UnrelatedDriverError("other constraint"))
        create_failure = RateFailureDatabase([None], unrelated_error)
        with pytest.raises(IntegrityError):
            await main.create_rate(payload, create_failure, admin)
        assert create_failure.rollback_count == 1

        referenced = RateFailureDatabase([1])
        with pytest.raises(HTTPException) as immutable:
            await main.update_rate(rate.id, payload, referenced, admin)
        assert immutable.value.status_code == 409

        update_overlap = RateFailureDatabase([None, 1])
        with pytest.raises(HTTPException) as overlap:
            await main.update_rate(rate.id, payload, update_overlap, admin)
        assert overlap.value.status_code == 409

        update_failure = RateFailureDatabase([None, None], overlap_error)
        with pytest.raises(HTTPException) as update_conflict:
            await main.update_rate(rate.id, payload, update_failure, admin)
        assert update_conflict.value.status_code == 409
        assert update_failure.rollback_count == 1

        unrelated_update = RateFailureDatabase([None, None], unrelated_error)
        with pytest.raises(IntegrityError):
            await main.update_rate(rate.id, payload, unrelated_update, admin)
        assert unrelated_update.rollback_count == 1

        assert (await main.get_rate(rate.id, RateFailureDatabase([]), admin)).id == rate.id
        missing_database = RateFailureDatabase([])
        missing_database.missing = True
        with pytest.raises(HTTPException) as missing_rate:
            await main.get_rate(999, missing_database, admin)
        assert missing_rate.value.status_code == 404


@pytest.mark.asyncio
async def test_main_invoice_handlers_filter_update_export_and_finalize(client):
    async with client.session_factory() as session:
        admin = await session.scalar(select(Admin).where(Admin.username == "operator"))
        provider = Provider(code="HANDLER-FUEL", name="Handler Fuel")
        airline = Airline(code="HANDLER-AIR", name="Handler Air")
        session.add_all([provider, airline])
        await session.flush()
        rate = FuelRate(
            provider_id=provider.id,
            fuel_type="JET A-1",
            rate_per_unit=Decimal("2.5"),
            currency="USD",
            effective_from=date(2026, 1, 1),
            active=True,
        )
        session.add(rate)
        await session.commit()
        await main.ready(session)

        invoice_data = InvoiceIn(
            reference="HANDLER-INVOICE-1",
            airline_id=airline.id,
            provider_id=provider.id,
            billing_month=date(2026, 9, 15),
            invoice_date=date(2026, 9, 10),
            fuel_type="JET A-1",
            quantity=Decimal("4"),
            notes="export me",
        )
        invoice = await main.post_invoice(invoice_data, session, admin)
        invoice_id = invoice.id
        assert invoice.total_amount == Decimal("10.00")

        listed = await main.list_invoices(
            q="HANDLER-INVOICE",
            airline_id=airline.id,
            provider_id=provider.id,
            billing_month=date(2026, 9, 25),
            status="draft",
            page=1,
            page_size=10,
            db=session,
            _=admin,
        )
        assert listed["total"] == 1
        assert listed["items"][0].id == invoice_id
        assert (await main.get_invoice(invoice_id, session, admin)).id == invoice_id

        updated = await main.put_invoice(
            invoice_id,
            invoice_data.model_copy(update={"quantity": Decimal("8")}),
            session,
            admin,
        )
        assert updated.total_amount == Decimal("20.00")
        exported = await main.export_invoices(session, admin)
        csv_data = "".join([chunk async for chunk in exported.body_iterator])
        assert "HANDLER-INVOICE-1" in csv_data
        assert "20.00" in csv_data

        finalized = await main.finalize_invoice(invoice_id, session, admin)
        assert finalized.status == "FINALIZED"
        with pytest.raises(HTTPException) as missing_update:
            await main.put_invoice(999, invoice_data, session, admin)
        assert missing_update.value.status_code == 404
        with pytest.raises(HTTPException) as missing_get:
            await main.get_invoice(999, session, admin)
        assert missing_get.value.status_code == 404
        with pytest.raises(HTTPException) as missing_finalize:
            await main.finalize_invoice(999, session, admin)
        assert missing_finalize.value.status_code == 404

        cancellable = await main.post_invoice(
            invoice_data.model_copy(update={"reference": "HANDLER-INVOICE-2"}), session, admin
        )
        cancelled = await main.cancel_invoice(
            cancellable.id,
            CancelIn(reason="Customer correction"),
            session,
            admin,
        )
        assert cancelled.status == "CANCELLED"
        with pytest.raises(HTTPException) as missing_cancel:
            await main.cancel_invoice(999, CancelIn(reason="Customer correction"), session, admin)
        assert missing_cancel.value.status_code == 404


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("  +1", "'  +1"),
        ("-1", "'-1"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("ordinary text", "ordinary text"),
        (42, 42),
    ],
)
def test_csv_cells_neutralize_formula_prefixes(value, expected):
    assert safe_csv_cell(value) == expected
