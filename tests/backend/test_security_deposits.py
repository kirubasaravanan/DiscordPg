from conftest import auth_headers


def test_create_deposit_as_manager_succeeds(client, manager_user, tenant):
    resp = client.post(
        "/api/v1/deposits",
        json={"tenant_id": str(tenant.id), "amount": "10000.00", "received_date": "2026-02-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 201
    assert resp.json()["refund_status"] == "HELD"


def test_create_deposit_as_staff_forbidden(client, staff_user, tenant):
    resp = client.post(
        "/api/v1/deposits",
        json={"tenant_id": str(tenant.id), "amount": "10000.00", "received_date": "2026-02-01"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


def test_list_deposits_as_staff_forbidden(client, staff_user):
    resp = client.get("/api/v1/deposits", headers=auth_headers(staff_user))
    assert resp.status_code == 403


def test_create_deposit_unknown_tenant_not_found(client, manager_user):
    resp = client.post(
        "/api/v1/deposits",
        json={"tenant_id": "00000000-0000-0000-0000-000000000000", "amount": "10000.00", "received_date": "2026-02-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 404


def test_create_deposit_negative_amount_rejected(client, manager_user, tenant):
    resp = client.post(
        "/api/v1/deposits",
        json={"tenant_id": str(tenant.id), "amount": "-1", "received_date": "2026-02-01"},
        headers=auth_headers(manager_user),
    )
    assert resp.status_code == 422


def test_update_deposit_refund_status(client, manager_user, tenant):
    create = client.post(
        "/api/v1/deposits",
        json={"tenant_id": str(tenant.id), "amount": "10000.00", "received_date": "2026-02-01"},
        headers=auth_headers(manager_user),
    )
    deposit_id = create.json()["id"]

    resp = client.patch(
        f"/api/v1/deposits/{deposit_id}", json={"refund_status": "REFUNDED"}, headers=auth_headers(manager_user)
    )
    assert resp.status_code == 200
    assert resp.json()["refund_status"] == "REFUNDED"


def test_list_deposits_filtered_by_tenant(client, manager_user, tenant):
    client.post(
        "/api/v1/deposits",
        json={"tenant_id": str(tenant.id), "amount": "10000.00", "received_date": "2026-02-01"},
        headers=auth_headers(manager_user),
    )

    resp = client.get(f"/api/v1/deposits?tenant_id={tenant.id}", headers=auth_headers(manager_user))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tenant_id"] == str(tenant.id)
