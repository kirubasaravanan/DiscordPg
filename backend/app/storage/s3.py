import boto3
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.storage.base import UploadTarget


class S3CompatibleStorageBackend:
    """Real Cloudflare R2 / AWS S3 backend via boto3 presigned URLs — the
    standard approach for both (R2 is deliberately S3-API-compatible;
    Cloudflare's own docs point at the AWS SDK with `endpoint_url` set to the
    account's R2 endpoint and `region_name="auto"`). Leave storage_s3_endpoint_url
    unset to talk to real AWS S3 instead.

    Not verified against a live bucket in this environment — see
    docs/ARCHITECTURE.md §12 for why, and what was verified instead.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if not settings.storage_s3_bucket:
            raise RuntimeError("storage_backend='s3' requires STORAGE_S3_BUCKET to be set.")
        self._bucket = settings.storage_s3_bucket
        self._expire_seconds = settings.storage_presigned_url_expire_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.storage_s3_endpoint_url,
            region_name=settings.storage_s3_region,
            aws_access_key_id=settings.storage_s3_access_key_id,
            aws_secret_access_key=settings.storage_s3_secret_access_key,
        )

    def generate_upload_target(self, storage_key: str) -> UploadTarget:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=self._expire_seconds,
        )
        return UploadTarget(upload_url=url, method="PUT", storage_key=storage_key, expires_in=self._expire_seconds)

    def generate_download_url(self, storage_key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=self._expire_seconds,
        )

    def object_exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=storage_key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                return False
            raise
