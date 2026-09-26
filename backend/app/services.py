import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Airline, FuelRate, Invoice, InvoiceAudit, Provider

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


async def applicable_rate(
    db: AsyncSession, provider_id: int, fuel_type: str, when: date
) -> FuelRate:
    result = await db.execute(
        select(FuelRate)
        .where(
            FuelRate.provider_id == provider_id,
            FuelRate.fuel_type == fuel_type,
            FuelRate.active.is_(True),
            FuelRate.effective_from <= when,
            or_(FuelRate.effective_to.is_(None), FuelRate.effective_to >= when),
        )
        .order_by(FuelRate.effective_from.desc())
    )
    rates = result.scalars().all()
    if len(rates) != 1:
        raise HTTPException(
            422, "No unique active rate applies for provider, fuel type and invoice date"
        )
    return rates[0]


async def create_invoice(db: AsyncSession, data, admin_id: int) -> Invoice:
    exists = await db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.reference == data.reference)
    )
    if exists:
        raise HTTPException(409, "Invoice reference already exists")
    airline, provider = (
        await db.get(Airline, data.airline_id),
        await db.get(Provider, data.provider_id),
    )
    if not airline or not airline.active:
        raise HTTPException(422, "Selected airline is missing or inactive")
    if not provider or not provider.active:
        raise HTTPException(422, "Selected provider is missing or inactive")
    rate = await applicable_rate(db, provider.id, data.fuel_type, data.invoice_date)
    subtotal = money(data.quantity * rate.rate_per_unit)
    tax = money(data.tax_amount)
    invoice = Invoice(
        reference=data.reference,
        airline_id=airline.id,
        provider_id=provider.id,
        rate_id=rate.id,
        airline_code=airline.code,
        airline_name=airline.name,
        provider_code=provider.code,
        provider_name=provider.name,
        billing_month=data.billing_month.replace(day=1),
        invoice_date=data.invoice_date,
        fuel_type=data.fuel_type,
        quantity=data.quantity,
        rate_per_unit=rate.rate_per_unit,
        currency=rate.currency,
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=money(subtotal + tax),
        notes=data.notes,
        status="DRAFT",
    )
    db.add(invoice)
    await db.flush()
    db.add(
        InvoiceAudit(
            invoice_id=invoice.id,
            admin_id=admin_id,
            event="CREATED",
            details="Invoice created as draft",
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Invoice reference already exists") from exc
    await db.refresh(invoice)
    return invoice


async def update_draft_invoice(db: AsyncSession, invoice: Invoice, data, admin_id: int) -> Invoice:
    if invoice.status != "DRAFT":
        raise HTTPException(409, "Only draft invoices can be edited")
    duplicate = await db.scalar(
        select(Invoice.id)
        .where(Invoice.reference == data.reference, Invoice.id != invoice.id)
        .limit(1)
    )
    if duplicate:
        raise HTTPException(409, "Invoice reference already exists")
    airline, provider = (
        await db.get(Airline, data.airline_id),
        await db.get(Provider, data.provider_id),
    )
    if not airline or not airline.active:
        raise HTTPException(422, "Selected airline is missing or inactive")
    if not provider or not provider.active:
        raise HTTPException(422, "Selected provider is missing or inactive")
    rate = await applicable_rate(db, provider.id, data.fuel_type, data.invoice_date)
    subtotal = money(data.quantity * rate.rate_per_unit)
    changes = {
        "reference": data.reference,
        "airline_id": airline.id,
        "provider_id": provider.id,
        "rate_id": rate.id,
        "airline_code": airline.code,
        "airline_name": airline.name,
        "provider_code": provider.code,
        "provider_name": provider.name,
        "billing_month": data.billing_month.replace(day=1),
        "invoice_date": data.invoice_date,
        "fuel_type": data.fuel_type,
        "quantity": data.quantity,
        "rate_per_unit": rate.rate_per_unit,
        "currency": rate.currency,
        "subtotal": subtotal,
        "tax_amount": money(data.tax_amount),
        "total_amount": money(subtotal + data.tax_amount),
        "notes": data.notes,
    }
    financial_fields = (
        "reference",
        "airline_id",
        "provider_id",
        "rate_id",
        "airline_code",
        "airline_name",
        "provider_code",
        "provider_name",
        "billing_month",
        "invoice_date",
        "fuel_type",
        "quantity",
        "rate_per_unit",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
        "notes",
    )
    before = {key: getattr(invoice, key) for key in financial_fields}
    for key, value in changes.items():
        setattr(invoice, key, value)
    db.add(
        InvoiceAudit(
            invoice_id=invoice.id,
            admin_id=admin_id,
            event="UPDATED",
            details=json.dumps(
                {
                    "before": before,
                    "after": {key: getattr(invoice, key) for key in financial_fields},
                },
                default=str,
                sort_keys=True,
            ),
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Invoice reference already exists") from exc
    await db.refresh(invoice)
    return invoice


async def change_invoice_status(
    db: AsyncSession, invoice: Invoice, admin_id: int, status: str, reason: str | None = None
):
    if invoice.status != "DRAFT":
        raise HTTPException(409, "Only draft invoices can be finalized or cancelled")
    invoice.status = status
    invoice.cancel_reason = reason
    db.add(InvoiceAudit(invoice_id=invoice.id, admin_id=admin_id, event=status, details=reason))
    await db.commit()
    await db.refresh(invoice)
    return invoice


def page_meta(total: int, page: int, size: int) -> dict:
    return {"total": total, "page": page, "page_size": size, "pages": (total + size - 1) // size}
