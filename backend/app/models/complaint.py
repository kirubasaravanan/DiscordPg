import datetime
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ComplaintCategory, ComplaintStatus, Priority
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Complaint(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """Append-only (docs/DATABASE.md §4.9). `category`/`priority` are filled in by
    the AI classifier (Phase 6) and validated against these enums before the
    service layer persists them — see docs/ARCHITECTURE.md §5.
    """

    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_status_priority", "status", "priority"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    category: Mapped[ComplaintCategory] = mapped_column(Enum(ComplaintCategory, name="complaint_category"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority"), nullable=False, default=Priority.MEDIUM, server_default=Priority.MEDIUM.value
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status"),
        nullable=False,
        default=ComplaintStatus.OPEN,
        server_default=ComplaintStatus.OPEN.value,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="complaints")
    room: Mapped["Room | None"] = relationship(back_populates="complaints")
