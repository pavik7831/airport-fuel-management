from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, get_current_admin
from app.models.airline import Airline
from app.models.fuel_provider import FuelProvider
from app.schemas.party import (
    AirlineCreate, AirlineResponse, AirlineUpdate,
    FuelProviderCreate, FuelProviderResponse, FuelProviderUpdate,
)

router = APIRouter(tags=["Master Data"], dependencies=[Depends(get_current_admin)])


def save_party(db: DbSession, model: type[FuelProvider] | type[Airline], payload, item_id: int | None = None):
    item = db.get(model, item_id) if item_id is not None else model(**payload.model_dump())
    if item is None:
        raise HTTPException(status_code=404, detail="Record not found")
    existing = db.scalar(select(model).where(model.code == payload.code, model.id != item.id))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code already exists")
    if item_id is not None:
        for field, value in payload.model_dump().items():
            setattr(item, field, value)
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.get("/fuel-providers", response_model=list[FuelProviderResponse])
def list_fuel_providers(db: DbSession):
    return db.scalars(select(FuelProvider).order_by(FuelProvider.name)).all()


@router.post("/fuel-providers", response_model=FuelProviderResponse, status_code=status.HTTP_201_CREATED)
def create_fuel_provider(payload: FuelProviderCreate, db: DbSession):
    return save_party(db, FuelProvider, payload)


@router.put("/fuel-providers/{provider_id}", response_model=FuelProviderResponse)
def update_fuel_provider(provider_id: int, payload: FuelProviderUpdate, db: DbSession):
    return save_party(db, FuelProvider, payload, provider_id)


@router.get("/airlines", response_model=list[AirlineResponse])
def list_airlines(db: DbSession):
    return db.scalars(select(Airline).order_by(Airline.name)).all()


@router.post("/airlines", response_model=AirlineResponse, status_code=status.HTTP_201_CREATED)
def create_airline(payload: AirlineCreate, db: DbSession):
    return save_party(db, Airline, payload)


@router.put("/airlines/{airline_id}", response_model=AirlineResponse)
def update_airline(airline_id: int, payload: AirlineUpdate, db: DbSession):
    return save_party(db, Airline, payload, airline_id)
