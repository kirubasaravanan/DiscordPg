import datetime

from conftest import auth_headers


def test_create_tenant_as_manager_succeeds(client, manager_user):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": "New Tenant", "phone": "9111100001", "joining_date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "ACTIVE"


def test_create_tenant_as_staff_forbidden(client, staff_user):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": "New Tenant", "phone": "9111100002", "joining_date": "2026-08-01"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_create_tenant_duplicate_phone_conflict(client, owner_user, tenant):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": "Duplicate", "phone": tenant.phone, "joining_date": "2026-08-01"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 409


def test_create_tenant_invalid_email_rejected(client, owner_user):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": "Bad Email", "phone": "9111100003", "email": "not-an-email", "joining_date": "2026-08-01"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 422


def test_list_tenants_as_staff_succeeds(client, staff_user, tenant):
    resp = client.get("/api/v1/tenants", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert any(t["id"] == str(tenant.id) for t in resp.json()["items"])


def test_get_tenant_not_found(client, owner_user):
    resp = client.get("/api/v1/tenants/00000000-0000-0000-0000-000000000000", headers=auth_headers(owner_user))
    assert resp.status_code == 404


def test_update_tenant_status_as_manager_succeeds(client, manager_user, tenant):
    resp = client.patch(
        f"/api/v1/tenants/{tenant.id}", json={"status": "NOTICE_PERIOD"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "NOTICE_PERIOD"


def test_delete_tenant_as_manager_forbidden(client, manager_user, tenant):
    resp = client.delete(f"/api/v1/tenants/{tenant.id}", headers=auth_headers(manager_user))
    assert resp.status_code == 403


def test_delete_tenant_as_owner_succeeds(client, owner_user, tenant):
    resp = client.delete(f"/api/v1/tenants/{tenant.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 204


def test_delete_tenant_with_active_allocation_conflict(client, owner_user, db_session, tenant, room, bed):
    from app.models import Allocation

    db_session.add(
        Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1))
    )
    db_session.flush()

    resp = client.delete(f"/api/v1/tenants/{tenant.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 409
