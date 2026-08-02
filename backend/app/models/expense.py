import datetime
import decimal
import uuid

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ExpenseCategory
from app.models.mixins import AuditUserMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, AuditUserMixin, Base):
    """Append-only (docs/DATABASE.md §4.10). `building_id` is nullable — an
    addition beyond CLAUDE.md's field list so expenses can be scoped to a
    building once a second one exists, while still allowing general/company
    expenses with no single building.
    """

    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_expenses_amount_non_negative"),)

    building_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("buildings.id"), nullable=True)
    category: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory, name="expense_category"), nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    building: Mapped["Building | None"] = relationship(back_populates="expenses")
