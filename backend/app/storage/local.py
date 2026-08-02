import pathlib

from app.config import get_settings
from app.security.jwt import StorageTokenAction, create_storage_token
from app.storage.base import UploadTarget


class LocalFilesystemStorageBackend:
    """Dev/test default. A real, working analog of presigned URLs — not a
    stub — via signed, key-scoped, time-limited tokens consumed by this same
    app's own /internal/storage/* routes (app/api/routers/internal_storage.py).
    Only mounted when settings.storage_backend == "local".
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_dir = pathlib.Path(settings.storage_local_path).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._base_url = settings.storage_local_base_url.rstrip("/")
        self._expire_seconds = settings.storage_presigned_url_expire_seconds

    def generate_upload_target(self, storage_key: str) -> UploadTarget:
        token = create_storage_token(storage_key, StorageTokenAction.UPLOAD, self._expire_seconds)
        url = f"{self._base_url}/internal/storage/{storage_key}?token={token}"
        return UploadTarget(upload_url=url, method="PUT", storage_key=storage_key, expires_in=self._expire_seconds)

    def generate_download_url(self, storage_key: str) -> str:
        token = create_storage_token(storage_key, StorageTokenAction.DOWNLOAD, self._expire_seconds)
        return f"{self._base_url}/internal/storage/{storage_key}?token={token}"

    def object_exists(self, storage_key: str) -> bool:
        return self._path_for(storage_key).is_file()

    def write(self, storage_key: str, data: bytes) -> None:
        path = self._path_for(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, storage_key: str) -> bytes:
        return self._path_for(storage_key).read_bytes()

    def _path_for(self, storage_key: str) -> pathlib.Path:
        candidate = (self._base_dir / storage_key).resolve()
        if candidate != self._base_dir and self._base_dir not in candidate.parents:
            raise ValueError(f"Storage key resolves outside the storage root: {storage_key!r}")
        return candidate
