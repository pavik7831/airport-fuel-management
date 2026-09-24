from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_email: EmailStr


class ProviderBase(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class ProviderCreate(ProviderBase): pass
class ProviderUpdate(ProviderBase): pass
class ProviderResponse(ProviderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class AirlineBase(ProviderBase): pass
class AirlineCreate(AirlineBase): pass
class AirlineUpdate(AirlineBase): pass
class AirlineResponse(AirlineBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class FuelRateBase(BaseModel):
    fuel_type: str = Field(min_length=2, max_length=100)
    rate: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    effective_date: date


class FuelRateCreate(FuelRateBase): pass
class FuelRateUpdate(FuelRateBase): pass
class FuelRateResponse(FuelRateBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class InvoiceBase(BaseModel):
    provider_id: int
    airline_id: int
    fuel_rate_id: int
    billing_month: date
    fuel_quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class InvoiceCreate(InvoiceBase): pass
class InvoiceUpdate(InvoiceBase): pass
class InvoiceResponse(InvoiceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference_number: str
    fuel_rate: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    provider: ProviderResponse
    airline: AirlineResponse


class DashboardResponse(BaseModel):
    total_providers: int
    total_airlines: int
    total_rates: int
    total_invoices: int
    total_invoice_amount: Decimal
    recent_invoices: list[InvoiceResponse]


class UserResponse(BaseModel):
    email: EmailStr
