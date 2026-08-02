import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import RoomStatus


class RoomCreate(BaseModel):
    building_id: uuid.UUID
    room_number: str = Field(..., min_length=1, max_length=20)
    floor: int | None = None
    capacity: int = Field(..., gt=0)


class RoomUpdate(BaseModel):
    room_number: str | None = Field(None, min_length=1, max_length=20)
    floor: int | None = None
    capacity: int | None = Field(None, gt=0)
    # FULL is excluded deliberately — see app/services/room_service.py, it's
    # derived from bed occupancy, not something set directly.
    status: RoomStatus | None = None


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_id: uuid.UUID
    room_number: str
    floor: int | None
    capacity: int
    status: RoomStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
