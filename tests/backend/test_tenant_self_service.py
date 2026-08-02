import datetime

from conftest import auth_headers


def test_get_own_profile(client, tenant_with_user):
    tenant, user = tenant_with_user
    resp = client.get("/api/v1/tenant/profile", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(tenant.id)


def test_profile_requires_tenant_role(client, owner_user):
    resp = client.get("/api/v1/tenant/profile", headers=auth_headers(owner_user))
    assert resp.status_code == 403


def test_profile_forbidden_for_tenant_role_with_no_linked_tenant(client, make_user):
    from app.models import UserRole

    unlinked_user = make_user(UserRole.TENANT)
    resp = client.get("/api/v1/tenant/profile", headers=auth_headers(unlinked_user))
    assert resp.status_code == 403


def test_get_own_rent_history(client, db_session, tenant_with_user, manager_user):
    tenant, user = tenant_with_user
    client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )

    resp = client.get("/api/v1/tenant/rent", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tenant_id"] == str(tenant.id)


def test_tenant_cannot_see_another_tenants_rent(client, db_session, tenant_with_user, manager_user, make_user):
    from app.models import Tenant, UserRole

    tenant, user = tenant_with_user

    other_user = make_user(UserRole.TENANT)
    other_tenant = Tenant(
        name="Other Tenant", phone="9333300001", joining_date=datetime.date(2026, 1, 1), user_id=other_user.id
    )
    db_session.add(other_tenant)
    db_session.flush()

    client.post(
        "/api/v1/rent",
        json={
            "tenant_id": str(other_tenant.id),
            "month": "2026-08-01",
            "rent_amount": "12000.00",
            "due_date": "2026-08-05",
        },
        headers=auth_headers(manager_user),
    )

    resp = client.get("/api/v1/tenant/rent", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0
