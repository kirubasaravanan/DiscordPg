from conftest import auth_headers


def test_get_rules_returns_content(client, tenant_with_user):
    _tenant, user = tenant_with_user

    resp = client.get("/api/v1/rules", headers=auth_headers(user))

    assert resp.status_code == 200
    content = resp.json()["content"]
    assert isinstance(content, str)
    assert "Rent" in content


def test_get_rules_accessible_to_staff_roles_too(client, owner_user):
    resp = client.get("/api/v1/rules", headers=auth_headers(owner_user))
    assert resp.status_code == 200


def test_get_rules_requires_auth(client):
    resp = client.get("/api/v1/rules")
    assert resp.status_code == 401
