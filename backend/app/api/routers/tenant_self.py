from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_current_tenant, page_params
from app.database.connection import get_db
from app.models import Tenant
from app.schemas.common import Page
from app.schemas.rent_ledger import RentLedgerRead
from app.schemas.tenant import TenantRead
from app.services import rent_ledger_service

router = APIRouter()


@router.get("/profile", response_model=TenantRead)
def get_profile(current_tenant: Tenant = Depends(get_current_tenant)) -> TenantRead:
    return current_tenant


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
