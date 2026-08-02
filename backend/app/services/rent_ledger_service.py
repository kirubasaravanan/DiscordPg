import decimal
import uuid

from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.models import PaymentStatus, RentLedger
from app.schemas.rent_ledger import RentLedgerCreate
from app.services.tenant_service import get_tenant


def list_rent_ledger(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    payment_status: PaymentStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[RentLedger], int]:
    query = db.query(RentLedger)
    if tenant_id is not None:
        query = query.filter(RentLedger.tenant_id == tenant_id)
    if payment_status is not None:
        query = query.filter(RentLedger.payment_status == payment_status)
    query = query.order_by(RentLedger.month.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_rent_entry(db: Session, entry_id: uuid.UUID) -> RentLedger:
    entry = db.get(RentLedger, entry_id)
    if entry is None:
        raise not_found("Rent ledger entry not found.")
    return entry


def create_rent_entry(db: Session, payload: RentLedgerCreate, actor_id: uuid.UUID) -> RentLedger:
    get_tenant(db, payload.tenant_id)  # 404s if the tenant doesn't exist
    entry = RentLedger(
        tenant_id=payload.tenant_id,
        month=payload.month,
        rent_amount=payload.rent_amount,
        paid_amount=decimal.Decimal("0"),
        balance=payload.rent_amount,
        due_date=payload.due_date,
        payment_status=PaymentStatus.PENDING,
        created_by=actor_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def record_payment(db: Session, entry_id: uuid.UUID, amount: decimal.Decimal, actor_id: uuid.UUID) -> RentLedger:
    """Adds `amount` to paid_amount and recomputes balance/payment_status.

    Overpayment (paid_amount ending up above rent_amount) is allowed rather
    than rejected — docs/DATABASE.md only constrains paid_amount >= 0, and
    advance payment is a legitimate real-world case; it just resolves to PAID
    with a negative balance representing credit.
    """
    entry = get_rent_entry(db, entry_id)
    entry.paid_amount = entry.paid_amount + amount
    entry.balance = entry.rent_amount - entry.paid_amount
    entry.payment_status = PaymentStatus.PAID if entry.paid_amount >= entry.rent_amount else PaymentStatus.PARTIAL
    entry.updated_by = actor_id
    db.commit()
    db.refresh(entry)
    return entry
