import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    discord_id: str | None = Field(None, max_length=32)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    role: UserRole | None = None
    is_active: bool | None = None
    discord_id: str | None = Field(None, max_length=32)
    password: str | None = Field(None, min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    phone: str | None
    role: UserRole
    discord_id: str | None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
