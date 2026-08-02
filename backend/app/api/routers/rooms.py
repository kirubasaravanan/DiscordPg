import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.common import Page
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.services import room_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[RoomRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_rooms(
    building_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = room_service.list_rooms(db, building_id=building_id, limit=pagination.page_size, offset=pagination.offset)
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> RoomRead:
    return room_service.create_room(db, payload, actor_id=current_user.id)


@router.get("/{room_id}", response_model=RoomRead, dependencies=[Depends(require_roles(*READ_ROLES))])
def get_room(room_id: uuid.UUID, db: Session = Depends(get_db)) -> RoomRead:
    return room_service.get_room(db, room_id)


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: uuid.UUID,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> RoomRead:
    return room_service.update_room(db, room_id, payload, actor_id=current_user.id)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: uuid.UUID,
    db: Session = Depends(get_db),
    # Deliberately not WRITE_ROLES: per docs/API.md §5.2, DELETE is OWNER-only
    # even though POST/PATCH also allow MANAGER.
    current_user: User = Depends(require_roles(UserRole.OWNER)),
) -> None:
    room_service.delete_room(db, room_id, actor_id=current_user.id)
