from conftest import auth_headers


def test_create_user_as_owner_succeeds(client, owner_user):
    resp = client.post(
        "/api/v1/users",
        json={"email": "newstaff@test.com", "password": "Sup3r-Secret!", "role": "STAFF"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "STAFF"
    assert "password" not in body
    assert "password_hash" not in body


def test_create_user_as_manager_forbidden(client, manager_user):
    resp = client.post(
        "/api/v1/users",
        json={"email": "newstaff2@test.com", "password": "Sup3r-Secret!", "role": "STAFF"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 403


def test_create_user_short_password_rejected(client, owner_user):
    resp = client.post(
        "/api/v1/users", json={"email": "x@test.com", "password": "short", "role": "STAFF"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 422


def test_new_user_can_log_in(client, owner_user):
    client.post(
        "/api/v1/users",
        json={"email": "loginable@test.com", "password": "Sup3r-Secret!", "role": "MANAGER"},
        headers=auth_headers(owner_user),
    )
    resp = client.post("/api/v1/auth/login", json={"identifier": "loginable@test.com", "password": "Sup3r-Secret!"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "MANAGER"


def test_list_users_as_staff_forbidden(client, staff_user):
    resp = client.get("/api/v1/users", headers=auth_headers(staff_user))
    assert resp.status_code == 403


def test_update_user_role_as_owner_succeeds(client, owner_user, staff_user):
    resp = client.patch(f"/api/v1/users/{staff_user.id}", json={"role": "MANAGER"}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    assert resp.json()["role"] == "MANAGER"


def test_deactivate_user(client, owner_user, staff_user):
    resp = client.patch(f"/api/v1/users/{staff_user.id}", json={"is_active": False}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_deactivated_user_cannot_log_in(client, owner_user, make_user):
    from app.models import UserRole

    victim = make_user(UserRole.STAFF, email="victim@test.com", password="Sup3r-Secret!")
    client.patch(f"/api/v1/users/{victim.id}", json={"is_active": False}, headers=auth_headers(owner_user))

    resp = client.post("/api/v1/auth/login", json={"identifier": "victim@test.com", "password": "Sup3r-Secret!"})
    assert resp.status_code == 401


def test_cannot_demote_the_last_owner(client, owner_user):
    resp = client.patch(f"/api/v1/users/{owner_user.id}", json={"role": "MANAGER"}, headers=auth_headers(owner_user))
    assert resp.status_code == 409


def test_cannot_deactivate_the_last_owner(client, owner_user):
    resp = client.patch(f"/api/v1/users/{owner_user.id}", json={"is_active": False}, headers=auth_headers(owner_user))
    assert resp.status_code == 409


def test_can_demote_owner_when_another_owner_remains(client, owner_user, make_user):
    from app.models import UserRole

    make_user(UserRole.OWNER)  # a second owner

    resp = client.patch(f"/api/v1/users/{owner_user.id}", json={"role": "MANAGER"}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    assert resp.json()["role"] == "MANAGER"


def test_update_user_password_allows_new_login(client, owner_user, staff_user):
    resp = client.patch(
        f"/api/v1/users/{staff_user.id}", json={"password": "New-Sup3r-Secret!"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200

    login = client.post(
        "/api/v1/auth/login", json={"identifier": staff_user.email, "password": "New-Sup3r-Secret!"}
    )
    assert login.status_code == 200
