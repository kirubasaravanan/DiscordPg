import datetime
import decimal
import uuid

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import RefundStatus
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SecurityDeposit(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """Append-only (docs/DATABASE.md §4.8)."""

    __tablename__ = "security_deposits"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_security_deposits_amount_non_negative"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(nullable=False)
    received_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    refund_status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"),
        nullable=False,
        default=RefundStatus.HELD,
        server_default=RefundStatus.HELD.value,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="security_deposits")
