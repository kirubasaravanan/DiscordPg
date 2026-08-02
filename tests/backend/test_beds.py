from conftest import auth_headers


def test_create_bed_as_manager_succeeds(client, manager_user, room):
    resp = client.post(
        "/api/v1/beds", json={"room_id": str(room.id), "bed_number": "B"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "VACANT"


def test_create_bed_unknown_room_not_found(client, owner_user):
    resp = client.post(
        "/api/v1/beds",
        json={"room_id": "00000000-0000-0000-0000-000000000000", "bed_number": "A"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 404


def test_create_bed_duplicate_number_in_room_conflict(client, owner_user, room, bed):
    resp = client.post(
        "/api/v1/beds", json={"room_id": str(room.id), "bed_number": bed.bed_number}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 409


def test_update_bed_status_occupied_rejected(client, owner_user, bed):
    resp = client.patch(f"/api/v1/beds/{bed.id}", json={"status": "OCCUPIED"}, headers=auth_headers(owner_user))
    assert resp.status_code == 400
    assert resp.json()["error"]["field"] == "status"


def test_update_bed_status_maintenance_allowed(client, owner_user, bed):
    resp = client.patch(f"/api/v1/beds/{bed.id}", json={"status": "MAINTENANCE"}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "MAINTENANCE"


def test_delete_bed_as_owner_succeeds(client, owner_user, bed):
    resp = client.delete(f"/api/v1/beds/{bed.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 204


def test_delete_occupied_bed_conflict(client, owner_user, db_session, bed):
    from app.models import BedStatus

    bed.status = BedStatus.OCCUPIED
    db_session.flush()

    resp = client.delete(f"/api/v1/beds/{bed.id}", headers=auth_headers(owner_user))
    assert resp.status_code == 409


def test_list_beds_filtered_by_room(client, staff_user, room, bed):
    resp = client.get(f"/api/v1/beds?room_id={room.id}", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    body = resp.json()
    assert all(b["room_id"] == str(room.id) for b in body["items"])
