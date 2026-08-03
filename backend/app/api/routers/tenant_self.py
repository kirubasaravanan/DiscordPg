import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_current_tenant, page_params
from app.api.errors import service_unavailable
from app.config import get_settings
from app.database.connection import get_db
from app.models import Tenant
from app.schemas.common import Page
from app.schemas.complaint import ComplaintCreate, ComplaintRead
from app.schemas.document import DocumentCreate, DocumentRead, DownloadURLResponse, UploadURLResponse
from app.schemas.faq import FAQRequest, FAQResponse
from app.schemas.rent_ledger import RentLedgerRead
from app.schemas.tenant import TenantRead, TenantSelfUpdate
from app.services import ai_client, complaint_service, document_service, rag_service, rent_ledger_service, tenant_service
from app.storage import StorageBackend, get_storage_backend

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


@router.post("/faq", response_model=FAQResponse)
def ask_faq(
    payload: FAQRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """docs/AI_DESIGN.md §3. Unlike complaint classification, there's no
    sensible non-AI fallback for "answer this question" — if ai_engine is
    unreachable, this surfaces a clear 503 rather than a fake answer.
    """
    del current_tenant  # only used for the auth/scoping check via the dependency
    try:
        return rag_service.answer_faq(db, payload.question)
    except ai_client.AIServiceError as exc:
        raise service_unavailable("The FAQ assistant is temporarily unavailable. Please try again later.") from exc


@router.post("/documents/upload-url", response_model=UploadURLResponse)
def request_document_upload_url(
    current_tenant: Tenant = Depends(get_current_tenant),
    storage: StorageBackend = Depends(get_storage_backend),
) -> UploadURLResponse:
    target = document_service.request_upload_url(storage, current_tenant.id)
    return UploadURLResponse(
        storage_key=target.storage_key,
        upload_url=target.upload_url,
        method=target.method,
        expires_in=target.expires_in,
    )


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def register_document(
    payload: DocumentCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> DocumentRead:
    return document_service.create_document(
        db, storage, current_tenant.id, payload, actor_id=current_tenant.user_id
    )


@router.get("/documents", response_model=Page[DocumentRead])
def list_own_documents(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = document_service.list_documents(
        db,
        tenant_id=current_tenant.id,
        verification_status=None,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get("/documents/{document_id}/download-url", response_model=DownloadURLResponse)
def get_own_document_download_url(
    document_id: uuid.UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> DownloadURLResponse:
    document = document_service.get_own_document(db, document_id, current_tenant.id)
    url = storage.generate_download_url(document.storage_url)
    return DownloadURLResponse(download_url=url, expires_in=get_settings().storage_presigned_url_expire_seconds)
