from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class Profile(BaseModel):
    id: int
    username: str


class EntityIn(BaseModel):
    code: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    contact_person: str | None = Field(None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=32, pattern=r"^[+()0-9 .-]*$")
    address: str | None = None
    active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("contact_person", "phone", "address", mode="before")
    @classmethod
    def trim_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


class EntityOut(EntityIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class RateIn(BaseModel):
    provider_id: int
    fuel_type: str = Field(min_length=1, max_length=40)
    rate_per_unit: Decimal = Field(gt=0, max_digits=14, decimal_places=5)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    effective_from: date
    effective_to: date | None = None
    active: bool = True

    @field_validator("fuel_type", mode="before")
    @classmethod
    def normalize_fuel_type(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("effective_to")
    @classmethod
    def end_after_start(cls, value, info):
        start = info.data.get("effective_from")
        if value and start and value < start:
            raise ValueError("effective_to must be on or after effective_from")
        return value

    @field_validator("effective_to", mode="before")
    @classmethod
    def empty_end_to_none(cls, value):
        return None if value == "" else value


class RateOut(RateIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class InvoiceIn(BaseModel):
    reference: str = Field(min_length=1, max_length=40)
    airline_id: int
    provider_id: int
    billing_month: date
    invoice_date: date
    fuel_type: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    notes: str | None = None

    @field_validator("reference", mode="before")
    @classmethod
    def trim_reference(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("fuel_type", mode="before")
    @classmethod
    def normalize_invoice_fuel_type(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("notes", mode="before")
    @classmethod
    def empty_notes_to_none(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    airline_id: int
    provider_id: int
    airline_name: str
    provider_name: str
    airline_code: str
    provider_code: str
    billing_month: date
    invoice_date: date
    fuel_type: str
    quantity: Decimal
    rate_per_unit: Decimal
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    notes: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value
