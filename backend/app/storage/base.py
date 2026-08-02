from dataclasses import dataclass
from typing import Protocol


@dataclass
class UploadTarget:
    upload_url: str
    method: str
    storage_key: str
    expires_in: int


class StorageBackend(Protocol):
    """Backend-agnostic contract app/services/document_service.py depends on.

    Key naming (e.g. namespacing by tenant) is the caller's job, not the
    backend's — a backend only knows how to turn a given key into a URL, or
    check whether something exists at it.
    """

    def generate_upload_target(self, storage_key: str) -> UploadTarget: ...

    def generate_download_url(self, storage_key: str) -> str: ...

    def object_exists(self, storage_key: str) -> bool: ...
