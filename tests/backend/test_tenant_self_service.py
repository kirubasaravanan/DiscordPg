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


def test_update_own_profile(client, tenant_with_user):
    tenant, user = tenant_with_user
    resp = client.patch(
        "/api/v1/tenant/profile", json={"phone": "9555500001", "emergency_contact": "9555599999"}, headers=auth_headers(user)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == "9555500001"
    assert body["emergency_contact"] == "9555599999"
    assert body["name"] == tenant.name  # unaffected


def test_update_own_profile_cannot_set_status(client, tenant_with_user):
    _, user = tenant_with_user
    resp = client.patch("/api/v1/tenant/profile", json={"status": "EXITED"}, headers=auth_headers(user))
    # status isn't a field on TenantSelfUpdate at all — the extra key is silently ignored by
    # Pydantic's default config, not rejected; assert it had no effect rather than assuming 422.
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


def test_faq_returns_answer_and_citations(client, tenant_with_user, monkeypatch):
    _, user = tenant_with_user
    monkeypatch.setattr(
        "app.api.routers.tenant_self.rag_service.answer_faq",
        lambda db, question: {"answer": "Rent is due on the 5th.", "cited_sources": ["rent_policy.md"]},
    )

    resp = client.post("/api/v1/tenant/faq", json={"question": "When is rent due?"}, headers=auth_headers(user))

    assert resp.status_code == 200
    assert resp.json() == {"answer": "Rent is due on the 5th.", "cited_sources": ["rent_policy.md"]}


def test_faq_returns_503_when_ai_service_unavailable(client, tenant_with_user, monkeypatch):
    from app.services.ai_client import AIServiceError

    _, user = tenant_with_user

    def _raise(db, question):
        raise AIServiceError("ai_engine unreachable")

    monkeypatch.setattr("app.api.routers.tenant_self.rag_service.answer_faq", _raise)

    resp = client.post("/api/v1/tenant/faq", json={"question": "anything"}, headers=auth_headers(user))

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_faq_requires_tenant_role(client, staff_user):
    resp = client.post("/api/v1/tenant/faq", json={"question": "anything"}, headers=auth_headers(staff_user))
    assert resp.status_code == 403


def test_faq_rejects_empty_question(client, tenant_with_user):
    _, user = tenant_with_user
    resp = client.post("/api/v1/tenant/faq", json={"question": ""}, headers=auth_headers(user))
    assert resp.status_code == 422
