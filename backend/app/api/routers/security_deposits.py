import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.common import Page
from app.schemas.security_deposit import SecurityDepositCreate, SecurityDepositRead, SecurityDepositUpdate
from app.services import security_deposit_service

router = APIRouter()

# Per docs/API.md §3 permission matrix, deposits are the one resource with no
# STAFF read access at all — narrower than every other resource so far.
ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[SecurityDepositRead], dependencies=[Depends(require_roles(*ROLES))])
def list_deposits(
    tenant_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = security_deposit_service.list_deposits(
        db, tenant_id=tenant_id, limit=pagination.page_size, offset=pagination.offset
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=SecurityDepositRead, status_code=status.HTTP_201_CREATED)
def create_deposit(
    payload: SecurityDepositCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> SecurityDepositRead:
    return security_deposit_service.create_deposit(db, payload, actor_id=current_user.id)


@router.patch("/{deposit_id}", response_model=SecurityDepositRead)
def update_deposit(
    deposit_id: uuid.UUID,
    payload: SecurityDepositUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> SecurityDepositRead:
    return security_deposit_service.update_deposit(db, deposit_id, payload, actor_id=current_user.id)
