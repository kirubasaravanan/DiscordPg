import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.allocation import AllocationCreate, AllocationEnd, AllocationRead
from app.schemas.common import Page
from app.services import allocation_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[AllocationRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_allocations(
    tenant_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    bed_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = allocation_service.list_allocations(
        db,
        tenant_id=tenant_id,
        room_id=room_id,
        bed_id=bed_id,
        active_only=active_only,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=AllocationRead, status_code=status.HTTP_201_CREATED)
def create_allocation(
    payload: AllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> AllocationRead:
    return allocation_service.create_allocation(db, payload, actor_id=current_user.id)


@router.patch("/{allocation_id}/end", response_model=AllocationRead)
def end_allocation(
    allocation_id: uuid.UUID,
    payload: AllocationEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> AllocationRead:
    return allocation_service.end_allocation(db, allocation_id, payload.end_date, actor_id=current_user.id)
