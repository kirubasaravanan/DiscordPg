import uuid

from sqlalchemy.orm import Session

from app.api.errors import bad_request, not_found
from app.models import Document, VerificationStatus
from app.schemas.document import DocumentCreate
from app.storage import StorageBackend, UploadTarget


def request_upload_url(storage: StorageBackend, tenant_id: uuid.UUID) -> UploadTarget:
    storage_key = f"tenants/{tenant_id}/{uuid.uuid4()}"
    return storage.generate_upload_target(storage_key)


def create_document(
    db: Session,
    storage: StorageBackend,
    tenant_id: uuid.UUID,
    payload: DocumentCreate,
    actor_id: uuid.UUID,
) -> Document:
    # storage_key is client-echoed from request_upload_url's response, so it's
    # not implicitly trustworthy — confirm it was actually issued for this
    # tenant (defense in depth against replaying someone else's key) and that
    # something was actually uploaded there (not just claimed).
    expected_prefix = f"tenants/{tenant_id}/"
    if not payload.storage_key.startswith(expected_prefix):
        raise bad_request("storage_key was not issued to this tenant.", field="storage_key")
    if not storage.object_exists(payload.storage_key):
        raise bad_request(
            "Nothing has been uploaded to this storage_key yet — upload the file to the URL from "
            "the upload-url endpoint before confirming.",
            field="storage_key",
        )

    document = Document(
        tenant_id=tenant_id,
        document_type=payload.document_type,
        storage_url=payload.storage_key,
        verification_status=VerificationStatus.PENDING,
        created_by=actor_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    verification_status: VerificationStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    query = db.query(Document).filter(Document.is_deleted.is_(False))
    if tenant_id is not None:
        query = query.filter(Document.tenant_id == tenant_id)
    if verification_status is not None:
        query = query.filter(Document.verification_status == verification_status)
    query = query.order_by(Document.created_at.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.is_deleted:
        raise not_found("Document not found.")
    return document


def get_own_document(db: Session, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
    """404s (not 403) if the document exists but belongs to someone else —
    same "don't confirm existence" reasoning as auth_service's login errors.
    """
    document = get_document(db, document_id)
    if document.tenant_id != tenant_id:
        raise not_found("Document not found.")
    return document


def verify_document(
    db: Session, document_id: uuid.UUID, verification_status: VerificationStatus, actor_id: uuid.UUID
) -> Document:
    document = get_document(db, document_id)
    document.verification_status = verification_status
    document.updated_by = actor_id
    db.commit()
    db.refresh(document)
    return document
