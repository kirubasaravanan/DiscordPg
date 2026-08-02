import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class AllocationCreate(BaseModel):
    tenant_id: uuid.UUID
    # room_id is deliberately not accepted here (deviates from the original
    # docs/API.md example) — it's derived server-side from bed.room_id, which
    # removes an entire class of "room_id doesn't match this bed" bad input.
    bed_id: uuid.UUID
    start_date: datetime.date


class AllocationEnd(BaseModel):
    end_date: datetime.date | None = None  # defaults to today if omitted


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    room_id: uuid.UUID
    bed_id: uuid.UUID
    start_date: datetime.date
    end_date: datetime.date | None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
