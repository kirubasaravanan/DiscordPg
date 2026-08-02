import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import RefundStatus


class SecurityDepositCreate(BaseModel):
    tenant_id: uuid.UUID
    amount: decimal.Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    received_date: datetime.date


class SecurityDepositUpdate(BaseModel):
    refund_status: RefundStatus | None = None


class SecurityDepositRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    amount: decimal.Decimal
    received_date: datetime.date
    refund_status: RefundStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None
