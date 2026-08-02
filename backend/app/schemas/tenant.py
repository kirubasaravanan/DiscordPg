import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import TenantStatus


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=7, max_length=20)
    email: EmailStr | None = None
    emergency_contact: str | None = Field(None, max_length=20)
    joining_date: datetime.date


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, min_length=7, max_length=20)
    email: EmailStr | None = None
    emergency_contact: str | None = Field(None, max_length=20)
    exit_date: datetime.date | None = None
    status: TenantStatus | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    phone: str
    email: str | None
    emergency_contact: str | None
    joining_date: datetime.date
    exit_date: datetime.date | None
    status: TenantStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
