from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import UserRole
from app.models.mixins import AuditUserMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    discord_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Bumped on logout to invalidate every refresh token issued before that
    # point (see app/security/jwt.py create_refresh_token) — not part of the
    # original docs/DATABASE.md design, added for Phase 3 auth/logout.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    tenant: Mapped["Tenant | None"] = relationship(back_populates="user", foreign_keys="Tenant.user_id")
