import pytest
from conftest import auth_headers

from app.services import ai_client


@pytest.fixture
def ai_classifier_unavailable(monkeypatch):
    """Forces the Phase 6 classifier's unreachable-ai_engine path
    deterministically — regardless of whatever happens to be listening on
    AI_ENGINE_URL in this environment right now (see docs/AI_DESIGN.md §7,
    docs/ARCHITECTURE.md §12 item 27: no live Ollama/ai_engine is assumed
    reachable in general, but a stray dev process shouldn't make this test
    flaky either way).
    """

    def _raise(description):
        del description
        raise ai_client.AIServiceError("ai_engine unreachable (forced for this test)")

    monkeypatch.setattr("app.services.complaint_service.ai_client.classify_complaint", _raise)


def test_tenant_can_file_complaint_without_category(client, tenant_with_user, ai_classifier_unavailable):
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
    assert body["suggested_action"] is None


def test_tenant_can_suggest_category_when_ai_unavailable(client, tenant_with_user, ai_classifier_unavailable):
    tenant, user = tenant_with_user
    resp = client.post(
        "/api/v1/tenant/complaints",
        json={"description": "Wi-Fi is down", "category": "WIFI"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    assert resp.json()["category"] == "WIFI"


def test_classifier_output_is_used_when_valid(client, tenant_with_user, monkeypatch):
    _tenant, user = tenant_with_user
    monkeypatch.setattr(
        "app.services.complaint_service.ai_client.classify_complaint",
        lambda description: {"category": "PLUMBING", "priority": "HIGH", "suggested_action": "Send a plumber."},
    )

    resp = client.post(
        "/api/v1/tenant/complaints",
        json={"description": "The tap is leaking", "category": "OTHER"},
        headers=auth_headers(user),
    )

    assert resp.status_code == 201
    body = resp.json()
    # Classifier's real output wins over the tenant's own guess.
    assert body["category"] == "PLUMBING"
    assert body["priority"] == "HIGH"
    assert body["suggested_action"] == "Send a plumber."


def test_classifier_invalid_category_falls_back_to_suggestion(client, tenant_with_user, monkeypatch):
    """A hallucinated/invalid category degrades to the tenant's own
    suggestion (or OTHER) — the service layer clamps it, per
    docs/ARCHITECTURE.md §5 item 5. Priority, which the model got right in
    this response, is still honored — one bad field doesn't discard the rest.
    """
    _tenant, user = tenant_with_user
    monkeypatch.setattr(
        "app.services.complaint_service.ai_client.classify_complaint",
        lambda description: {"category": "NOT_A_REAL_CATEGORY", "priority": "HIGH", "suggested_action": "Investigate."},
    )

    resp = client.post(
        "/api/v1/tenant/complaints",
        json={"description": "Something's wrong", "category": "WIFI"},
        headers=auth_headers(user),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "WIFI"  # fell back to the tenant's suggestion
    assert body["priority"] == "HIGH"  # still honored — it was valid
    assert body["suggested_action"] == "Investigate."


def test_classifier_invalid_priority_falls_back_to_medium(client, tenant_with_user, monkeypatch):
    _tenant, user = tenant_with_user
    monkeypatch.setattr(
        "app.services.complaint_service.ai_client.classify_complaint",
        lambda description: {"category": "PLUMBING", "priority": "CATASTROPHIC", "suggested_action": "Send someone."},
    )

    resp = client.post(
        "/api/v1/tenant/complaints", json={"description": "The tap is leaking"}, headers=auth_headers(user)
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "PLUMBING"
    assert body["priority"] == "MEDIUM"  # invalid value clamped to the default


def test_classifier_blank_suggested_action_is_stored_as_null(client, tenant_with_user, monkeypatch):
    _tenant, user = tenant_with_user
    monkeypatch.setattr(
        "app.services.complaint_service.ai_client.classify_complaint",
        lambda description: {"category": "PLUMBING", "priority": "HIGH", "suggested_action": "   "},
    )

    resp = client.post(
        "/api/v1/tenant/complaints", json={"description": "The tap is leaking"}, headers=auth_headers(user)
    )

    assert resp.status_code == 201
    assert resp.json()["suggested_action"] is None


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
