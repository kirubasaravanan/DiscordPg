import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.bed import BedCreate, BedRead, BedUpdate
from app.schemas.common import Page
from app.services import bed_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[BedRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_beds(
    room_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = bed_service.list_beds(db, room_id=room_id, limit=pagination.page_size, offset=pagination.offset)
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=BedRead, status_code=status.HTTP_201_CREATED)
def create_bed(
    payload: BedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> BedRead:
    return bed_service.create_bed(db, payload, actor_id=current_user.id)


@router.get("/{bed_id}", response_model=BedRead, dependencies=[Depends(require_roles(*READ_ROLES))])
def get_bed(bed_id: uuid.UUID, db: Session = Depends(get_db)) -> BedRead:
    return bed_service.get_bed(db, bed_id)


@router.patch("/{bed_id}", response_model=BedRead)
def update_bed(
    bed_id: uuid.UUID,
    payload: BedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> BedRead:
    return bed_service.update_bed(db, bed_id, payload, actor_id=current_user.id)


@router.delete("/{bed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bed(
    bed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OWNER)),
) -> None:
    bed_service.delete_bed(db, bed_id, actor_id=current_user.id)
