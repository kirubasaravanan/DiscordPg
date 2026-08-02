import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import PaymentStatus, User, UserRole
from app.schemas.common import Page
from app.schemas.rent_ledger import RentLedgerCreate, RentLedgerRead, RentPayment
from app.services import rent_ledger_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[RentLedgerRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_rent_ledger(
    tenant_id: uuid.UUID | None = Query(None),
    payment_status: PaymentStatus | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = rent_ledger_service.list_rent_ledger(
        db,
        tenant_id=tenant_id,
        payment_status=payment_status,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=RentLedgerRead, status_code=status.HTTP_201_CREATED)
def create_rent_entry(
    payload: RentLedgerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> RentLedgerRead:
    return rent_ledger_service.create_rent_entry(db, payload, actor_id=current_user.id)


@router.patch("/{entry_id}/payment", response_model=RentLedgerRead)
def record_payment(
    entry_id: uuid.UUID,
    payload: RentPayment,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> RentLedgerRead:
    return rent_ledger_service.record_payment(db, entry_id, payload.amount, actor_id=current_user.id)
