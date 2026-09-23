from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DbSession, get_current_admin
from app.models.airline import Airline
from app.models.fuel_provider import FuelProvider
from app.models.fuel_rate import FuelRate
from app.models.invoice import Invoice
from app.schemas.invoice import DashboardSummary, InvoiceGenerate, InvoiceResponse

router = APIRouter(tags=["Invoices"], dependencies=[Depends(get_current_admin)])


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(db: DbSession):
    return db.scalars(select(Invoice).order_by(Invoice.billing_month.desc(), Invoice.id.desc())).all()


@router.post("/invoices/generate", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def generate_invoice(payload: InvoiceGenerate, db: DbSession):
    provider = db.get(FuelProvider, payload.fuel_provider_id)
    airline = db.get(Airline, payload.airline_id)
    rate = db.get(FuelRate, payload.fuel_rate_id)
    if not provider or not airline or not rate:
        raise HTTPException(status_code=400, detail="Provider, airline, or fuel rate was not found")
    billing_month = payload.billing_month.replace(day=1)
    duplicate = db.scalar(select(Invoice).where(
        Invoice.fuel_provider_id == provider.id, Invoice.airline_id == airline.id, Invoice.billing_month == billing_month
    ))
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice already exists for this airline, provider, and month")
    total = (payload.fuel_quantity_litres * rate.rate_per_litre).quantize(Decimal("0.01"))
    invoice = Invoice(
        invoice_number=f"INV-{billing_month:%Y%m}-{provider.code}-{airline.code}",
        fuel_provider_id=provider.id, airline_id=airline.id, fuel_rate_id=rate.id,
        billing_month=billing_month, fuel_quantity_litres=payload.fuel_quantity_litres,
        rate_per_litre=rate.rate_per_litre, currency=rate.currency, total_amount=total,
    )
    db.add(invoice); db.commit(); db.refresh(invoice)
    return invoice


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard_summary(db: DbSession):
    total = db.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0)))
    return DashboardSummary(
        fuel_providers=db.scalar(select(func.count()).select_from(FuelProvider)),
        airlines=db.scalar(select(func.count()).select_from(Airline)),
        fuel_rates=db.scalar(select(func.count()).select_from(FuelRate)),
        invoices=db.scalar(select(func.count()).select_from(Invoice)),
        total_invoiced_amount=total,
    )
