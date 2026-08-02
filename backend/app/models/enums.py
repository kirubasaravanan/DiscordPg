import enum


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    STAFF = "STAFF"
    TENANT = "TENANT"


class RoomStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    FULL = "FULL"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"


class BedStatus(str, enum.Enum):
    VACANT = "VACANT"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"


class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    EXITED = "EXITED"
    BLACKLISTED = "BLACKLISTED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class RefundStatus(str, enum.Enum):
    HELD = "HELD"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    FORFEITED = "FORFEITED"


class ComplaintCategory(str, enum.Enum):
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    CLEANING = "CLEANING"
    WIFI = "WIFI"
    FOOD = "FOOD"
    SECURITY = "SECURITY"
    OTHER = "OTHER"


class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ComplaintStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class ExpenseCategory(str, enum.Enum):
    MAINTENANCE = "MAINTENANCE"
    UTILITIES = "UTILITIES"
    SALARY = "SALARY"
    SUPPLIES = "SUPPLIES"
    OTHER = "OTHER"


class DocumentType(str, enum.Enum):
    ID_PROOF = "ID_PROOF"
    ADDRESS_PROOF = "ADDRESS_PROOF"
    AGREEMENT = "AGREEMENT"
    PHOTO = "PHOTO"
    OTHER = "OTHER"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
