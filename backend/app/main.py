import csv
import io
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db import engine, get_db
from backend.app.models import Admin, Airline, FuelRate, Invoice, Provider
from backend.app.schemas import (
    CancelIn,
    EntityIn,
    EntityOut,
    InvoiceIn,
    InvoiceOut,
    LoginIn,
    Profile,
    RateIn,
    RateOut,
)
from backend.app.security import (
    create_csrf_token,
    create_token,
    current_admin,
    verify_password,
)
from backend.app.services import (
    change_invoice_status,
    create_invoice,
    page_meta,
    update_draft_invoice,
)

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("afm")
limiter = Limiter(key_func=get_remote_address)


def safe_csv_cell(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def is_rate_overlap_violation(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    diagnostic = getattr(original, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == "ex_rate_active_period_no_overlap"


@asynccontextmanager
async def lifespan(_app):
    yield
    await engine.dispose()


app = FastAPI(
    title="Airport Fuel Management API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.frontend_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def common_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id", secrets.token_hex(8))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/v1") else "no-cache"
    )
    return response


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(1))
        return {"status": "ready"}
    except Exception as exc:
        log.exception("Readiness check failed")
        raise HTTPException(503, "Database unavailable") from exc


@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login(
    request: Request, data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)
):
    admin = await db.scalar(select(Admin).where(Admin.username == data.username))
    if not admin or not admin.active or not verify_password(data.password, admin.password_hash):
        raise HTTPException(401, "Invalid username or password")
    token = create_token(admin.id)
    csrf = create_csrf_token()
    response.set_cookie(
        "afm_access",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        "afm_csrf",
        csrf,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    return {"id": admin.id, "username": admin.username, "csrf_token": csrf}


@app.post("/api/v1/auth/logout")
async def logout(response: Response, _: Admin = Depends(current_admin)):
    response.delete_cookie("afm_access", path="/")
    response.delete_cookie("afm_csrf", path="/")
    return {"detail": "Logged out"}


@app.get("/api/v1/auth/me", response_model=Profile)
async def me(admin: Admin = Depends(current_admin)):
    return admin


@app.get("/api/v1/config")
async def public_configuration(_: Admin = Depends(current_admin)):
    return {
        "default_currency": settings.default_currency,
        "default_quantity_unit": settings.default_quantity_unit,
    }


@app.get("/api/v1/providers")
@app.get("/api/v1/airlines")
async def list_entities(
    request: Request,
    q: str = "",
    active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    kind = request.url.path.rsplit("/", 1)[-1]
    model = {"providers": Provider, "airlines": Airline}.get(kind)
    if not model:
        raise HTTPException(404, "Not found")
    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    if q:
        condition = or_(
            model.code.ilike(f"%{q}%"), model.name.ilike(f"%{q}%"), model.email.ilike(f"%{q}%")
        )
        stmt, count_stmt = stmt.where(condition), count_stmt.where(condition)
    if active is not None:
        stmt, count_stmt = (
            stmt.where(model.active.is_(active)),
            count_stmt.where(model.active.is_(active)),
        )
    total = await db.scalar(count_stmt)
    items = (
        await db.scalars(stmt.order_by(model.name).offset((page - 1) * page_size).limit(page_size))
    ).all()
    return {
        "items": [EntityOut.model_validate(x) for x in items],
        **page_meta(total, page, page_size),
    }


@app.post("/api/v1/providers", response_model=EntityOut, status_code=201)
@app.post("/api/v1/airlines", response_model=EntityOut, status_code=201)
async def create_entity(
    request: Request,
    data: EntityIn,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    kind = request.url.path.rsplit("/", 1)[-1]
    model = {"providers": Provider, "airlines": Airline}.get(kind)
    if not model:
        raise HTTPException(404, "Not found")
    obj = model(**data.model_dump())
    db.add(obj)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Code already exists") from exc
        raise
    await db.refresh(obj)
    return obj


@app.get("/api/v1/providers/{entity_id}", response_model=EntityOut)
@app.get("/api/v1/airlines/{entity_id}", response_model=EntityOut)
async def get_entity(
    request: Request,
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    kind = request.url.path.split("/")[3]
    model = {"providers": Provider, "airlines": Airline}.get(kind)
    obj = await db.get(model, entity_id) if model else None
    if not obj:
        raise HTTPException(404, "Not found")
    return obj


@app.put("/api/v1/providers/{entity_id}", response_model=EntityOut)
@app.put("/api/v1/airlines/{entity_id}", response_model=EntityOut)
async def update_entity(
    request: Request,
    entity_id: int,
    data: EntityIn,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    kind = request.url.path.split("/")[3]
    model = {"providers": Provider, "airlines": Airline}.get(kind)
    obj = await db.get(model, entity_id) if model else None
    if not obj:
        raise HTTPException(404, "Not found")
    for key, value in data.model_dump().items():
        setattr(obj, key, value)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Code already exists") from exc
        raise
    await db.refresh(obj)
    return obj


@app.delete("/api/v1/providers/{entity_id}", status_code=204)
@app.delete("/api/v1/airlines/{entity_id}", status_code=204)
async def deactivate_entity(
    request: Request,
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    kind = request.url.path.split("/")[3]
    model = {"providers": Provider, "airlines": Airline}.get(kind)
    obj = await db.get(model, entity_id) if model else None
    if not obj:
        raise HTTPException(404, "Not found")
    obj.active = False
    await db.commit()


@app.get("/api/v1/rates")
async def list_rates(
    provider_id: int | None = None,
    fuel_type: str | None = None,
    active: bool | None = None,
    effective_on: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    stmt = select(FuelRate)
    count = select(func.count()).select_from(FuelRate)
    for column, value in (
        (FuelRate.provider_id, provider_id),
        (FuelRate.fuel_type, fuel_type),
        (FuelRate.active, active),
    ):
        if value is not None:
            stmt, count = stmt.where(column == value), count.where(column == value)
    if effective_on:
        period = (FuelRate.effective_from <= effective_on) & or_(
            FuelRate.effective_to.is_(None), FuelRate.effective_to >= effective_on
        )
        stmt, count = stmt.where(period), count.where(period)
    total = await db.scalar(count)
    rows = (
        await db.scalars(
            stmt.order_by(FuelRate.effective_from.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {"items": [RateOut.model_validate(x) for x in rows], **page_meta(total, page, page_size)}


@app.post("/api/v1/rates", response_model=RateOut, status_code=201)
async def create_rate(
    data: RateIn, db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)
):
    provider = await db.get(Provider, data.provider_id)
    if not provider or not provider.active:
        raise HTTPException(422, "Provider is missing or inactive")
    end = data.effective_to or date.max
    clash = await db.scalar(
        select(FuelRate.id)
        .where(
            FuelRate.provider_id == data.provider_id,
            FuelRate.fuel_type == data.fuel_type,
            FuelRate.active.is_(True),
            FuelRate.effective_from <= end,
            or_(FuelRate.effective_to.is_(None), FuelRate.effective_to >= data.effective_from),
        )
        .limit(1)
    )
    if clash and data.active:
        raise HTTPException(409, "Rate effective period overlaps an existing rate")
    row = FuelRate(**data.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if is_rate_overlap_violation(exc):
            raise HTTPException(409, "Rate effective period overlaps an existing rate") from exc
        raise
    await db.refresh(row)
    return row


@app.put("/api/v1/rates/{rate_id}", response_model=RateOut)
async def update_rate(
    rate_id: int,
    data: RateIn,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    row = await db.get(FuelRate, rate_id)
    if not row:
        raise HTTPException(404, "Rate not found")
    if await db.scalar(select(Invoice.id).where(Invoice.rate_id == rate_id).limit(1)):
        raise HTTPException(
            409, "A rate referenced by an invoice is immutable; create a new rate period"
        )
    end = data.effective_to or date.max
    overlap = await db.scalar(
        select(FuelRate.id)
        .where(
            FuelRate.id != rate_id,
            FuelRate.provider_id == data.provider_id,
            FuelRate.fuel_type == data.fuel_type,
            FuelRate.active.is_(True),
            FuelRate.effective_from <= end,
            or_(FuelRate.effective_to.is_(None), FuelRate.effective_to >= data.effective_from),
        )
        .limit(1)
    )
    if overlap and data.active:
        raise HTTPException(409, "Rate effective period overlaps an existing rate")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if is_rate_overlap_violation(exc):
            raise HTTPException(409, "Rate effective period overlaps an existing rate") from exc
        raise
    await db.refresh(row)
    return row


@app.get("/api/v1/rates/{rate_id}", response_model=RateOut)
async def get_rate(
    rate_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)
):
    row = await db.get(FuelRate, rate_id)
    if not row:
        raise HTTPException(404, "Rate not found")
    return row


@app.delete("/api/v1/rates/{rate_id}", status_code=204)
async def deactivate_rate(
    rate_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)
):
    row = await db.get(FuelRate, rate_id)
    if not row:
        raise HTTPException(404, "Rate not found")
    row.active = False
    await db.commit()


@app.get("/api/v1/invoices")
async def list_invoices(
    q: str = "",
    airline_id: int | None = None,
    provider_id: int | None = None,
    billing_month: date | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    stmt, count = select(Invoice), select(func.count()).select_from(Invoice)
    filters = []
    if q:
        filters.append(Invoice.reference.ilike(f"%{q}%"))
    if airline_id:
        filters.append(Invoice.airline_id == airline_id)
    if provider_id:
        filters.append(Invoice.provider_id == provider_id)
    if billing_month:
        filters.append(Invoice.billing_month == billing_month.replace(day=1))
    if status:
        filters.append(Invoice.status == status.upper())
    for condition in filters:
        stmt, count = stmt.where(condition), count.where(condition)
    total = await db.scalar(count)
    rows = (
        await db.scalars(
            stmt.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "items": [InvoiceOut.model_validate(x) for x in rows],
        **page_meta(total, page, page_size),
    }


@app.post("/api/v1/invoices", response_model=InvoiceOut, status_code=201)
async def post_invoice(
    data: InvoiceIn, db: AsyncSession = Depends(get_db), admin: Admin = Depends(current_admin)
):
    return await create_invoice(db, data, admin.id)


@app.put("/api/v1/invoices/{invoice_id}", response_model=InvoiceOut)
async def put_invoice(
    invoice_id: int,
    data: InvoiceIn,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(current_admin),
):
    row = await db.get(Invoice, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    return await update_draft_invoice(db, row, data, admin.id)


@app.get("/api/v1/invoices/export.csv")
async def export_invoices(db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)):
    rows = (await db.scalars(select(Invoice).order_by(Invoice.invoice_date.desc()))).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "reference",
            "airline",
            "provider",
            "billing_month",
            "fuel_type",
            "quantity",
            "rate",
            "currency",
            "subtotal",
            "tax",
            "total",
            "status",
        ]
    )
    for x in rows:
        writer.writerow(
            safe_csv_cell(value)
            for value in [
                x.reference,
                x.airline_name,
                x.provider_name,
                x.billing_month,
                x.fuel_type,
                x.quantity,
                x.rate_per_unit,
                x.currency,
                x.subtotal,
                x.tax_amount,
                x.total_amount,
                x.status,
            ]
        )
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@app.get("/api/v1/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: int, db: AsyncSession = Depends(get_db), _: Admin = Depends(current_admin)
):
    row = await db.get(Invoice, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    return row


@app.post("/api/v1/invoices/{invoice_id}/finalize", response_model=InvoiceOut)
async def finalize_invoice(
    invoice_id: int, db: AsyncSession = Depends(get_db), admin: Admin = Depends(current_admin)
):
    row = await db.get(Invoice, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    return await change_invoice_status(db, row, admin.id, "FINALIZED")


@app.post("/api/v1/invoices/{invoice_id}/cancel", response_model=InvoiceOut)
async def cancel_invoice(
    invoice_id: int,
    data: CancelIn,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(current_admin),
):
    row = await db.get(Invoice, invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found")
    return await change_invoice_status(db, row, admin.id, "CANCELLED", data.reason)


@app.get("/api/v1/dashboard")
async def dashboard(
    months: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(current_admin),
):
    today = date.today()
    month_start = today.replace(day=1)
    first_month_index = today.year * 12 + today.month - 1 - (months - 1)
    first_month = date(first_month_index // 12, first_month_index % 12 + 1, 1)
    active_providers = await db.scalar(
        select(func.count()).select_from(Provider).where(Provider.active.is_(True))
    )
    active_airlines = await db.scalar(
        select(func.count()).select_from(Airline).where(Airline.active.is_(True))
    )
    active_rates = await db.scalar(
        select(func.count()).select_from(FuelRate).where(FuelRate.active.is_(True))
    )
    invoice_count = await db.scalar(select(func.count()).select_from(Invoice))
    mcount = await db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.billing_month == month_start)
    )
    mtotal = (
        await db.execute(
            select(Invoice.currency, func.sum(Invoice.total_amount))
            .where(Invoice.billing_month == month_start, Invoice.status != "CANCELLED")
            .group_by(Invoice.currency)
        )
    ).all()
    monthly = (
        await db.execute(
            select(
                Invoice.billing_month,
                Invoice.currency,
                func.count(),
                func.sum(Invoice.total_amount),
            )
            .where(
                Invoice.status != "CANCELLED",
                Invoice.billing_month >= first_month,
                Invoice.billing_month <= month_start,
            )
            .group_by(Invoice.billing_month, Invoice.currency)
            .order_by(Invoice.billing_month.desc())
        )
    ).all()
    recent = (await db.scalars(select(Invoice).order_by(Invoice.created_at.desc()).limit(8))).all()
    providers = (
        await db.execute(
            select(Invoice.provider_name, Invoice.currency, func.sum(Invoice.total_amount))
            .where(
                Invoice.status != "CANCELLED",
                Invoice.billing_month >= first_month,
                Invoice.billing_month <= month_start,
            )
            .group_by(Invoice.provider_name, Invoice.currency)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(10)
        )
    ).all()
    airlines = (
        await db.execute(
            select(Invoice.airline_name, Invoice.currency, func.sum(Invoice.total_amount))
            .where(
                Invoice.status != "CANCELLED",
                Invoice.billing_month >= first_month,
                Invoice.billing_month <= month_start,
            )
            .group_by(Invoice.airline_name, Invoice.currency)
            .order_by(func.sum(Invoice.total_amount).desc())
            .limit(10)
        )
    ).all()
    return {
        "active_providers": active_providers,
        "active_airlines": active_airlines,
        "active_rates": active_rates,
        "total_invoices": invoice_count,
        "current_month_count": mcount,
        "current_month_amounts": [{"currency": c, "total": str(t or 0)} for c, t in mtotal],
        "monthly_totals": [
            {"month": str(m), "currency": c, "count": n, "total": str(t or 0)}
            for m, c, n, t in monthly
        ],
        "recent_invoices": [InvoiceOut.model_validate(i) for i in recent],
        "provider_totals": [
            {"name": n, "currency": c, "total": str(t or 0)} for n, c, t in providers
        ],
        "airline_totals": [
            {"name": n, "currency": c, "total": str(t or 0)} for n, c, t in airlines
        ],
    }
