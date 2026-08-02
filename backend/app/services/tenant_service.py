import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import conflict, not_found
from app.models import Allocation, Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate


def list_tenants(db: Session, *, limit: int, offset: int) -> tuple[list[Tenant], int]:
    query = db.query(Tenant).filter(Tenant.is_deleted.is_(False)).order_by(Tenant.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_tenant(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.is_deleted:
        raise not_found("Tenant not found.")
    return tenant


def create_tenant(db: Session, payload: TenantCreate, actor_id: uuid.UUID) -> Tenant:
    tenant = Tenant(**payload.model_dump(), created_by=actor_id)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update_tenant(db: Session, tenant_id: uuid.UUID, payload: TenantUpdate, actor_id: uuid.UUID) -> Tenant:
    tenant = get_tenant(db, tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    tenant.updated_by = actor_id
    db.commit()
    db.refresh(tenant)
    return tenant


def delete_tenant(db: Session, tenant_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    tenant = get_tenant(db, tenant_id)
    has_active_allocation = (
        db.query(Allocation).filter(Allocation.tenant_id == tenant_id, Allocation.end_date.is_(None)).first()
        is not None
    )
    if has_active_allocation:
        raise conflict("Cannot delete a tenant with an active allocation — end the allocation first.")
    tenant.is_deleted = True
    tenant.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    tenant.updated_by = actor_id
    db.commit()
