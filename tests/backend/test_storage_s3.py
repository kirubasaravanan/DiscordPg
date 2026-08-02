"""Tests the parts of S3CompatibleStorageBackend that don't require actually
consuming a presigned URL over HTTP — object_exists() against a real (moto-
mocked) bucket via direct boto3 calls, and that generated URLs reference the
correct bucket/key. Consuming the presigned URL itself via a raw HTTP client
was tried and does not work reliably in this environment: moto's `mock_aws`
intercepts boto3/botocore calls directly, but this sandbox's own HTTPS_PROXY
takes an httpx request to a presigned https://*.amazonaws.com URL before
moto's interception applies, producing a 403 unrelated to the actual code.
Not a gap in the implementation — see docs/ARCHITECTURE.md §12.
"""

import urllib.parse

import boto3
import pytest
from moto import mock_aws

from app.config import Settings
from app.storage.s3 import S3CompatibleStorageBackend

TEST_BUCKET = "pgos-test-bucket"


def _test_settings(**overrides) -> Settings:
    defaults = {
        "storage_backend": "s3",
        "storage_s3_bucket": TEST_BUCKET,
        "storage_s3_region": "us-east-1",
        "storage_s3_endpoint_url": None,
        "storage_s3_access_key_id": "testing",
        "storage_s3_secret_access_key": "testing",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def moto_bucket():
    with mock_aws():
        client = boto3.client(
            "s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing"
        )
        client.create_bucket(Bucket=TEST_BUCKET)
        yield client


def test_missing_bucket_config_raises_clear_error(moto_bucket):
    with pytest.raises(RuntimeError, match="STORAGE_S3_BUCKET"):
        S3CompatibleStorageBackend(settings=_test_settings(storage_s3_bucket=None))


def test_object_exists_reflects_real_bucket_state(moto_bucket):
    backend = S3CompatibleStorageBackend(settings=_test_settings())

    assert backend.object_exists("some/key") is False

    moto_bucket.put_object(Bucket=TEST_BUCKET, Key="some/key", Body=b"data")
    assert backend.object_exists("some/key") is True


def test_generate_upload_target_references_correct_bucket_and_key(moto_bucket):
    backend = S3CompatibleStorageBackend(settings=_test_settings())
    target = backend.generate_upload_target("docs/tenant-123/file.pdf")

    assert target.method == "PUT"
    assert target.storage_key == "docs/tenant-123/file.pdf"
    assert target.expires_in == 900  # Settings.storage_presigned_url_expire_seconds default
    parsed = urllib.parse.urlsplit(target.upload_url)
    assert parsed.scheme == "https"
    assert TEST_BUCKET in target.upload_url
    assert "docs/tenant-123/file.pdf" in target.upload_url


def test_generate_download_url_references_correct_bucket_and_key(moto_bucket):
    backend = S3CompatibleStorageBackend(settings=_test_settings())
    url = backend.generate_download_url("docs/tenant-123/file.pdf")

    assert TEST_BUCKET in url
    assert "docs/tenant-123/file.pdf" in url
