import datetime
import uuid

from sqlalchemy import Date, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Allocation(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """Append-only: never soft-deleted, only closed via `end_date` (docs/DATABASE.md §4.6)."""

    __tablename__ = "allocations"
    __table_args__ = (
        # A bed may have at most one active (end_date IS NULL) allocation at a time.
        Index("uq_allocations_active_bed", "bed_id", unique=True, postgresql_where=text("end_date IS NULL")),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    bed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("beds.id"), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="allocations")
    room: Mapped["Room"] = relationship(back_populates="allocations")
    bed: Mapped["Bed"] = relationship(back_populates="allocations")
