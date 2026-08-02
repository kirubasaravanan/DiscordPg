import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models import DocumentType, VerificationStatus


class UploadURLResponse(BaseModel):
    storage_key: str
    upload_url: str
    method: str
    expires_in: int


class DocumentCreate(BaseModel):
    document_type: DocumentType
    storage_key: str


class DocumentVerify(BaseModel):
    verification_status: VerificationStatus


class DocumentRead(BaseModel):
    """storage_url is deliberately not exposed — it's an internal storage key,
    not something a client should use directly. Use the download-url
    endpoints to get a fresh, time-limited link instead.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_type: DocumentType
    verification_status: VerificationStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime | None


class DownloadURLResponse(BaseModel):
    download_url: str
    expires_in: int
