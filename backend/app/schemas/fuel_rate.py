from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FuelRateBase(BaseModel):
    fuel_type: str = Field(min_length=2, max_length=80)
    rate_per_litre: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    effective_from: date


class FuelRateCreate(FuelRateBase):
    pass


class FuelRateUpdate(FuelRateBase):
    pass


class FuelRateResponse(FuelRateBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
