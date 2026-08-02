import uuid

from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.models import SecurityDeposit
from app.schemas.security_deposit import SecurityDepositCreate, SecurityDepositUpdate
from app.services.tenant_service import get_tenant


def list_deposits(
    db: Session, *, tenant_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[SecurityDeposit], int]:
    query = db.query(SecurityDeposit)
    if tenant_id is not None:
        query = query.filter(SecurityDeposit.tenant_id == tenant_id)
    query = query.order_by(SecurityDeposit.received_date.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_deposit(db: Session, deposit_id: uuid.UUID) -> SecurityDeposit:
    deposit = db.get(SecurityDeposit, deposit_id)
    if deposit is None:
        raise not_found("Security deposit not found.")
    return deposit


def create_deposit(db: Session, payload: SecurityDepositCreate, actor_id: uuid.UUID) -> SecurityDeposit:
    get_tenant(db, payload.tenant_id)  # 404s if the tenant doesn't exist
    deposit = SecurityDeposit(**payload.model_dump(), created_by=actor_id)
    db.add(deposit)
    db.commit()
    db.refresh(deposit)
    return deposit


def update_deposit(
    db: Session, deposit_id: uuid.UUID, payload: SecurityDepositUpdate, actor_id: uuid.UUID
) -> SecurityDeposit:
    deposit = get_deposit(db, deposit_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(deposit, field, value)
    deposit.updated_by = actor_id
    db.commit()
    db.refresh(deposit)
    return deposit
