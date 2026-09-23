from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("fuel_provider_id", "airline_id", "billing_month", name="uq_invoice_monthly_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    fuel_provider_id: Mapped[int] = mapped_column(ForeignKey("fuel_providers.id"))
    airline_id: Mapped[int] = mapped_column(ForeignKey("airlines.id"))
    fuel_rate_id: Mapped[int] = mapped_column(ForeignKey("fuel_rates.id"))
    billing_month: Mapped[date] = mapped_column(Date)
    fuel_quantity_litres: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rate_per_litre: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(20), default="Generated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
