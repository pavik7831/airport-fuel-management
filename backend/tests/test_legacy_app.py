import os
import sys
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "legacy-test-secret-value-with-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_db  # noqa: E402
from app.app import app  # noqa: E402
from app.auth import get_password_hash  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture
async def legacy_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                User(
                    email="legacy-admin@example.com",
                    password_hash=hash_password("legacy-admin-password"),
                    is_admin=True,
                ),
                User(
                    email="legacy-user@example.com",
                    password_hash=hash_password("legacy-user-password"),
                    is_admin=False,
                ),
            ]
        )
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.session_factory = factory
            client.test_engine = engine
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_legacy_app_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_legacy_auth_compatibility_routes(legacy_client):
    invalid = await legacy_client.post(
        "/api/auth/login",
        json={"email": "legacy-admin@example.com", "password": "incorrect"},
    )
    assert invalid.status_code == 401
    non_admin = await legacy_client.post(
        "/api/auth/login",
        json={"email": "legacy-user@example.com", "password": "legacy-user-password"},
    )
    assert non_admin.status_code == 401

    login = await legacy_client.post(
        "/api/auth/login",
        json={"email": "legacy-admin@example.com", "password": "legacy-admin-password"},
    )
    assert login.status_code == 200
    assert login.json()["user_email"] == "legacy-admin@example.com"
    assert get_password_hash("legacy-password-wrapper-test").startswith("$argon2id$")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = await legacy_client.get("/api/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json() == {"email": "legacy-admin@example.com"}
    invalid_token = await legacy_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert invalid_token.status_code == 401

    missing_subject = jwt.encode({}, get_settings().secret_key, algorithm="HS256")
    missing_subject_response = await legacy_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {missing_subject}"}
    )
    assert missing_subject_response.status_code == 401


@pytest.mark.asyncio
async def test_legacy_authenticated_master_data_rate_invoice_journey(legacy_client):
    invalid = await legacy_client.post(
        "/api/v1/auth/login",
        json={"email": "legacy-admin@example.com", "password": "incorrect"},
    )
    assert invalid.status_code == 401
    non_admin = await legacy_client.post(
        "/api/v1/auth/login",
        json={"email": "legacy-user@example.com", "password": "legacy-user-password"},
    )
    assert non_admin.status_code == 403

    login = await legacy_client.post(
        "/api/v1/auth/login",
        json={"email": "legacy-admin@example.com", "password": "legacy-admin-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        await legacy_client.get(
            "/api/v1/fuel-rates", headers={"Authorization": "Bearer invalid-token"}
        )
    ).status_code == 401
    regular_token = create_access_token("legacy-user@example.com")
    assert (
        await legacy_client.get(
            "/api/v1/fuel-rates", headers={"Authorization": f"Bearer {regular_token}"}
        )
    ).status_code == 401
    profile = await legacy_client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "legacy-admin@example.com"

    provider_data = {"code": "FUEL", "name": "Legacy Fuel"}
    provider = await legacy_client.post(
        "/api/v1/fuel-providers", json=provider_data, headers=headers
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    listed_providers = await legacy_client.get("/api/v1/fuel-providers", headers=headers)
    assert listed_providers.json()[0]["id"] == provider_id
    duplicate_provider = await legacy_client.post(
        "/api/v1/fuel-providers", json=provider_data, headers=headers
    )
    assert duplicate_provider.status_code == 409
    assert (
        await legacy_client.put("/api/v1/fuel-providers/999", json=provider_data, headers=headers)
    ).status_code == 404
    assert (
        await legacy_client.put(
            f"/api/v1/fuel-providers/{provider_id}",
            json={"code": "FUEL", "name": "Updated Fuel"},
            headers=headers,
        )
    ).json()["name"] == "Updated Fuel"

    airline_data = {"code": "AIR", "name": "Legacy Air"}
    airline = await legacy_client.post("/api/v1/airlines", json=airline_data, headers=headers)
    assert airline.status_code == 201
    airline_id = airline.json()["id"]
    assert (await legacy_client.get("/api/v1/airlines", headers=headers)).json()[0][
        "id"
    ] == airline_id
    assert (
        await legacy_client.put(
            f"/api/v1/airlines/{airline_id}",
            json={"code": "AIR2", "name": "Updated Air"},
            headers=headers,
        )
    ).json()["code"] == "AIR2"
    second_airline = await legacy_client.post(
        "/api/v1/airlines", json={"code": "AIR3", "name": "Second Air"}, headers=headers
    )
    assert second_airline.status_code == 201
    assert (
        await legacy_client.put(
            f"/api/v1/airlines/{second_airline.json()['id']}",
            json={"code": "AIR2", "name": "Duplicate Air"},
            headers=headers,
        )
    ).status_code == 409

    rate_data = {
        "fuel_type": "JET A-1",
        "rate_per_litre": "2.50",
        "currency": "USD",
        "effective_from": "2026-01-01",
    }
    rate = await legacy_client.post("/api/v1/fuel-rates", json=rate_data, headers=headers)
    assert rate.status_code == 201
    rate_id = rate.json()["id"]
    assert (await legacy_client.get("/api/v1/fuel-rates", headers=headers)).json()[0][
        "id"
    ] == rate_id
    assert (
        await legacy_client.put(
            f"/api/v1/fuel-rates/{rate_id}",
            json={**rate_data, "rate_per_litre": "3.00"},
            headers=headers,
        )
    ).json()["rate_per_litre"] == "3.00"
    assert (
        await legacy_client.put("/api/v1/fuel-rates/999", json=rate_data, headers=headers)
    ).status_code == 404

    invoice_data = {
        "fuel_provider_id": provider_id,
        "airline_id": airline_id,
        "fuel_rate_id": rate_id,
        "billing_month": "2026-09-19",
        "fuel_quantity_litres": "10.00",
    }
    missing_records = await legacy_client.post(
        "/api/v1/invoices/generate",
        json={**invoice_data, "fuel_provider_id": 999, "airline_id": 999, "fuel_rate_id": 999},
        headers=headers,
    )
    assert missing_records.status_code == 400
    invoice = await legacy_client.post(
        "/api/v1/invoices/generate", json=invoice_data, headers=headers
    )
    assert invoice.status_code == 201
    assert invoice.json()["billing_month"] == "2026-09-01"
    assert invoice.json()["total_amount"] == "30.00"
    duplicate_invoice = await legacy_client.post(
        "/api/v1/invoices/generate", json=invoice_data, headers=headers
    )
    assert duplicate_invoice.status_code == 409
    assert (await legacy_client.get("/api/v1/invoices", headers=headers)).json()[0][
        "id"
    ] == invoice.json()["id"]
    dashboard = (await legacy_client.get("/api/v1/dashboard", headers=headers)).json()
    assert dashboard["fuel_providers"] == 1
    assert dashboard["airlines"] == 2
    assert dashboard["fuel_rates"] == 1
    assert dashboard["invoices"] == 1
    assert dashboard["total_invoiced_amount"] == "30.00"


@pytest.mark.asyncio
async def test_legacy_lifespan_bootstraps_admin_once(legacy_client, monkeypatch):
    import app.app as legacy_app_module

    monkeypatch.setattr(legacy_app_module, "SessionLocal", legacy_client.session_factory)
    monkeypatch.setattr(legacy_app_module, "engine", legacy_client.test_engine)
    legacy_app_module.create_initial_admin()
    legacy_app_module.create_initial_admin()

    with legacy_client.session_factory() as session:
        admin = session.query(User).filter(User.email == "admin@airportfuel.com").all()
        assert len(admin) == 1

    async with legacy_app_module.app.router.lifespan_context(legacy_app_module.app):
        pass

    with legacy_client.session_factory() as session:
        admin = session.query(User).filter(User.email == "admin@airportfuel.com").all()
        assert len(admin) == 1


@pytest.mark.asyncio
async def test_legacy_resources_router_crud_and_invoice_lifecycle(legacy_client):
    login = await legacy_client.post(
        "/api/v1/auth/login",
        json={"email": "legacy-admin@example.com", "password": "legacy-admin-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    invalid_token = await legacy_client.get(
        "/api/providers", headers={"Authorization": "Bearer invalid-token"}
    )
    assert invalid_token.status_code == 401
    non_admin_token = create_access_token("legacy-user@example.com")
    non_admin = await legacy_client.get(
        "/api/providers", headers={"Authorization": f"Bearer {non_admin_token}"}
    )
    assert non_admin.status_code == 401

    provider_data = {"code": "RESFUEL", "name": "Resource Fuel"}
    provider = await legacy_client.post("/api/providers", json=provider_data, headers=headers)
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    assert (await legacy_client.get("/api/providers?search=Resource", headers=headers)).json()[0][
        "id"
    ] == provider_id
    assert (
        await legacy_client.post("/api/providers", json=provider_data, headers=headers)
    ).status_code == 409
    assert (
        await legacy_client.put(
            f"/api/providers/{provider_id}",
            json={"code": "RESFUEL", "name": "Updated Resource Fuel"},
            headers=headers,
        )
    ).json()["name"] == "Updated Resource Fuel"
    assert (
        await legacy_client.put("/api/providers/999", json=provider_data, headers=headers)
    ).status_code == 404

    airline_data = {"code": "RESAIR", "name": "Resource Air"}
    airline = await legacy_client.post("/api/airlines", json=airline_data, headers=headers)
    assert airline.status_code == 201
    airline_id = airline.json()["id"]
    assert (await legacy_client.get("/api/airlines?search=Resource", headers=headers)).json()[0][
        "id"
    ] == airline_id
    assert (
        await legacy_client.put(
            f"/api/airlines/{airline_id}",
            json={"code": "RESAIR2", "name": "Updated Resource Air"},
            headers=headers,
        )
    ).json()["code"] == "RESAIR2"

    rate_data = {
        "fuel_type": "JET A-1",
        "rate_per_litre": "3.25",
        "currency": "USD",
        "effective_from": "2026-01-01",
    }
    rate = await legacy_client.post("/api/rates", json=rate_data, headers=headers)
    assert rate.status_code == 201
    rate_id = rate.json()["id"]
    assert (await legacy_client.get("/api/rates", headers=headers)).json()[0]["id"] == rate_id
    assert (
        await legacy_client.put(
            f"/api/rates/{rate_id}",
            json={**rate_data, "rate_per_litre": "4.00"},
            headers=headers,
        )
    ).json()["rate_per_litre"] == "4.00"
    assert (
        await legacy_client.put("/api/rates/999", json=rate_data, headers=headers)
    ).status_code == 404

    invoice_data = {
        "fuel_provider_id": provider_id,
        "airline_id": airline_id,
        "fuel_rate_id": rate_id,
        "billing_month": "2026-09-18",
        "fuel_quantity_litres": "3.00",
    }
    from app.models.fuel_provider import FuelProvider

    with legacy_client.session_factory() as session:
        provider_record = session.get(FuelProvider, provider_id)
        provider_record.is_active = False
        session.commit()
    inactive_invoice = await legacy_client.post("/api/invoices", json=invoice_data, headers=headers)
    assert inactive_invoice.status_code == 400
    with legacy_client.session_factory() as session:
        provider_record = session.get(FuelProvider, provider_id)
        provider_record.is_active = True
        session.commit()

    invoice = await legacy_client.post("/api/invoices", json=invoice_data, headers=headers)
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    assert invoice.json()["total_amount"] == "12.00"
    assert (
        await legacy_client.get("/api/invoices?search=RESFUEL&month=2026-09-01", headers=headers)
    ).json()[0]["id"] == invoice_id
    assert (
        await legacy_client.get(f"/api/invoices/{invoice_id}", headers=headers)
    ).status_code == 200
    duplicate = await legacy_client.post("/api/invoices", json=invoice_data, headers=headers)
    assert duplicate.status_code == 409
    revised = await legacy_client.put(
        f"/api/invoices/{invoice_id}",
        json={**invoice_data, "fuel_quantity_litres": "4.00"},
        headers=headers,
    )
    assert revised.status_code == 200
    assert revised.json()["total_amount"] == "16.00"
    assert (await legacy_client.get("/api/dashboard", headers=headers)).json()[
        "total_invoices"
    ] == 1
    assert (
        await legacy_client.delete(f"/api/invoices/{invoice_id}", headers=headers)
    ).status_code == 204
    assert (await legacy_client.get("/api/invoices/999", headers=headers)).status_code == 404


def test_legacy_sync_session_dependency_closes_session(monkeypatch):
    import app.db.session as legacy_session

    closed = []
    session = type("Session", (), {"close": lambda self: closed.append(True)})()
    monkeypatch.setattr(legacy_session, "SessionLocal", lambda: session)
    dependency = legacy_session.get_db()

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)
    assert closed == [True]
