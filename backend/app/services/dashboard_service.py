import datetime
import decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Bed,
    BedStatus,
    Complaint,
    ComplaintStatus,
    Expense,
    PaymentStatus,
    Priority,
    RentLedger,
    Room,
)


def _current_month_start(today: datetime.date | None = None) -> datetime.date:
    return (today or datetime.date.today()).replace(day=1)


def _next_month_start(month_start: datetime.date) -> datetime.date:
    if month_start.month == 12:
        return month_start.replace(year=month_start.year + 1, month=1)
    return month_start.replace(month=month_start.month + 1)


def _previous_month_start(month_start: datetime.date) -> datetime.date:
    if month_start.month == 1:
        return month_start.replace(year=month_start.year - 1, month=12)
    return month_start.replace(month=month_start.month - 1)


def _sum_expenses(db: Session, start: datetime.date, end: datetime.date) -> decimal.Decimal:
    total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(Expense.date >= start, Expense.date < end).scalar()
    return decimal.Decimal(total)


def get_dashboard_summary(db: Session) -> dict[str, Any]:
    """Matches docs/API.md §5.12's documented response shape."""
    month_start = _current_month_start()
    next_month = _next_month_start(month_start)

    total_beds = db.query(Bed).filter(Bed.is_deleted.is_(False)).count()
    occupied_beds = db.query(Bed).filter(Bed.is_deleted.is_(False), Bed.status == BedStatus.OCCUPIED).count()
    vacant_beds = db.query(Bed).filter(Bed.is_deleted.is_(False), Bed.status == BedStatus.VACANT).count()

    month_rows = db.query(RentLedger).filter(RentLedger.month == month_start).all()
    collected_this_month = sum((row.paid_amount for row in month_rows), decimal.Decimal("0"))
    pending_this_month = sum(
        (row.balance for row in month_rows if row.payment_status != PaymentStatus.PAID), decimal.Decimal("0")
    )
    # Overdue count is not scoped to this month — a stale overdue balance from
    # any prior month still needs attention on a dashboard glance.
    overdue_count = db.query(RentLedger).filter(RentLedger.payment_status == PaymentStatus.OVERDUE).count()

    open_complaints = db.query(Complaint).filter(Complaint.status == ComplaintStatus.OPEN).count()
    in_progress_complaints = db.query(Complaint).filter(Complaint.status == ComplaintStatus.IN_PROGRESS).count()
    urgent_complaints = (
        db.query(Complaint)
        .filter(
            Complaint.priority == Priority.URGENT,
            Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]),
        )
        .count()
    )

    return {
        "occupancy": {"total_beds": total_beds, "occupied_beds": occupied_beds, "vacant_beds": vacant_beds},
        "rent": {
            "collected_this_month": collected_this_month,
            "pending_this_month": pending_this_month,
            "overdue_count": overdue_count,
        },
        "complaints": {"open": open_complaints, "in_progress": in_progress_complaints, "urgent": urgent_complaints},
        "expenses": {"this_month": _sum_expenses(db, month_start, next_month)},
    }


def get_income_report(db: Session, *, months: int) -> list[dict[str, Any]]:
    """Trailing `months` (including the current one), oldest first."""
    rows: list[dict[str, Any]] = []
    month_start = _current_month_start()
    for _ in range(months):
        next_month = _next_month_start(month_start)
        rent_collected = decimal.Decimal(
            db.query(func.coalesce(func.sum(RentLedger.paid_amount), 0))
            .filter(RentLedger.month == month_start)
            .scalar()
        )
        expenses_total = _sum_expenses(db, month_start, next_month)
        rows.append(
            {
                "month": month_start,
                "rent_collected": rent_collected,
                "expenses": expenses_total,
                "net": rent_collected - expenses_total,
            }
        )
        month_start = _previous_month_start(month_start)
    rows.reverse()
    return rows


def get_occupancy_report(db: Session) -> list[dict[str, Any]]:
    """Per-room breakdown, complementing the dashboard's single aggregate number."""
    occupied_counts = dict(
        db.query(Bed.room_id, func.count(Bed.id))
        .filter(Bed.is_deleted.is_(False), Bed.status == BedStatus.OCCUPIED)
        .group_by(Bed.room_id)
        .all()
    )
    rooms = db.query(Room).filter(Room.is_deleted.is_(False)).order_by(Room.room_number).all()
    return [
        {
            "room_id": room.id,
            "building_id": room.building_id,
            "room_number": room.room_number,
            "capacity": room.capacity,
            "occupied_beds": occupied_counts.get(room.id, 0),
            "status": room.status,
        }
        for room in rooms
    ]


def get_complaints_report(db: Session) -> list[dict[str, Any]]:
    """Category breakdown — open (incl. reopened) vs. all-time total per category."""
    total_counts = dict(db.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all())
    open_counts = dict(
        db.query(Complaint.category, func.count(Complaint.id))
        .filter(Complaint.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED]))
        .group_by(Complaint.category)
        .all()
    )
    rows = [
        {"category": category, "open_count": open_counts.get(category, 0), "total_count": total_count}
        for category, total_count in total_counts.items()
    ]
    rows.sort(key=lambda row: row["total_count"], reverse=True)
    return rows
