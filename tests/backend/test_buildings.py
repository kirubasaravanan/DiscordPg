from conftest import auth_headers


def test_create_building_as_owner_succeeds(client, owner_user):
    resp = client.post(
        "/api/v1/buildings",
        json={"name": "New PG", "address": "5 New Street"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "New PG"
    assert body["id"]


def test_create_building_as_manager_forbidden(client, manager_user):
    resp = client.post(
        "/api/v1/buildings", json={"name": "New PG"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_create_building_requires_auth(client):
    resp = client.post("/api/v1/buildings", json={"name": "New PG"})
    assert resp.status_code == 401


def test_list_buildings_as_staff_succeeds(client, staff_user, building):
    resp = client.get("/api/v1/buildings", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(b["id"] == str(building.id) for b in body["items"])


def test_get_building_not_found(client, owner_user):
    resp = client.get("/api/v1/buildings/00000000-0000-0000-0000-000000000000", headers=auth_headers(owner_user))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_update_building_as_owner_succeeds(client, owner_user, building):
    resp = client.patch(
        f"/api/v1/buildings/{building.id}", json={"name": "Renamed PG"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed PG"


def test_delete_building_as_owner_succeeds(client, owner_user, building):
    resp = client.delete(f"/api/v1/buildings/{building.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 204

    follow_up = client.get(f"/api/v1/buildings/{building.id}", headers=auth_headers(owner_user))
    assert follow_up.status_code == 404


def test_delete_building_with_active_rooms_conflict(client, owner_user, building, room):
    resp = client.delete(f"/api/v1/buildings/{building.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"
