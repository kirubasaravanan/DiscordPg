from conftest import auth_headers


def test_create_rent_entry_as_manager_succeeds(client, manager_user, tenant):
    resp = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["payment_status"] == "PENDING"
    assert body["paid_amount"] == "0.00"
    assert body["balance"] == "9500.00"


def test_create_rent_entry_as_staff_forbidden(client, staff_user, tenant):
    resp = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_create_rent_entry_rejects_non_first_of_month(client, manager_user, tenant):
    resp = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-15", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 422


def test_create_rent_entry_unknown_tenant_not_found(client, manager_user):
    resp = client.post(
        "/api/v1/rent",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "month": "2026-08-01",
            "rent_amount": "9500.00",
            "due_date": "2026-08-05",
        },
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 404


def test_create_rent_entry_duplicate_month_conflict(client, manager_user, tenant):
    payload = {"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"}
    first = client.post("/api/v1/rent", json=payload, headers=auth_headers(manager_user))
    assert first.status_code == 201

    second = client.post("/api/v1/rent", json=payload, headers=auth_headers(manager_user))
    assert second.status_code == 409


def test_record_partial_payment(client, manager_user, tenant):
    create = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    entry_id = create.json()["id"]

    resp = client.patch(f"/api/v1/rent/{entry_id}/payment", json={"amount": "5000.00"}, headers=auth_headers(manager_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_status"] == "PARTIAL"
    assert body["paid_amount"] == "5000.00"
    assert body["balance"] == "4500.00"


def test_record_payment_in_full_marks_paid(client, manager_user, tenant):
    create = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    entry_id = create.json()["id"]

    resp = client.patch(f"/api/v1/rent/{entry_id}/payment", json={"amount": "9500.00"}, headers=auth_headers(manager_user))
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "PAID"


def test_record_two_partial_payments_accumulate(client, manager_user, tenant):
    create = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    entry_id = create.json()["id"]

    client.patch(f"/api/v1/rent/{entry_id}/payment", json={"amount": "3000.00"}, headers=auth_headers(manager_user))
    resp = client.patch(f"/api/v1/rent/{entry_id}/payment", json={"amount": "6500.00"}, headers=auth_headers(manager_user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["paid_amount"] == "9500.00"
    assert body["payment_status"] == "PAID"


def test_record_payment_rejects_non_positive_amount(client, manager_user, tenant):
    create = client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )
    entry_id = create.json()["id"]

    resp = client.patch(f"/api/v1/rent/{entry_id}/payment", json={"amount": "0"}, headers=auth_headers(manager_user))
    assert resp.status_code == 422


def test_list_rent_ledger_filtered_by_tenant_and_status(client, staff_user, manager_user, tenant):
    client.post(
        "/api/v1/rent",
        json={"tenant_id": str(tenant.id), "month": "2026-08-01", "rent_amount": "9500.00", "due_date": "2026-08-05"},
        headers=auth_headers(manager_user),
    )

    resp = client.get(
        f"/api/v1/rent?tenant_id={tenant.id}&payment_status=PENDING", headers=auth_headers(staff_user)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tenant_id"] == str(tenant.id)
