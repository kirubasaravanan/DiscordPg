from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_current_tenant, page_params
from app.database.connection import get_db
from app.models import Tenant
from app.schemas.common import Page
from app.schemas.complaint import ComplaintCreate, ComplaintRead
from app.schemas.rent_ledger import RentLedgerRead
from app.schemas.tenant import TenantRead, TenantSelfUpdate
from app.services import complaint_service, rent_ledger_service, tenant_service

router = APIRouter()


@router.get("/profile", response_model=TenantRead)
def get_profile(current_tenant: Tenant = Depends(get_current_tenant)) -> TenantRead:
    return current_tenant


@router.patch("/profile", response_model=TenantRead)
def update_profile(
    payload: TenantSelfUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> TenantRead:
    return tenant_service.update_own_profile(db, current_tenant, payload)


@router.get("/rent", response_model=Page[RentLedgerRead])
def get_rent_history(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    # tenant_id always comes from the authenticated tenant, never a query
    # param — see docs/ARCHITECTURE.md §7.
    items, total = rent_ledger_service.list_rent_ledger(
        db,
        tenant_id=current_tenant.id,
        payment_status=None,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("/complaints", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
def file_complaint(
    payload: ComplaintCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ComplaintRead:
    return complaint_service.create_complaint(db, current_tenant.id, payload, actor_id=current_tenant.user_id)


@router.get("/complaints", response_model=Page[ComplaintRead])
def list_own_complaints(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = complaint_service.list_complaints(
        db,
        tenant_id=current_tenant.id,
        room_id=None,
        status=None,
        priority=None,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)
