import datetime
import decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Allocation, Bed, Expense, ExpenseCategory, RentLedger, Room, SecurityDeposit


# --- Unique constraints -----------------------------------------------------


def test_room_number_unique_within_building(db_session, building, room):
    db_session.commit()
    db_session.add(Room(building_id=building.id, room_number=room.room_number, floor=2, capacity=3))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_room_number_can_repeat_across_buildings(db_session, building, room):
    from app.models import Building

    db_session.commit()
    other_building = Building(name="Other PG", address="2 Other Street")
    db_session.add(other_building)
    db_session.flush()
    db_session.add(Room(building_id=other_building.id, room_number=room.room_number, floor=1, capacity=2))
    db_session.flush()  # must not raise


def test_bed_number_unique_within_room(db_session, room, bed):
    db_session.commit()
    db_session.add(Bed(room_id=room.id, bed_number=bed.bed_number))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_tenant_phone_unique(db_session, tenant):
    from app.models import Tenant

    db_session.commit()
    db_session.add(Tenant(name="Duplicate Phone", phone=tenant.phone, joining_date=datetime.date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rent_ledger_one_row_per_tenant_per_month(db_session, tenant):
    month = datetime.date(2026, 6, 1)
    db_session.add(
        RentLedger(
            tenant_id=tenant.id,
            month=month,
            rent_amount=decimal.Decimal("9000"),
            due_date=datetime.date(2026, 6, 5),
            balance=decimal.Decimal("9000"),
        )
    )
    db_session.commit()

    db_session.add(
        RentLedger(
            tenant_id=tenant.id,
            month=month,
            rent_amount=decimal.Decimal("9000"),
            due_date=datetime.date(2026, 6, 5),
            balance=decimal.Decimal("9000"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


# --- Check constraints -------------------------------------------------------


def test_room_capacity_must_be_positive(db_session, building):
    db_session.add(Room(building_id=building.id, room_number="999", floor=1, capacity=0))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rent_ledger_amounts_cannot_be_negative(db_session, tenant):
    db_session.add(
        RentLedger(
            tenant_id=tenant.id,
            month=datetime.date(2026, 6, 1),
            rent_amount=decimal.Decimal("-100"),
            due_date=datetime.date(2026, 6, 5),
            balance=decimal.Decimal("-100"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_security_deposit_amount_cannot_be_negative(db_session, tenant):
    db_session.add(SecurityDeposit(tenant_id=tenant.id, amount=decimal.Decimal("-1"), received_date=datetime.date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_expense_amount_cannot_be_negative(db_session, building):
    db_session.add(
        Expense(
            building_id=building.id,
            category=ExpenseCategory.MAINTENANCE,
            amount=decimal.Decimal("-1"),
            date=datetime.date(2026, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


# --- Partial unique index: one active allocation per bed --------------------


def test_bed_can_have_only_one_active_allocation(db_session, tenant, room, bed):
    from app.models import Tenant

    db_session.add(Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1)))
    db_session.commit()

    other_tenant = Tenant(name="Second Tenant", phone="9000000001", joining_date=datetime.date(2026, 2, 1))
    db_session.add(other_tenant)
    db_session.flush()
    db_session.add(Allocation(tenant_id=other_tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 2, 1)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_bed_can_be_reallocated_once_previous_allocation_ends(db_session, tenant, room, bed):
    from app.models import Tenant

    first = Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1))
    db_session.add(first)
    db_session.commit()

    # Close out the first allocation before starting the next one.
    first.end_date = datetime.date(2026, 3, 1)
    db_session.flush()

    second_tenant = Tenant(name="Next Tenant", phone="9000000002", joining_date=datetime.date(2026, 3, 1))
    db_session.add(second_tenant)
    db_session.flush()
    db_session.add(
        Allocation(tenant_id=second_tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 3, 1))
    )
    db_session.flush()  # must not raise — only one *active* (end_date IS NULL) allocation exists
