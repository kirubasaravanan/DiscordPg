from functools import lru_cache

from app.config import get_settings
from app.storage.base import StorageBackend, UploadTarget

__all__ = ["StorageBackend", "UploadTarget", "get_storage_backend"]


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.storage.s3 import S3CompatibleStorageBackend

        return S3CompatibleStorageBackend()

    from app.storage.local import LocalFilesystemStorageBackend

    return LocalFilesystemStorageBackend()
