import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import PaymentStatus


class RentLedgerCreate(BaseModel):
    tenant_id: uuid.UUID
    month: datetime.date
    rent_amount: decimal.Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    due_date: datetime.date

    @field_validator("month")
    @classmethod
    def month_must_be_first_of_month(cls, v: datetime.date) -> datetime.date:
        if v.day != 1:
            raise ValueError("month must be the first day of the month (e.g. 2026-08-01).")
        return v


class RentPayment(BaseModel):
    amount: decimal.Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)


class RentLedgerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    month: datetime.date
    rent_amount: decimal.Decimal
    paid_amount: decimal.Decimal
    balance: decimal.Decimal
    due_date: datetime.date
    payment_status: PaymentStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
