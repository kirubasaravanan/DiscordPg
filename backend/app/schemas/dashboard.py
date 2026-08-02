import datetime
import decimal
import uuid

from pydantic import BaseModel

from app.models import ComplaintCategory, RoomStatus


class OccupancySummary(BaseModel):
    total_beds: int
    occupied_beds: int
    vacant_beds: int


class RentSummary(BaseModel):
    collected_this_month: decimal.Decimal
    pending_this_month: decimal.Decimal
    overdue_count: int


class ComplaintsSummary(BaseModel):
    open: int
    in_progress: int
    urgent: int


class ExpensesSummary(BaseModel):
    this_month: decimal.Decimal


class DashboardRead(BaseModel):
    """Matches docs/API.md §5.12's documented shape exactly."""

    occupancy: OccupancySummary
    rent: RentSummary
    complaints: ComplaintsSummary
    expenses: ExpensesSummary


class IncomeReportRow(BaseModel):
    month: datetime.date
    rent_collected: decimal.Decimal
    expenses: decimal.Decimal
    net: decimal.Decimal


class IncomeReport(BaseModel):
    rows: list[IncomeReportRow]


class RoomOccupancyRow(BaseModel):
    room_id: uuid.UUID
    building_id: uuid.UUID
    room_number: str
    capacity: int
    occupied_beds: int
    status: RoomStatus


class OccupancyReport(BaseModel):
    rows: list[RoomOccupancyRow]


class ComplaintCategoryBreakdown(BaseModel):
    category: ComplaintCategory
    open_count: int
    total_count: int


class ComplaintsReport(BaseModel):
    by_category: list[ComplaintCategoryBreakdown]
