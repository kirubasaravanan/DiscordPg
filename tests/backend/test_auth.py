from app.models import UserRole
from app.security.jwt import decode_token


def test_login_success(client, make_user):
    make_user(UserRole.OWNER, email="owner@test.com", password="Sup3r-Secret!")

    resp = client.post("/api/v1/auth/login", json={"identifier": "owner@test.com", "password": "Sup3r-Secret!"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "OWNER"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert decode_token(body["access_token"])["type"] == "access"
    assert decode_token(body["refresh_token"])["type"] == "refresh"


def test_login_via_phone_identifier(client, make_user):
    make_user(UserRole.STAFF, email="staff@test.com", password="Sup3r-Secret!", phone="9999900001")

    resp = client.post("/api/v1/auth/login", json={"identifier": "9999900001", "password": "Sup3r-Secret!"})

    assert resp.status_code == 200


def test_login_wrong_password(client, make_user):
    make_user(UserRole.OWNER, email="owner2@test.com", password="Sup3r-Secret!")

    resp = client.post("/api/v1/auth/login", json={"identifier": "owner2@test.com", "password": "wrong"})

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_identifier(client):
    resp = client.post("/api/v1/auth/login", json={"identifier": "nobody@test.com", "password": "whatever"})
    assert resp.status_code == 401


def test_login_inactive_user_rejected(client, make_user):
    make_user(UserRole.STAFF, email="inactive@test.com", password="Sup3r-Secret!", is_active=False)

    resp = client.post("/api/v1/auth/login", json={"identifier": "inactive@test.com", "password": "Sup3r-Secret!"})

    assert resp.status_code == 401


def test_refresh_issues_new_access_token(client, make_user):
    make_user(UserRole.MANAGER, email="mgr@test.com", password="Sup3r-Secret!")
    login = client.post("/api/v1/auth/login", json={"identifier": "mgr@test.com", "password": "Sup3r-Secret!"})
    refresh_token = login.json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert resp.status_code == 200
    assert decode_token(resp.json()["access_token"])["type"] == "access"


def test_refresh_rejects_access_token(client, make_user):
    make_user(UserRole.MANAGER, email="mgr2@test.com", password="Sup3r-Secret!")
    login = client.post("/api/v1/auth/login", json={"identifier": "mgr2@test.com", "password": "Sup3r-Secret!"})
    access_token = login.json()["access_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert resp.status_code == 401


def test_logout_revokes_outstanding_refresh_tokens(client, make_user):
    make_user(UserRole.OWNER, email="owner3@test.com", password="Sup3r-Secret!")
    login = client.post("/api/v1/auth/login", json={"identifier": "owner3@test.com", "password": "Sup3r-Secret!"})
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]

    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_resp.status_code == 204

    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
    assert "revoked" in refresh_resp.json()["error"]["message"].lower()


def test_logout_requires_bearer_token(client):
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_logout_rejects_malformed_token(client):
    resp = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
