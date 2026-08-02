import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import User, UserRole
from app.schemas.common import Page
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.services import tenant_service

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
WRITE_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[TenantRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_tenants(db: Session = Depends(get_db), pagination: PageParams = Depends(page_params)) -> Page:
    items, total = tenant_service.list_tenants(db, limit=pagination.page_size, offset=pagination.offset)
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> TenantRead:
    return tenant_service.create_tenant(db, payload, actor_id=current_user.id)


@router.get("/{tenant_id}", response_model=TenantRead, dependencies=[Depends(require_roles(*READ_ROLES))])
def get_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)) -> TenantRead:
    return tenant_service.get_tenant(db, tenant_id)


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
) -> TenantRead:
    return tenant_service.update_tenant(db, tenant_id, payload, actor_id=current_user.id)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OWNER)),
) -> None:
    tenant_service.delete_tenant(db, tenant_id, actor_id=current_user.id)
