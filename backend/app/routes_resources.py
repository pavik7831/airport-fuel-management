from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .auth import get_current_user
from .database import get_db
from .models import AdminUser, Airline, FuelProvider, FuelRate, Invoice
from .schemas import (AirlineCreate, AirlineResponse, AirlineUpdate, DashboardResponse, FuelRateCreate,
                      FuelRateResponse, FuelRateUpdate, InvoiceCreate, InvoiceResponse, InvoiceUpdate,
                      ProviderCreate, ProviderResponse, ProviderUpdate)

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

def save(db: Session, item):
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A record with those unique values already exists") from exc


def get_or_404(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    if not item: raise HTTPException(status_code=404, detail="Record not found")
    return item


def invoice_query(db: Session):
    return db.query(Invoice).options(joinedload(Invoice.provider), joinedload(Invoice.airline))


@router.get("/providers", response_model=list[ProviderResponse])
def providers(db: Session = Depends(get_db), search: str = ""):
    query = db.query(FuelProvider)
    if search: query = query.filter(or_(FuelProvider.code.ilike(f"%{search}%"), FuelProvider.name.ilike(f"%{search}%")))
    return query.order_by(FuelProvider.name).all()

@router.post("/providers", response_model=ProviderResponse, status_code=201)
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)): return save(db, FuelProvider(**payload.model_dump()))

@router.put("/providers/{item_id}", response_model=ProviderResponse)
def update_provider(item_id: int, payload: ProviderUpdate, db: Session = Depends(get_db)):
    item = get_or_404(db, FuelProvider, item_id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    return save(db, item)


@router.get("/airlines", response_model=list[AirlineResponse])
def airlines(db: Session = Depends(get_db), search: str = ""):
    query = db.query(Airline)
    if search: query = query.filter(or_(Airline.code.ilike(f"%{search}%"), Airline.name.ilike(f"%{search}%")))
    return query.order_by(Airline.name).all()

@router.post("/airlines", response_model=AirlineResponse, status_code=201)
def create_airline(payload: AirlineCreate, db: Session = Depends(get_db)): return save(db, Airline(**payload.model_dump()))

@router.put("/airlines/{item_id}", response_model=AirlineResponse)
def update_airline(item_id: int, payload: AirlineUpdate, db: Session = Depends(get_db)):
    item = get_or_404(db, Airline, item_id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    return save(db, item)


@router.get("/rates", response_model=list[FuelRateResponse])
def rates(db: Session = Depends(get_db)): return db.query(FuelRate).order_by(FuelRate.effective_date.desc()).all()

@router.post("/rates", response_model=FuelRateResponse, status_code=201)
def create_rate(payload: FuelRateCreate, db: Session = Depends(get_db)): return save(db, FuelRate(**payload.model_dump()))

@router.put("/rates/{item_id}", response_model=FuelRateResponse)
def update_rate(item_id: int, payload: FuelRateUpdate, db: Session = Depends(get_db)):
    item = get_or_404(db, FuelRate, item_id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    return save(db, item)


@router.get("/invoices", response_model=list[InvoiceResponse])
def invoices(db: Session = Depends(get_db), search: str = "", month: date | None = Query(default=None)):
    query = invoice_query(db)
    if month: query = query.filter(Invoice.billing_month == month)
    if search: query = query.join(FuelProvider).join(Airline).filter(or_(Invoice.reference_number.ilike(f"%{search}%"), FuelProvider.name.ilike(f"%{search}%"), Airline.name.ilike(f"%{search}%")))
    return query.order_by(Invoice.billing_month.desc(), Invoice.created_at.desc()).all()

@router.get("/invoices/{item_id}", response_model=InvoiceResponse)
def invoice(item_id: int, db: Session = Depends(get_db)): return invoice_query(db).filter(Invoice.id == item_id).first() or (_ for _ in ()).throw(HTTPException(404, "Invoice not found"))


def build_invoice(db: Session, payload, existing=None):
    provider = get_or_404(db, FuelProvider, payload.provider_id)
    airline = get_or_404(db, Airline, payload.airline_id)
    rate = get_or_404(db, FuelRate, payload.fuel_rate_id)
    if not provider.is_active or not airline.is_active: raise HTTPException(400, detail="Provider and airline must be active")
    billing_month = payload.billing_month.replace(day=1)
    duplicate = db.query(Invoice).filter(Invoice.provider_id == provider.id, Invoice.airline_id == airline.id, Invoice.billing_month == billing_month)
    if existing: duplicate = duplicate.filter(Invoice.id != existing.id)
    if duplicate.first(): raise HTTPException(409, detail="An invoice already exists for this provider, airline, and billing month")
    values = {"provider_id": provider.id, "airline_id": airline.id, "fuel_rate_id": rate.id, "billing_month": billing_month, "fuel_quantity": payload.fuel_quantity, "fuel_rate": rate.rate, "total_amount": (payload.fuel_quantity * rate.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}
    if existing: values.pop("billing_month"); values.pop("provider_id"); values.pop("airline_id"); existing.__dict__.update(values); return existing
    values["reference_number"] = f"AFM-{billing_month:%Y%m}-{provider.code}-{airline.code}-{date.today():%d%H%M%S}"
    return Invoice(**values)

@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)): return save(db, build_invoice(db, payload))

@router.put("/invoices/{item_id}", response_model=InvoiceResponse)
def update_invoice(item_id: int, payload: InvoiceUpdate, db: Session = Depends(get_db)):
    item = get_or_404(db, Invoice, item_id)
    return save(db, build_invoice(db, payload, item))

@router.delete("/invoices/{item_id}", status_code=204)
def delete_invoice(item_id: int, db: Session = Depends(get_db)):
    item = get_or_404(db, Invoice, item_id); db.delete(item); db.commit()


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db)):
    recent = invoice_query(db).order_by(Invoice.created_at.desc()).limit(5).all()
    total = db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar() or 0
    return DashboardResponse(total_providers=db.query(FuelProvider).count(), total_airlines=db.query(Airline).count(), total_rates=db.query(FuelRate).count(), total_invoices=db.query(Invoice).count(), total_invoice_amount=total, recent_invoices=recent)
