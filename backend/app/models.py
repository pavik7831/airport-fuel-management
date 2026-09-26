from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Admin(Base):
    __tablename__ = "administrators"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EntityMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class Provider(EntityMixin, Base):
    __tablename__ = "providers"


class Airline(EntityMixin, Base):
    __tablename__ = "airlines"


class FuelRate(Base):
    __tablename__ = "fuel_rates"
    __table_args__ = (
        CheckConstraint("rate_per_unit > 0", name="ck_rate_positive"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_rate_dates"
        ),
        Index("ix_rate_lookup", "provider_id", "fuel_type", "effective_from", "effective_to"),
        ExcludeConstraint(
            ("provider_id", "="),
            ("fuel_type", "="),
            (text("daterange(effective_from, effective_to, '[]')"), "&&"),
            where=text("active"),
            using="gist",
            name="ex_rate_active_period_no_overlap",
        ).ddl_if(dialect="postgresql"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    fuel_type: Mapped[str] = mapped_column(String(40))
    rate_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 5))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_quantity_positive"),
        CheckConstraint("rate_per_unit > 0", name="ck_invoice_rate_positive"),
        CheckConstraint("status IN ('DRAFT', 'FINALIZED', 'CANCELLED')", name="ck_invoice_status"),
        CheckConstraint(
            "subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0", name="ck_invoice_amounts"
        ),
        UniqueConstraint("reference", name="uq_invoice_reference"),
        Index("ix_invoice_billing_month", "billing_month"),
        Index("ix_invoice_status_date", "status", "invoice_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40))
    airline_id: Mapped[int] = mapped_column(
        ForeignKey("airlines.id", ondelete="RESTRICT"), index=True
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )
    rate_id: Mapped[int] = mapped_column(ForeignKey("fuel_rates.id", ondelete="RESTRICT"))
    airline_code: Mapped[str] = mapped_column(String(24))
    airline_name: Mapped[str] = mapped_column(String(160))
    provider_code: Mapped[str] = mapped_column(String(24))
    provider_name: Mapped[str] = mapped_column(String(160))
    billing_month: Mapped[date] = mapped_column(Date)
    invoice_date: Mapped[date] = mapped_column(Date)
    fuel_type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    rate_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 5))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
    audit_events: Mapped[list["InvoiceAudit"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceAudit(Base):
    __tablename__ = "invoice_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )
    admin_id: Mapped[int] = mapped_column(ForeignKey("administrators.id", ondelete="RESTRICT"))
    event: Mapped[str] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    invoice: Mapped[Invoice] = relationship(back_populates="audit_events")
