from pydantic import BaseModel, ConfigDict, Field


class PartyBase(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=150)
    contact_person: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)


class FuelProviderCreate(PartyBase):
    pass


class FuelProviderUpdate(PartyBase):
    pass


class FuelProviderResponse(PartyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AirlineCreate(PartyBase):
    pass


class AirlineUpdate(PartyBase):
    pass


class AirlineResponse(PartyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
