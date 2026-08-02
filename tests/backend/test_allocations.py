import datetime

from conftest import auth_headers


def test_create_allocation_occupies_bed_and_derives_room_id(client, manager_user, tenant, room, bed):
    resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["room_id"] == str(room.id)
    assert body["end_date"] is None

    bed_resp = client.get(f"/api/v1/beds/{bed.id}", headers=auth_headers(manager_user))
    assert bed_resp.json()["status"] == "OCCUPIED"


def test_allocation_fills_last_vacant_bed_marks_room_full(client, manager_user, db_session, tenant, building):
    from app.models import Bed, Room, Tenant

    # A 1-bed room so a single allocation fills it completely.
    room = Room(building_id=building.id, room_number="single-1", floor=1, capacity=1)
    db_session.add(room)
    db_session.flush()
    bed = Bed(room_id=room.id, bed_number="A")
    db_session.add(bed)
    db_session.flush()

    resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201

    room_resp = client.get(f"/api/v1/rooms/{room.id}", headers=auth_headers(manager_user))
    assert room_resp.json()["status"] == "FULL"


def test_create_allocation_on_occupied_bed_conflict(client, manager_user, db_session, tenant, room, bed):
    from app.models import BedStatus

    bed.status = BedStatus.OCCUPIED
    db_session.flush()

    resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 409


def test_create_allocation_as_staff_forbidden(client, staff_user, tenant, bed):
    resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-08-01"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_end_allocation_frees_bed_and_room_becomes_available(client, manager_user, db_session, tenant, room, bed):
    from app.models import Allocation, RoomStatus

    allocation = Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1))
    db_session.add(allocation)
    from app.models import BedStatus

    bed.status = BedStatus.OCCUPIED
    room.status = RoomStatus.FULL
    db_session.flush()

    resp = client.patch(
        f"/api/v1/allocations/{allocation.id}/end", json={"end_date": "2026-08-01"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 200
    assert resp.json()["end_date"] == "2026-08-01"

    bed_resp = client.get(f"/api/v1/beds/{bed.id}", headers=auth_headers(manager_user))
    assert bed_resp.json()["status"] == "VACANT"
    room_resp = client.get(f"/api/v1/rooms/{room.id}", headers=auth_headers(manager_user))
    assert room_resp.json()["status"] == "AVAILABLE"


def test_end_allocation_defaults_end_date_to_today(client, manager_user, db_session, tenant, room, bed):
    from app.models import Allocation

    allocation = Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1))
    db_session.add(allocation)
    db_session.flush()

    resp = client.patch(f"/api/v1/allocations/{allocation.id}/end", json={}, headers=auth_headers(manager_user))
    assert resp.status_code == 200
    assert resp.json()["end_date"] == datetime.date.today().isoformat()


def test_end_already_ended_allocation_conflict(client, manager_user, db_session, tenant, room, bed):
    from app.models import Allocation

    allocation = Allocation(
        tenant_id=tenant.id,
        room_id=room.id,
        bed_id=bed.id,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 2, 1),
    )
    db_session.add(allocation)
    db_session.flush()

    resp = client.patch(
        f"/api/v1/allocations/{allocation.id}/end", json={"end_date": "2026-03-01"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 409


def test_end_allocation_before_start_date_rejected(client, manager_user, tenant, room, bed):
    create_resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    allocation_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/allocations/{allocation_id}/end", json={"end_date": "2026-01-01"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["field"] == "end_date"


def test_reallocate_bed_after_end(client, manager_user, db_session, tenant, room, bed):
    from app.models import Tenant

    first = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(tenant.id), "bed_id": str(bed.id), "start_date": "2026-01-01"},
        headers=auth_headers(manager_user),
    )
    client.patch(f"/api/v1/allocations/{first.json()['id']}/end", json={"end_date": "2026-06-01"}, headers=auth_headers(manager_user))

    second_tenant = Tenant(name="Second Tenant", phone="9222200001", joining_date=datetime.date(2026, 6, 1))
    db_session.add(second_tenant)
    db_session.flush()

    resp = client.post(
        "/api/v1/allocations",
        json={"tenant_id": str(second_tenant.id), "bed_id": str(bed.id), "start_date": "2026-06-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201


def test_list_allocations_active_only_filter(client, manager_user, db_session, tenant, room, bed):
    from app.models import Allocation

    ended = Allocation(
        tenant_id=tenant.id,
        room_id=room.id,
        bed_id=bed.id,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 2, 1),
    )
    db_session.add(ended)
    db_session.flush()

    resp = client.get("/api/v1/allocations?active_only=true", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    assert all(a["end_date"] is None for a in resp.json()["items"])
