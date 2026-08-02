import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class BuildingCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None


class BuildingUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = None


class BuildingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
