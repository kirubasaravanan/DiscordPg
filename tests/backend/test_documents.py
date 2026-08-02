import datetime
import urllib.parse

from conftest import auth_headers


def _path_and_query(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.path}?{parsed.query}"


def test_full_tenant_document_lifecycle(client, tenant_with_user, owner_user):
    tenant, user = tenant_with_user

    # 1. Request an upload URL.
    upload_req = client.post("/api/v1/tenant/documents/upload-url", headers=auth_headers(user))
    assert upload_req.status_code == 200
    upload_body = upload_req.json()
    storage_key = upload_body["storage_key"]
    assert storage_key.startswith(f"tenants/{tenant.id}/")

    # 2. Actually upload bytes to it.
    file_bytes = b"this is a real uploaded id proof, not a fake stand-in"
    put_resp = client.put(_path_and_query(upload_body["upload_url"]), content=file_bytes)
    assert put_resp.status_code == 204

    # 3. Confirm/register the document.
    confirm = client.post(
        "/api/v1/tenant/documents",
        json={"document_type": "ID_PROOF", "storage_key": storage_key},
        headers=auth_headers(user),
    )
    assert confirm.status_code == 201
    document_id = confirm.json()["id"]
    assert confirm.json()["verification_status"] == "PENDING"
    assert "storage_url" not in confirm.json()

    # 4. It shows up in the tenant's own document list.
    listing = client.get("/api/v1/tenant/documents", headers=auth_headers(user))
    assert listing.status_code == 200
    assert any(d["id"] == document_id for d in listing.json()["items"])

    # 5. Get a download URL and actually download the bytes back.
    download_req = client.get(f"/api/v1/tenant/documents/{document_id}/download-url", headers=auth_headers(user))
    assert download_req.status_code == 200
    download_resp = client.get(_path_and_query(download_req.json()["download_url"]))
    assert download_resp.status_code == 200
    assert download_resp.content == file_bytes

    # 6. Staff/owner verifies it.
    verify = client.patch(
        f"/api/v1/documents/{document_id}/verify",
        json={"verification_status": "VERIFIED"},
        headers=auth_headers(owner_user),
    )
    assert verify.status_code == 200
    assert verify.json()["verification_status"] == "VERIFIED"


def test_confirm_without_upload_is_rejected(client, tenant_with_user):
    _, user = tenant_with_user
    upload_req = client.post("/api/v1/tenant/documents/upload-url", headers=auth_headers(user))
    storage_key = upload_req.json()["storage_key"]

    resp = client.post(
        "/api/v1/tenant/documents",
        json={"document_type": "ID_PROOF", "storage_key": storage_key},
        headers=auth_headers(user),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["field"] == "storage_key"


def test_confirm_with_another_tenants_storage_key_is_rejected(client, tenant_with_user, make_user, db_session):
    from app.models import Tenant, UserRole

    _, user_a = tenant_with_user
    upload_req = client.post("/api/v1/tenant/documents/upload-url", headers=auth_headers(user_a))
    storage_key_a = upload_req.json()["storage_key"]
    client.put(_path_and_query(upload_req.json()["upload_url"]), content=b"a's file")

    user_b = make_user(UserRole.TENANT)
    tenant_b = Tenant(name="Tenant B", phone="9666600001", joining_date=datetime.date(2026, 1, 1), user_id=user_b.id)
    db_session.add(tenant_b)
    db_session.flush()

    resp = client.post(
        "/api/v1/tenant/documents",
        json={"document_type": "ID_PROOF", "storage_key": storage_key_a},
        headers=auth_headers(user_b),
    )
    assert resp.status_code == 400
    assert "not issued to this tenant" in resp.json()["error"]["message"]


def test_non_tenant_cannot_request_upload_url(client, owner_user):
    resp = client.post("/api/v1/tenant/documents/upload-url", headers=auth_headers(owner_user))
    assert resp.status_code == 403


def test_tenant_cannot_get_download_url_for_another_tenants_document(
    client, tenant_with_user, make_user, db_session, manager_user
):
    from app.models import Document, Tenant, UserRole, VerificationStatus

    tenant_a, user_a = tenant_with_user
    doc = Document(tenant_id=tenant_a.id, document_type="ID_PROOF", storage_url="tenants/x/y", verification_status=VerificationStatus.PENDING)
    db_session.add(doc)
    db_session.flush()

    user_b = make_user(UserRole.TENANT)
    tenant_b = Tenant(name="Tenant B", phone="9666600002", joining_date=datetime.date(2026, 1, 1), user_id=user_b.id)
    db_session.add(tenant_b)
    db_session.flush()

    resp = client.get(f"/api/v1/tenant/documents/{doc.id}/download-url", headers=auth_headers(user_b))
    assert resp.status_code == 404


def test_staff_cannot_verify_document(client, staff_user, db_session, tenant):
    from app.models import Document, VerificationStatus

    doc = Document(tenant_id=tenant.id, document_type="AGREEMENT", storage_url="tenants/x/y", verification_status=VerificationStatus.PENDING)
    db_session.add(doc)
    db_session.flush()

    resp = client.patch(
        f"/api/v1/documents/{doc.id}/verify", json={"verification_status": "VERIFIED"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 403


def test_admin_lists_and_filters_documents_by_verification_status(client, staff_user, db_session, tenant):
    from app.models import Document, VerificationStatus

    db_session.add_all(
        [
            Document(tenant_id=tenant.id, document_type="ID_PROOF", storage_url="a", verification_status=VerificationStatus.PENDING),
            Document(tenant_id=tenant.id, document_type="PHOTO", storage_url="b", verification_status=VerificationStatus.VERIFIED),
        ]
    )
    db_session.flush()

    resp = client.get("/api/v1/documents?verification_status=PENDING", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert all(d["verification_status"] == "PENDING" for d in resp.json()["items"])


def test_admin_download_url_works_for_any_tenants_document(client, staff_user, db_session, tenant):
    from app.models import Document, VerificationStatus
    from app.storage.local import LocalFilesystemStorageBackend

    backend = LocalFilesystemStorageBackend()
    key = f"tenants/{tenant.id}/admin-view-test"
    backend.write(key, b"admin can see this")

    doc = Document(tenant_id=tenant.id, document_type="AGREEMENT", storage_url=key, verification_status=VerificationStatus.PENDING)
    db_session.add(doc)
    db_session.flush()

    resp = client.get(f"/api/v1/documents/{doc.id}/download-url", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    download = client.get(_path_and_query(resp.json()["download_url"]))
    assert download.content == b"admin can see this"
