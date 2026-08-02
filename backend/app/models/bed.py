import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import BedStatus
from app.models.mixins import AuditUserMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Bed(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, SoftDeleteMixin, Base):
    __tablename__ = "beds"
    __table_args__ = (UniqueConstraint("room_id", "bed_number", name="uq_beds_room_bed_number"),)

    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    bed_number: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[BedStatus] = mapped_column(
        Enum(BedStatus, name="bed_status"),
        nullable=False,
        default=BedStatus.VACANT,
        server_default=BedStatus.VACANT.value,
    )

    room: Mapped["Room"] = relationship(back_populates="beds")
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="bed")
