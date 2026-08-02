import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.building import BuildingCreate, BuildingRead, BuildingUpdate
from app.schemas.common import Page
from app.services import building_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER,)


@router.get("", response_model=Page[BuildingRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_buildings(db: Session = Depends(get_db), pagination: PageParams = Depends(page_params)) -> Page:
    items, total = building_service.list_buildings(db, limit=pagination.page_size, offset=pagination.offset)
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=BuildingRead, status_code=status.HTTP_201_CREATED)
def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> BuildingRead:
    return building_service.create_building(db, payload, actor_id=current_user.id)


@router.get("/{building_id}", response_model=BuildingRead, dependencies=[Depends(require_roles(*READ_ROLES))])
def get_building(building_id: uuid.UUID, db: Session = Depends(get_db)) -> BuildingRead:
    return building_service.get_building(db, building_id)


@router.patch("/{building_id}", response_model=BuildingRead)
def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> BuildingRead:
    return building_service.update_building(db, building_id, payload, actor_id=current_user.id)


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(
    building_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> None:
    building_service.delete_building(db, building_id, actor_id=current_user.id)
