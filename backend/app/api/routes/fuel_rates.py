from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, get_current_admin
from app.models.fuel_rate import FuelRate
from app.schemas.fuel_rate import FuelRateCreate, FuelRateResponse, FuelRateUpdate

router = APIRouter(
    prefix="/fuel-rates", tags=["Fuel Rates"], dependencies=[Depends(get_current_admin)]
)


@router.get("", response_model=list[FuelRateResponse])
def list_fuel_rates(db: DbSession) -> list[FuelRate]:
    return db.query(FuelRate).order_by(FuelRate.effective_from.desc(), FuelRate.id.desc()).all()


@router.post("", response_model=FuelRateResponse, status_code=status.HTTP_201_CREATED)
def create_fuel_rate(payload: FuelRateCreate, db: DbSession) -> FuelRate:
    rate = FuelRate(**payload.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


@router.put("/{rate_id}", response_model=FuelRateResponse)
def update_fuel_rate(rate_id: int, payload: FuelRateUpdate, db: DbSession) -> FuelRate:
    rate = db.get(FuelRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuel rate not found")
    for field, value in payload.model_dump().items():
        setattr(rate, field, value)
    db.commit()
    db.refresh(rate)
    return rate
