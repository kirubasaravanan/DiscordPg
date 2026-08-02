import datetime
import uuid

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import TenantStatus
from app.models.mixins import AuditUserMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, SoftDeleteMixin, Base):
    __tablename__ = "tenants"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    joining_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    exit_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        nullable=False,
        default=TenantStatus.ACTIVE,
        server_default=TenantStatus.ACTIVE.value,
    )

    # Disambiguates against the created_by/updated_by FKs to users.id that
    # AuditUserMixin also adds — without this, SQLAlchemy can't tell which
    # of the three tenants->users foreign keys this relationship should join on.
    user: Mapped["User | None"] = relationship(back_populates="tenant", foreign_keys=[user_id])
    allocations: Mapped[list["Allocation"]] = relationship(back_populates="tenant")
    rent_ledger_entries: Mapped[list["RentLedger"]] = relationship(back_populates="tenant")
    security_deposits: Mapped[list["SecurityDeposit"]] = relationship(back_populates="tenant")
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="tenant")
    documents: Mapped[list["Document"]] = relationship(back_populates="tenant")
