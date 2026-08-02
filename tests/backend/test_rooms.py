from conftest import auth_headers


def test_create_room_as_manager_succeeds(client, manager_user, building):
    resp = client.post(
        "/api/v1/rooms",
        json={"building_id": str(building.id), "room_number": "301", "floor": 3, "capacity": 2},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "AVAILABLE"


def test_create_room_as_staff_forbidden(client, staff_user, building):
    resp = client.post(
        "/api/v1/rooms",
        json={"building_id": str(building.id), "room_number": "301", "capacity": 2},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_create_room_unknown_building_not_found(client, owner_user):
    resp = client.post(
        "/api/v1/rooms",
        json={"building_id": "00000000-0000-0000-0000-000000000000", "room_number": "301", "capacity": 2},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 404


def test_create_room_duplicate_number_in_building_conflict(client, owner_user, building, room):
    resp = client.post(
        "/api/v1/rooms",
        json={"building_id": str(building.id), "room_number": room.room_number, "capacity": 3},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_create_room_invalid_capacity_rejected(client, owner_user, building):
    resp = client.post(
        "/api/v1/rooms",
        json={"building_id": str(building.id), "room_number": "302", "capacity": 0},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_room_status_full_rejected(client, owner_user, room):
    resp = client.patch(f"/api/v1/rooms/{room.id}", json={"status": "FULL"}, headers=auth_headers(owner_user))
    assert resp.status_code == 400
    assert resp.json()["error"]["field"] == "status"


def test_update_room_status_maintenance_allowed(client, owner_user, room):
    resp = client.patch(f"/api/v1/rooms/{room.id}", json={"status": "MAINTENANCE"}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "MAINTENANCE"


def test_delete_room_as_manager_forbidden(client, manager_user, room):
    resp = client.delete(f"/api/v1/rooms/{room.id}", headers=auth_headers(manager_user))
    assert resp.status_code == 403


def test_delete_room_as_owner_succeeds(client, owner_user, room):
    resp = client.delete(f"/api/v1/rooms/{room.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 204


def test_delete_room_with_active_beds_conflict(client, owner_user, room, bed):
    resp = client.delete(f"/api/v1/rooms/{room.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 409


def test_list_rooms_filtered_by_building(client, staff_user, building, room):
    resp = client.get(f"/api/v1/rooms?building_id={building.id}", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["building_id"] == str(building.id) for r in body["items"])
    assert any(r["id"] == str(room.id) for r in body["items"])
