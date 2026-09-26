import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models import Admin, Airline, Base, FuelRate, InvoiceAudit, Provider
from backend.app.schemas import InvoiceIn
from backend.app.services import (
    applicable_rate,
    change_invoice_status,
    create_invoice,
    money,
    page_meta,
    update_draft_invoice,
)


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        admin = Admin(username="test-admin", password_hash="test-hash")
        provider = Provider(code="FUEL", name="Test Fuel", active=True)
        airline = Airline(code="AIR", name="Test Air", active=True)
        session.add_all([admin, provider, airline])
        await session.flush()
        session.add(
            FuelRate(
                provider_id=provider.id,
                fuel_type="JET A-1",
                rate_per_unit=Decimal("1.23500"),
                currency="USD",
                effective_from=date(2026, 1, 1),
                active=True,
            )
        )
        await session.commit()
        yield session, admin, provider, airline
    await engine.dispose()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.005"), Decimal("1.01")),
        (Decimal("4.994"), Decimal("4.99")),
        (Decimal("0"), Decimal("0.00")),
    ],
)
def test_financial_rounding(value, expected):
    assert money(value) == expected


@pytest.mark.asyncio
async def test_duplicate_invoice_reference_rejected():
    from backend.app.services import create_invoice

    class FakeDB:
        async def scalar(self, _query):
            return 1

    with pytest.raises(HTTPException) as err:
        await create_invoice(FakeDB(), type("Data", (), {"reference": "INV-1"})(), 1)
    assert err.value.status_code == 409


def test_month_date_normalization():
    assert date(2026, 2, 28).replace(day=1) == date(2026, 2, 1)


@pytest.mark.asyncio
async def test_rate_resolution_and_invoice_decimal_snapshot(database):
    db, admin, provider, airline = database
    rate = await applicable_rate(db, provider.id, "JET A-1", date(2026, 2, 1))
    assert rate.rate_per_unit == Decimal("1.23500")
    data = InvoiceIn(
        reference="TEST-001",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 19),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("10"),
        tax_amount=Decimal("0.50"),
    )
    invoice = await create_invoice(db, data, admin.id)
    assert invoice.subtotal == Decimal("12.35")
    assert invoice.total_amount == Decimal("12.85")
    assert invoice.billing_month == date(2026, 2, 1)
    assert invoice.rate_id == rate.id
    assert invoice.provider_name == "Test Fuel"
    rate.rate_per_unit = Decimal("9.99000")
    await db.commit()
    await db.refresh(invoice)
    assert invoice.rate_per_unit == Decimal("1.23500")


@pytest.mark.asyncio
async def test_missing_or_ambiguous_rate_rejected(database):
    db, _, provider, _ = database
    with pytest.raises(HTTPException) as err:
        await applicable_rate(db, provider.id, "AVGAS", date(2026, 2, 1))
    assert err.value.status_code == 422
    db.add(
        FuelRate(
            provider_id=provider.id,
            fuel_type="JET A-1",
            rate_per_unit=Decimal("1.5"),
            currency="USD",
            effective_from=date(2026, 2, 1),
            active=True,
        )
    )
    await db.commit()
    with pytest.raises(HTTPException):
        await applicable_rate(db, provider.id, "JET A-1", date(2026, 2, 1))


@pytest.mark.asyncio
async def test_invoice_reference_unique_and_terminal_lifecycle(database):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="LIFE-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("2"),
    )
    invoice = await create_invoice(db, data, admin.id)
    with pytest.raises(HTTPException) as duplicate:
        await create_invoice(db, data, admin.id)
    assert duplicate.value.status_code == 409
    final = await change_invoice_status(db, invoice, admin.id, "FINALIZED")
    assert final.status == "FINALIZED"
    with pytest.raises(HTTPException) as terminal:
        await change_invoice_status(db, final, admin.id, "CANCELLED", "mistake")
    assert terminal.value.status_code == 409


@pytest.mark.asyncio
async def test_database_rejects_unknown_invoice_status(database):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="INVALID-STATUS",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )
    invoice = await create_invoice(db, data, admin.id)
    invoice.status = "PAID"
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_draft_edit_recalculates_and_cancellation_records_reason(database):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="EDIT-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("2"),
    )
    invoice = await create_invoice(db, data, admin.id)
    revised = data.model_copy(update={"reference": "EDIT-2", "quantity": Decimal("4")})
    updated = await update_draft_invoice(db, invoice, revised, admin.id)
    assert updated.reference == "EDIT-2"
    assert updated.total_amount == Decimal("4.94")
    cancelled = await change_invoice_status(
        db, updated, admin.id, "CANCELLED", "Duplicate service entry"
    )
    assert cancelled.cancel_reason == "Duplicate service entry"
    assert cancelled.status == "CANCELLED"
    events = (
        await db.scalars(select(InvoiceAudit).where(InvoiceAudit.invoice_id == invoice.id))
    ).all()
    assert [event.event for event in events] == ["CREATED", "UPDATED", "CANCELLED"]
    snapshot = json.loads(events[1].details)
    assert snapshot["before"]["quantity"] == "2.000"
    assert Decimal(snapshot["after"]["quantity"]) == Decimal("4")
    assert snapshot["before"]["total_amount"] == "2.47"
    assert snapshot["after"]["total_amount"] == "4.94"


@pytest.mark.asyncio
async def test_inactive_airline_cannot_be_invoiced(database):
    db, admin, provider, airline = database
    airline.active = False
    await db.commit()
    data = InvoiceIn(
        reference="INACTIVE-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )
    with pytest.raises(HTTPException) as err:
        await create_invoice(db, data, admin.id)
    assert err.value.status_code == 422


@pytest.mark.asyncio
async def test_inactive_provider_cannot_be_invoiced(database):
    db, admin, provider, airline = database
    provider.active = False
    await db.commit()
    data = InvoiceIn(
        reference="INACTIVE-PROVIDER-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )
    with pytest.raises(HTTPException) as err:
        await create_invoice(db, data, admin.id)
    assert err.value.status_code == 422


@pytest.mark.asyncio
async def test_draft_edit_rejects_duplicate_reference(database):
    db, admin, provider, airline = database

    def payload(reference):
        return InvoiceIn(
            reference=reference,
            airline_id=airline.id,
            provider_id=provider.id,
            billing_month=date(2026, 2, 1),
            invoice_date=date(2026, 2, 1),
            fuel_type="JET A-1",
            quantity=Decimal("1"),
        )

    original = await create_invoice(db, payload("ORIGINAL"), admin.id)
    await create_invoice(db, payload("ALREADY-USED"), admin.id)
    with pytest.raises(HTTPException) as err:
        await update_draft_invoice(db, original, payload("ALREADY-USED"), admin.id)
    assert err.value.status_code == 409


@pytest.mark.asyncio
async def test_edit_rejects_inactive_related_records(database):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="EDIT-INACTIVE",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )
    invoice = await create_invoice(db, data, admin.id)
    provider.active = False
    await db.commit()
    with pytest.raises(HTTPException) as provider_error:
        await update_draft_invoice(db, invoice, data, admin.id)
    assert provider_error.value.status_code == 422


@pytest.mark.asyncio
async def test_unique_reference_race_is_translated_to_conflict(database, monkeypatch):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="RACE-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )

    async def fail_commit():
        raise IntegrityError("insert", {}, RuntimeError("unique violation"))

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as err:
        await create_invoice(db, data, admin.id)
    assert err.value.status_code == 409


@pytest.mark.asyncio
async def test_draft_edit_integrity_failure_rolls_back(database, monkeypatch):
    db, admin, provider, airline = database
    data = InvoiceIn(
        reference="EDIT-RACE-1",
        airline_id=airline.id,
        provider_id=provider.id,
        billing_month=date(2026, 2, 1),
        invoice_date=date(2026, 2, 1),
        fuel_type="JET A-1",
        quantity=Decimal("1"),
    )
    invoice = await create_invoice(db, data, admin.id)

    async def fail_commit():
        raise IntegrityError("update", {}, RuntimeError("unique violation"))

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(HTTPException) as err:
        await update_draft_invoice(db, invoice, data, admin.id)
    assert err.value.status_code == 409


def test_pagination_calculation():
    assert page_meta(41, 2, 20) == {"total": 41, "page": 2, "page_size": 20, "pages": 3}
