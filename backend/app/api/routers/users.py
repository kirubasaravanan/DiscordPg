import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter()

ROLES = (UserRole.OWNER,)


@router.get("", response_model=Page[UserRead], dependencies=[Depends(require_roles(*ROLES))])
def list_users(db: Session = Depends(get_db), pagination: PageParams = Depends(page_params)) -> Page:
    items, total = user_service.list_users(db, limit=pagination.page_size, offset=pagination.offset)
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> UserRead:
    return user_service.create_user(db, payload, actor_id=current_user.id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> UserRead:
    return user_service.update_user(db, user_id, payload, actor_id=current_user.id)
