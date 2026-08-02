import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import RoomStatus
from app.models.mixins import AuditUserMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Room(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, SoftDeleteMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("building_id", "room_number", name="uq_rooms_building_room_number"),
        CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),
    )

    building_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status"),
        nullable=False,
        default=RoomStatus.AVAILABLE,
        server_default=RoomStatus.AVAILABLE.value,
    )

    building: Mapped["Building"] = relationship(back_populates="rooms")
    beds: Mapped[list["Bed"]] = relationship(back_populates="room")
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="room")
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="room")
