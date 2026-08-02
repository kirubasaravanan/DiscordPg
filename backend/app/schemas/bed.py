import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import BedStatus


class BedCreate(BaseModel):
    room_id: uuid.UUID
    bed_number: str = Field(..., min_length=1, max_length=10)


class BedUpdate(BaseModel):
    bed_number: str | None = Field(None, min_length=1, max_length=10)
    # OCCUPIED is excluded deliberately — see app/services/bed_service.py,
    # it's derived from allocations, not something set directly.
    status: BedStatus | None = None


class BedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    bed_number: str
    status: BedStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
