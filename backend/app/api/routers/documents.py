import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.config import get_settings
from app.database.connection import get_db
from app.models import User, UserRole, VerificationStatus
from app.schemas.common import Page
from app.schemas.document import DocumentRead, DocumentVerify, DownloadURLResponse
from app.services import document_service
from app.storage import StorageBackend, get_storage_backend

router = APIRouter()

READ_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
VERIFY_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[DocumentRead], dependencies=[Depends(require_roles(*READ_ROLES))])
def list_documents(
    tenant_id: uuid.UUID | None = Query(None),
    verification_status: VerificationStatus | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = document_service.list_documents(
        db,
        tenant_id=tenant_id,
        verification_status=verification_status,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.get(
    "/{document_id}/download-url",
    response_model=DownloadURLResponse,
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_download_url(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> DownloadURLResponse:
    document = document_service.get_document(db, document_id)
    url = storage.generate_download_url(document.storage_url)
    return DownloadURLResponse(download_url=url, expires_in=get_settings().storage_presigned_url_expire_seconds)


@router.patch("/{document_id}/verify", response_model=DocumentRead)
def verify_document(
    document_id: uuid.UUID,
    payload: DocumentVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*VERIFY_ROLES)),
) -> DocumentRead:
    return document_service.verify_document(db, document_id, payload.verification_status, actor_id=current_user.id)
