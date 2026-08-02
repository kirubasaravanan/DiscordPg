import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import ComplaintStatus, Priority, User, UserRole
from app.schemas.common import Page
from app.schemas.complaint import ComplaintRead, ComplaintUpdate
from app.services import complaint_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
# STAFF can update (triage/resolve tickets) but there's no admin-side create —
# complaints only originate from a tenant filing one (POST /api/v1/tenant/complaints).
UPDATE_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)


@router.get("", response_model=Page[ComplaintRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_complaints(
    tenant_id: uuid.UUID | None = Query(None),
    room_id: uuid.UUID | None = Query(None),
    status: ComplaintStatus | None = Query(None),
    priority: Priority | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = complaint_service.list_complaints(
        db,
        tenant_id=tenant_id,
        room_id=room_id,
        status=status,
        priority=priority,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/{complaint_id}", response_model=ComplaintRead, dependencies=[Depends(require_roles(*READ_ROLES))])
def get_complaint(complaint_id: uuid.UUID, db: Session = Depends(get_db)) -> ComplaintRead:
    return complaint_service.get_complaint(db, complaint_id)


@router.patch("/{complaint_id}", response_model=ComplaintRead)
def update_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*UPDATE_ROLES)),
) -> ComplaintRead:
    return complaint_service.update_complaint(db, complaint_id, payload, actor_id=current_user.id)
