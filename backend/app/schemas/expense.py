import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import ExpenseCategory


class ExpenseCreate(BaseModel):
    building_id: uuid.UUID | None = None
    category: ExpenseCategory
    amount: decimal.Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    date: datetime.date
    vendor: str | None = Field(None, max_length=255)
    notes: str | None = None


class ExpenseUpdate(BaseModel):
    building_id: uuid.UUID | None = None
    category: ExpenseCategory | None = None
    amount: decimal.Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    date: datetime.date | None = None
    vendor: str | None = Field(None, max_length=255)
    notes: str | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_id: uuid.UUID | None
    category: ExpenseCategory
    amount: decimal.Decimal
    date: datetime.date
    vendor: str | None
    notes: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
