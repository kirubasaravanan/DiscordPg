import urllib.parse

import pytest

from app.security.jwt import StorageTokenAction, create_storage_token
from app.storage.local import LocalFilesystemStorageBackend


def _path_and_query(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(url)
    return parsed.path, parsed.query


def test_upload_then_download_round_trip(client):
    backend = LocalFilesystemStorageBackend()
    key = "tests/roundtrip-1"
    target = backend.generate_upload_target(key)
    path, query = _path_and_query(target.upload_url)

    put_resp = client.put(f"{path}?{query}", content=b"hello from a real upload")
    assert put_resp.status_code == 204

    download_url = backend.generate_download_url(key)
    dpath, dquery = _path_and_query(download_url)
    get_resp = client.get(f"{dpath}?{dquery}")
    assert get_resp.status_code == 200
    assert get_resp.content == b"hello from a real upload"


def test_download_before_upload_is_404(client):
    backend = LocalFilesystemStorageBackend()
    key = "tests/never-uploaded"
    download_url = backend.generate_download_url(key)
    path, query = _path_and_query(download_url)

    resp = client.get(f"{path}?{query}")
    assert resp.status_code == 404


def test_download_token_cannot_be_used_to_upload(client):
    backend = LocalFilesystemStorageBackend()
    key = "tests/wrong-action"
    download_url = backend.generate_download_url(key)  # a DOWNLOAD-scoped token
    path, query = _path_and_query(download_url)

    resp = client.put(f"{path}?{query}", content=b"should not be allowed")
    assert resp.status_code == 401


def test_token_for_one_key_cannot_be_replayed_against_another(client):
    backend = LocalFilesystemStorageBackend()
    target = backend.generate_upload_target("tests/key-a")
    _, query = _path_and_query(target.upload_url)

    # Reuse key-a's valid token, but hit the endpoint for a different path.
    resp = client.put(f"/internal/storage/tests/key-b?{query}", content=b"sneaky")
    assert resp.status_code == 401


def test_expired_token_is_rejected(client):
    token = create_storage_token("tests/expired", StorageTokenAction.UPLOAD, expire_seconds=-10)
    resp = client.put(f"/internal/storage/tests/expired?token={token}", content=b"too late")
    assert resp.status_code == 401


def test_malformed_token_is_rejected(client):
    resp = client.put("/internal/storage/tests/whatever?token=not-a-real-token", content=b"x")
    assert resp.status_code == 401


def test_path_traversal_key_is_rejected_by_backend_directly():
    backend = LocalFilesystemStorageBackend()
    with pytest.raises(ValueError):
        backend.write("../../etc/passwd", b"malicious")
