from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceGenerate(BaseModel):
    fuel_provider_id: int
    airline_id: int
    fuel_rate_id: int
    billing_month: date
    fuel_quantity_litres: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    fuel_provider_id: int
    airline_id: int
    fuel_rate_id: int
    billing_month: date
    fuel_quantity_litres: Decimal
    rate_per_litre: Decimal
    currency: str
    total_amount: Decimal
    status: str
    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    fuel_providers: int
    airlines: int
    fuel_rates: int
    invoices: int
    total_invoiced_amount: Decimal
