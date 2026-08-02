import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import ComplaintCategory, ComplaintStatus, Priority


class ComplaintCreate(BaseModel):
    """Tenant-facing creation (`POST /api/v1/tenant/complaints`).

    `category` is an optional suggestion, not a classification — see
    app/services/complaint_service.py for why (no AI classifier until
    Phase 6). `priority`/`status` are never client-supplied.
    """

    description: str = Field(..., min_length=1)
    room_id: uuid.UUID | None = None
    category: ComplaintCategory | None = None


class ComplaintUpdate(BaseModel):
    """Admin/staff update (`PATCH /api/v1/complaints/{id}`)."""

    category: ComplaintCategory | None = None
    priority: Priority | None = None
    status: ComplaintStatus | None = None


class ComplaintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    room_id: uuid.UUID | None
    category: ComplaintCategory
    description: str
    priority: Priority
    status: ComplaintStatus
    resolved_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
