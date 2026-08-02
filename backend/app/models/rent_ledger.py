import datetime
import decimal
import uuid

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import PaymentStatus
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RentLedger(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """Append-only: one row per tenant per month (docs/DATABASE.md §4.7)."""

    __tablename__ = "rent_ledger"
    __table_args__ = (
        UniqueConstraint("tenant_id", "month", name="uq_rent_ledger_tenant_month"),
        CheckConstraint("rent_amount >= 0", name="ck_rent_ledger_rent_amount_non_negative"),
        CheckConstraint("paid_amount >= 0", name="ck_rent_ledger_paid_amount_non_negative"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    month: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rent_amount: Mapped[decimal.Decimal] = mapped_column(nullable=False)
    paid_amount: Mapped[decimal.Decimal] = mapped_column(nullable=False, default=0, server_default="0")
    # Maintained by the service layer as rent_amount - paid_amount (docs/DATABASE.md §4.7) —
    # not a generated column, so partial payments keep an explicit audit trail.
    balance: Mapped[decimal.Decimal] = mapped_column(nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="rent_ledger_entries")
