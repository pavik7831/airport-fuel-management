from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FuelProvider(Base):
    __tablename__ = "fuel_providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="provider")


class Airline(Base):
    __tablename__ = "airlines"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="airline")


class FuelRate(Base):
    __tablename__ = "fuel_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    fuel_type: Mapped[str] = mapped_column(String(100))
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="fuel_rate_record")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("provider_id", "airline_id", "billing_month", name="uq_invoice_party_month"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("fuel_providers.id"))
    airline_id: Mapped[int] = mapped_column(ForeignKey("airlines.id"))
    fuel_rate_id: Mapped[int] = mapped_column(ForeignKey("fuel_rates.id"))
    billing_month: Mapped[date] = mapped_column(Date, index=True)
    fuel_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    fuel_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(20), default="issued")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    provider: Mapped[FuelProvider] = relationship(back_populates="invoices")
    airline: Mapped[Airline] = relationship(back_populates="invoices")
    fuel_rate_record: Mapped[FuelRate] = relationship(back_populates="invoices")
