"""Seed representative development data (docs/DATABASE.md §9).

Run from backend/: `uv run python -m app.database.seed`

Safe to re-run: no-ops if a Building already exists rather than duplicating
rows. Local/dev use only — never point this at a production database.
"""

import datetime
import decimal

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models import (
    Allocation,
    Bed,
    BedStatus,
    Building,
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    Expense,
    ExpenseCategory,
    PaymentStatus,
    Priority,
    RentLedger,
    Room,
    RoomStatus,
    SecurityDeposit,
    Tenant,
    User,
    UserRole,
)
from app.security.password import hash_password

# Fake, obviously-labeled dev-only credentials — real Argon2id hashes so
# login actually works locally, but never use these outside a local/dev
# database seeded from this script.
SEED_PASSWORDS = {
    UserRole.OWNER: "Owner-Dev-Pass123!",
    UserRole.MANAGER: "Manager-Dev-Pass123!",
    UserRole.STAFF: "Staff-Dev-Pass123!",
    UserRole.TENANT: "Tenant-Dev-Pass123!",
}

ROOMS = [
    # (room_number, floor, capacity)
    ("101", 1, 2),
    ("102", 1, 3),
    ("103", 1, 2),
    ("201", 2, 3),
    ("202", 2, 2),
]

TENANTS = [
    # (name, phone, email, joining_date)
    ("Arjun Mehta", "9876500001", "arjun.mehta@example.com", datetime.date(2026, 2, 1)),
    ("Priya Nair", "9876500002", "priya.nair@example.com", datetime.date(2026, 3, 15)),
    ("Rohan Gupta", "9876500003", "rohan.gupta@example.com", datetime.date(2026, 4, 1)),
    ("Sneha Iyer", "9876500004", "sneha.iyer@example.com", datetime.date(2026, 5, 10)),
    ("Karthik Rao", "9876500005", "karthik.rao@example.com", datetime.date(2026, 6, 1)),
    ("Divya Shah", "9876500006", "divya.shah@example.com", datetime.date(2026, 7, 1)),
]

RENT = decimal.Decimal("9500.00")


def seed(db: Session | None = None) -> None:
    """Populate representative data.

    Accepts an optional session so tests can inject one bound to the test
    database/transaction instead of the process-wide SessionLocal.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        if db.query(Building).first() is not None:
            print("Seed data already present (a Building exists) — skipping.")
            return

        building = Building(name="Sunrise PG", address="12 MG Road, Bengaluru, Karnataka 560001")
        db.add(building)
        db.flush()

        rooms: list[Room] = []
        beds: list[Bed] = []
        for room_number, floor, capacity in ROOMS:
            room = Room(building_id=building.id, room_number=room_number, floor=floor, capacity=capacity)
            db.add(room)
            db.flush()
            rooms.append(room)
            for i in range(capacity):
                bed = Bed(room_id=room.id, bed_number=chr(ord("A") + i))
                db.add(bed)
                beds.append(bed)
        db.flush()

        staff_users = [
            User(email="owner@example.com", password_hash=hash_password(SEED_PASSWORDS[UserRole.OWNER]), role=UserRole.OWNER),
            User(email="manager@example.com", password_hash=hash_password(SEED_PASSWORDS[UserRole.MANAGER]), role=UserRole.MANAGER),
            User(email="staff@example.com", password_hash=hash_password(SEED_PASSWORDS[UserRole.STAFF]), role=UserRole.STAFF),
        ]
        db.add_all(staff_users)

        tenants = [
            Tenant(name=name, phone=phone, email=email, joining_date=joining, emergency_contact="9876599999")
            for name, phone, email, joining in TENANTS
        ]
        db.add_all(tenants)
        db.flush()

        # Link the first tenant to a TENANT-role portal/bot account.
        tenant_user = User(
            email=tenants[0].email, password_hash=hash_password(SEED_PASSWORDS[UserRole.TENANT]), role=UserRole.TENANT
        )
        db.add(tenant_user)
        db.flush()
        tenants[0].user_id = tenant_user.id

        # Allocate the first 5 tenants to the first 5 beds (all of rooms 101 and
        # 102), so those two rooms end up FULL while 103/201/202 stay vacant —
        # exercising both occupied and available states.
        allocation_start = datetime.date(2026, 2, 1)
        for tenant, bed in zip(tenants[:5], beds[:5]):
            db.add(Allocation(tenant_id=tenant.id, room_id=bed.room_id, bed_id=bed.id, start_date=allocation_start))
            bed.status = BedStatus.OCCUPIED
            db.add(SecurityDeposit(tenant_id=tenant.id, amount=decimal.Decimal("10000.00"), received_date=allocation_start))
        rooms[0].status = RoomStatus.FULL  # 101, capacity 2, both beds allocated
        rooms[1].status = RoomStatus.FULL  # 102, capacity 3, all beds allocated
        db.flush()

        # Rent ledger for the 5 allocated tenants. "Today" at authoring time is
        # 2026-08-02, so June/July are settled history and August (due the 5th)
        # is still open — deliberately covering every payment_status, including
        # the PARTIAL and OVERDUE rows docs/DATABASE.md §9 calls for.
        jun, jul, aug = datetime.date(2026, 6, 1), datetime.date(2026, 7, 1), datetime.date(2026, 8, 1)
        rent_rows = [
            # (tenant_index, month, paid_amount, status)
            (0, jun, RENT, PaymentStatus.PAID),
            (0, jul, RENT, PaymentStatus.PAID),
            (0, aug, decimal.Decimal("5000.00"), PaymentStatus.PARTIAL),
            (1, jun, RENT, PaymentStatus.PAID),
            (1, jul, decimal.Decimal("0.00"), PaymentStatus.OVERDUE),
            (1, aug, decimal.Decimal("0.00"), PaymentStatus.PENDING),
            (2, jun, RENT, PaymentStatus.PAID),
            (2, jul, RENT, PaymentStatus.PAID),
            (2, aug, decimal.Decimal("0.00"), PaymentStatus.PENDING),
            (3, jun, RENT, PaymentStatus.PAID),
            (3, jul, RENT, PaymentStatus.PAID),
            (3, aug, RENT, PaymentStatus.PAID),
            (4, jun, RENT, PaymentStatus.PAID),
            (4, jul, RENT, PaymentStatus.PAID),
            (4, aug, RENT, PaymentStatus.PAID),
        ]
        for tenant_idx, month, paid, status in rent_rows:
            db.add(
                RentLedger(
                    tenant_id=tenants[tenant_idx].id,
                    month=month,
                    rent_amount=RENT,
                    paid_amount=paid,
                    balance=RENT - paid,
                    due_date=month.replace(day=5),
                    payment_status=status,
                )
            )

        db.add_all(
            [
                Complaint(
                    tenant_id=tenants[0].id,
                    room_id=rooms[0].id,
                    category=ComplaintCategory.PLUMBING,
                    description="Bathroom tap is leaking",
                    priority=Priority.HIGH,
                    status=ComplaintStatus.OPEN,
                ),
                Complaint(
                    tenant_id=tenants[1].id,
                    room_id=rooms[1].id,
                    category=ComplaintCategory.WIFI,
                    description="Wi-Fi drops every evening",
                    priority=Priority.MEDIUM,
                    status=ComplaintStatus.IN_PROGRESS,
                ),
                Complaint(
                    tenant_id=tenants[2].id,
                    room_id=rooms[0].id,
                    category=ComplaintCategory.CLEANING,
                    description="Common area wasn't cleaned this week",
                    priority=Priority.LOW,
                    status=ComplaintStatus.RESOLVED,
                    resolved_at=datetime.datetime(2026, 7, 28, 10, 30, tzinfo=datetime.timezone.utc),
                ),
            ]
        )

        db.add_all(
            [
                Expense(
                    building_id=building.id,
                    category=ExpenseCategory.MAINTENANCE,
                    amount=decimal.Decimal("3200.00"),
                    date=datetime.date(2026, 7, 20),
                    vendor="Sharma Plumbing Works",
                    notes="Fixed leaking pipe in room 101",
                ),
                Expense(
                    building_id=building.id,
                    category=ExpenseCategory.UTILITIES,
                    amount=decimal.Decimal("18500.00"),
                    date=datetime.date(2026, 7, 31),
                    vendor="BESCOM",
                    notes="July electricity bill",
                ),
            ]
        )

        db.commit()
        print(
            f"Seeded 1 building, {len(rooms)} rooms, {len(beds)} beds, "
            f"{len(tenants)} tenants, {len(staff_users) + 1} users, "
            f"{min(5, len(tenants))} allocations, {len(rent_rows)} rent ledger rows."
        )
        print("Dev login credentials (local/dev only):")
        for role, password in SEED_PASSWORDS.items():
            email = tenant_user.email if role is UserRole.TENANT else f"{role.value.lower()}@example.com"
            print(f"  {role.value:<8} {email:<28} {password}")
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    seed()
