import datetime
import decimal

from conftest import auth_headers


def _month_start(d: datetime.date) -> datetime.date:
    return d.replace(day=1)


def _previous_month_start(month_start: datetime.date) -> datetime.date:
    last_day_of_prev_month = month_start - datetime.timedelta(days=1)
    return last_day_of_prev_month.replace(day=1)


def test_dashboard_aggregates_exactly(client, staff_user, db_session, building, tenant):
    from app.models import (
        Bed,
        BedStatus,
        Complaint,
        ComplaintCategory,
        ComplaintStatus,
        Expense,
        ExpenseCategory,
        PaymentStatus,
        Priority,
        RentLedger,
        Room,
    )

    room = Room(building_id=building.id, room_number="d1", floor=1, capacity=2)
    db_session.add(room)
    db_session.flush()
    db_session.add_all(
        [
            Bed(room_id=room.id, bed_number="A", status=BedStatus.OCCUPIED),
            Bed(room_id=room.id, bed_number="B", status=BedStatus.VACANT),
        ]
    )

    this_month = _month_start(datetime.date.today())
    prev_month = _previous_month_start(this_month)

    db_session.add_all(
        [
            RentLedger(
                tenant_id=tenant.id,
                month=this_month,
                rent_amount=decimal.Decimal("5000.00"),
                paid_amount=decimal.Decimal("5000.00"),
                balance=decimal.Decimal("0.00"),
                due_date=this_month,
                payment_status=PaymentStatus.PAID,
            ),
            RentLedger(
                tenant_id=tenant.id,
                month=prev_month,
                rent_amount=decimal.Decimal("5000.00"),
                paid_amount=decimal.Decimal("2000.00"),
                balance=decimal.Decimal("3000.00"),
                due_date=prev_month,
                payment_status=PaymentStatus.OVERDUE,
            ),
        ]
    )

    db_session.add_all(
        [
            Complaint(
                tenant_id=tenant.id,
                category=ComplaintCategory.PLUMBING,
                description="urgent open one",
                priority=Priority.URGENT,
                status=ComplaintStatus.OPEN,
            ),
            Complaint(
                tenant_id=tenant.id,
                category=ComplaintCategory.WIFI,
                description="resolved urgent one - should not count",
                priority=Priority.URGENT,
                status=ComplaintStatus.RESOLVED,
                resolved_at=datetime.datetime.now(datetime.timezone.utc),
            ),
            Complaint(
                tenant_id=tenant.id,
                category=ComplaintCategory.CLEANING,
                description="in progress",
                priority=Priority.LOW,
                status=ComplaintStatus.IN_PROGRESS,
            ),
        ]
    )

    db_session.add(
        Expense(
            building_id=building.id,
            category=ExpenseCategory.MAINTENANCE,
            amount=decimal.Decimal("300.00"),
            date=this_month,
        )
    )
    db_session.flush()

    resp = client.get("/api/v1/dashboard", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    body = resp.json()

    assert body["occupancy"] == {"total_beds": 2, "occupied_beds": 1, "vacant_beds": 1}
    assert body["rent"]["collected_this_month"] == "5000.00"  # only this_month's PAID row counts
    assert body["rent"]["overdue_count"] == 1  # counts across all months, not just this one
    assert body["complaints"] == {"open": 1, "in_progress": 1, "urgent": 1}  # resolved urgent excluded
    assert body["expenses"]["this_month"] == "300.00"


def test_dashboard_requires_auth(client):
    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 401


def test_reports_forbidden_for_staff(client, staff_user):
    resp = client.get("/api/v1/reports/income", headers=auth_headers(staff_user))
    assert resp.status_code == 403


def test_income_report_shape_and_ordering(client, manager_user, db_session, tenant, building):
    from app.models import ExpenseCategory, PaymentStatus, RentLedger

    this_month = _month_start(datetime.date.today())
    prev_month = _previous_month_start(this_month)
    db_session.add(
        RentLedger(
            tenant_id=tenant.id,
            month=prev_month,
            rent_amount=decimal.Decimal("1000.00"),
            paid_amount=decimal.Decimal("1000.00"),
            balance=decimal.Decimal("0.00"),
            due_date=prev_month,
            payment_status=PaymentStatus.PAID,
        )
    )
    db_session.flush()

    resp = client.get("/api/v1/reports/income?months=2", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert rows[0]["month"] < rows[1]["month"]  # oldest first
    assert rows[1]["month"] == this_month.isoformat()
    prev_row = next(r for r in rows if r["month"] == prev_month.isoformat())
    assert prev_row["rent_collected"] == "1000.00"
    assert prev_row["net"] == "1000.00"


def test_occupancy_report_per_room(client, manager_user, room, bed):
    resp = client.get("/api/v1/reports/occupancy", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    row = next(r for r in rows if r["room_id"] == str(room.id))
    assert row["capacity"] == room.capacity
    assert row["occupied_beds"] == 0  # `bed` fixture defaults to VACANT


def test_complaints_report_groups_by_category(client, manager_user, db_session, tenant):
    from app.models import Complaint, ComplaintCategory, ComplaintStatus, Priority

    db_session.add_all(
        [
            Complaint(
                tenant_id=tenant.id,
                category=ComplaintCategory.PLUMBING,
                description="a",
                priority=Priority.LOW,
                status=ComplaintStatus.OPEN,
            ),
            Complaint(
                tenant_id=tenant.id,
                category=ComplaintCategory.PLUMBING,
                description="b",
                priority=Priority.LOW,
                status=ComplaintStatus.CLOSED,
            ),
        ]
    )
    db_session.flush()

    resp = client.get("/api/v1/reports/complaints", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    row = next(r for r in resp.json()["by_category"] if r["category"] == "PLUMBING")
    assert row["total_count"] == 2
    assert row["open_count"] == 1
