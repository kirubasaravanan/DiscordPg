from conftest import auth_headers


def test_tenant_can_file_complaint_without_category(client, tenant_with_user):
    tenant, user = tenant_with_user
    resp = client.post(
        "/api/v1/tenant/complaints", json={"description": "Bathroom tap is leaking"}, headers=auth_headers(user)
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "OTHER"
    assert body["priority"] == "MEDIUM"
    assert body["status"] == "OPEN"
    assert body["tenant_id"] == str(tenant.id)


def test_tenant_can_suggest_category(client, tenant_with_user):
    tenant, user = tenant_with_user
    resp = client.post(
        "/api/v1/tenant/complaints",
        json={"description": "Wi-Fi is down", "category": "WIFI"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["category"] == "WIFI"


def test_tenant_complaint_unknown_room_not_found(client, tenant_with_user):
    _, user = tenant_with_user
    resp = client.post(
        "/api/v1/tenant/complaints",
        json={"description": "x", "room_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 404


def test_non_tenant_cannot_file_complaint(client, owner_user):
    resp = client.post("/api/v1/tenant/complaints", json={"description": "x"}, headers=auth_headers(owner_user))
    assert resp.status_code == 403


def test_tenant_sees_only_own_complaints(client, db_session, tenant_with_user, make_user):
    from datetime import date

    from app.models import Tenant, UserRole

    tenant, user = tenant_with_user
    client.post("/api/v1/tenant/complaints", json={"description": "mine"}, headers=auth_headers(user))

    other_user = make_user(UserRole.TENANT)
    other_tenant = Tenant(name="Other", phone="9444400001", joining_date=date(2026, 1, 1), user_id=other_user.id)
    db_session.add(other_tenant)
    db_session.flush()
    client.post("/api/v1/tenant/complaints", json={"description": "not mine"}, headers=auth_headers(other_user))

    resp = client.get("/api/v1/tenant/complaints", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "mine"


def test_staff_can_list_and_view_complaint_queue(client, staff_user, tenant_with_user):
    _, user = tenant_with_user
    client.post("/api/v1/tenant/complaints", json={"description": "queue test"}, headers=auth_headers(user))

    resp = client.get("/api/v1/complaints", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_staff_can_resolve_complaint_sets_resolved_at(client, staff_user, tenant_with_user):
    _, user = tenant_with_user
    create = client.post(
        "/api/v1/tenant/complaints", json={"description": "fix me"}, headers=auth_headers(user)
    )
    complaint_id = create.json()["id"]

    resp = client.patch(
        f"/api/v1/complaints/{complaint_id}", json={"status": "RESOLVED"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESOLVED"
    assert resp.json()["resolved_at"] is not None


def test_reopening_complaint_clears_resolved_at(client, staff_user, tenant_with_user):
    _, user = tenant_with_user
    create = client.post("/api/v1/tenant/complaints", json={"description": "fix me"}, headers=auth_headers(user))
    complaint_id = create.json()["id"]
    client.patch(f"/api/v1/complaints/{complaint_id}", json={"status": "RESOLVED"}, headers=auth_headers(staff_user))

    resp = client.patch(
        f"/api/v1/complaints/{complaint_id}", json={"status": "REOPENED"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 200
    assert resp.json()["resolved_at"] is None


def test_closing_a_resolved_complaint_keeps_resolved_at(client, staff_user, tenant_with_user):
    _, user = tenant_with_user
    create = client.post("/api/v1/tenant/complaints", json={"description": "fix me"}, headers=auth_headers(user))
    complaint_id = create.json()["id"]
    resolved = client.patch(
        f"/api/v1/complaints/{complaint_id}", json={"status": "RESOLVED"}, headers=auth_headers(staff_user)
    )
    resolved_at = resolved.json()["resolved_at"]

    closed = client.patch(f"/api/v1/complaints/{complaint_id}", json={"status": "CLOSED"}, headers=auth_headers(staff_user))
    assert closed.status_code == 200
    assert closed.json()["resolved_at"] == resolved_at


def test_tenant_cannot_update_complaint_status(client, tenant_with_user):
    _, user = tenant_with_user
    create = client.post("/api/v1/tenant/complaints", json={"description": "x"}, headers=auth_headers(user))
    complaint_id = create.json()["id"]

    resp = client.patch(f"/api/v1/complaints/{complaint_id}", json={"status": "RESOLVED"}, headers=auth_headers(user))
    assert resp.status_code == 403


def test_list_complaints_filtered_by_status(client, staff_user, tenant_with_user):
    _, user = tenant_with_user
    client.post("/api/v1/tenant/complaints", json={"description": "one"}, headers=auth_headers(user))

    resp = client.get("/api/v1/complaints?status=OPEN", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert all(c["status"] == "OPEN" for c in resp.json()["items"])
