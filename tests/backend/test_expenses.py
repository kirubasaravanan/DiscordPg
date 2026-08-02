from conftest import auth_headers


def test_create_expense_as_manager_succeeds(client, manager_user, building):
    resp = client.post(
        "/api/v1/expenses",
        json={"building_id": str(building.id), "category": "MAINTENANCE", "amount": "500.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201


def test_create_expense_without_building_succeeds(client, manager_user):
    resp = client.post(
        "/api/v1/expenses",
        json={"category": "SALARY", "amount": "20000.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    assert resp.json()["building_id"] is None


def test_create_expense_as_staff_forbidden(client, staff_user):
    resp = client.post(
        "/api/v1/expenses",
        json={"category": "SUPPLIES", "amount": "100.00", "date": "2026-08-01"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_create_expense_unknown_building_not_found(client, manager_user):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "building_id": "00000000-0000-0000-0000-000000000000",
            "category": "UTILITIES",
            "amount": "100.00",
            "date": "2026-08-01",
        },
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 404


def test_expenses_router_has_no_delete_route(client, owner_user, manager_user, building):
    create = client.post(
        "/api/v1/expenses",
        json={"building_id": str(building.id), "category": "OTHER", "amount": "50.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    expense_id = create.json()["id"]

    resp = client.delete(f"/api/v1/expenses/{expense_id}", headers=auth_headers(owner_user))
    assert resp.status_code == 405


def test_update_expense_corrects_amount(client, manager_user, building):
    create = client.post(
        "/api/v1/expenses",
        json={"building_id": str(building.id), "category": "MAINTENANCE", "amount": "500.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    expense_id = create.json()["id"]

    resp = client.patch(f"/api/v1/expenses/{expense_id}", json={"amount": "550.00"}, headers=auth_headers(manager_user))
    assert resp.status_code == 200
    assert resp.json()["amount"] == "550.00"


def test_list_expenses_filtered_by_category(client, manager_user, building):
    client.post(
        "/api/v1/expenses",
        json={"building_id": str(building.id), "category": "UTILITIES", "amount": "1000.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )
    client.post(
        "/api/v1/expenses",
        json={"building_id": str(building.id), "category": "SUPPLIES", "amount": "200.00", "date": "2026-08-01"},
        headers=auth_headers(manager_user),
    )

    resp = client.get("/api/v1/expenses?category=UTILITIES", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    body = resp.json()
    assert all(e["category"] == "UTILITIES" for e in body["items"])
