"""Importing this package registers every model on Base.metadata — required
for Alembic autogenerate and for Base.metadata.create_all() in tests to see
the full schema.
"""

from app.models.allocation import Allocation
from app.models.bed import Bed
from app.models.building import Building
from app.models.complaint import Complaint
from app.models.document import Document
from app.models.enums import (
    BedStatus,
    ComplaintCategory,
    ComplaintStatus,
    DocumentType,
    ExpenseCategory,
    PaymentStatus,
    Priority,
    RefundStatus,
    RoomStatus,
    TenantStatus,
    UserRole,
    VerificationStatus,
)
from app.models.expense import Expense
from app.models.rent_ledger import RentLedger
from app.models.room import Room
from app.models.security_deposit import SecurityDeposit
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "Allocation",
    "Bed",
    "BedStatus",
    "Building",
    "Complaint",
    "ComplaintCategory",
    "ComplaintStatus",
    "Document",
    "DocumentType",
    "Expense",
    "ExpenseCategory",
    "PaymentStatus",
    "Priority",
    "RefundStatus",
    "RentLedger",
    "Room",
    "RoomStatus",
    "SecurityDeposit",
    "Tenant",
    "TenantStatus",
    "User",
    "UserRole",
    "VerificationStatus",
]
