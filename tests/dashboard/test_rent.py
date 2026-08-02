"""Rent view — income trend and the record-payment action are OWNER/MANAGER
only (docs/API.md §3's WRITE_ROLES); STAFF gets read-only KPIs + ledger.
"""

from conftest import api_get


def _submit_button_count(at):
    return len([b for b in at.button if b.label == "Submit"])


def test_owner_sees_kpis_matching_live_data(owner_at, owner_token):
    owner_at.switch_page("views/rent.py")
    owner_at.run()
    assert not owner_at.exception

    truth = api_get(owner_token, "/dashboard")["rent"]
    values = {m.label: m.value for m in owner_at.metric}
    assert values["Overdue entries"] == str(truth["overdue_count"])
    assert values["Collected this month"] == f"₹{float(truth['collected_this_month']):,.2f}"
    assert values["Pending this month"] == f"₹{float(truth['pending_this_month']):,.2f}"


def test_owner_sees_income_trend_and_can_record_payments(owner_at, owner_token):
    owner_at.switch_page("views/rent.py")
    owner_at.run()

    assert not owner_at.exception
    assert "Income trend (6 months)" in [s.value for s in owner_at.subheader]

    ledger = api_get(owner_token, "/rent", page_size=100)["items"]
    unpaid = sum(1 for entry in ledger if entry["payment_status"] != "PAID")
    assert _submit_button_count(owner_at) == unpaid


def test_manager_sees_income_trend(manager_at):
    manager_at.switch_page("views/rent.py")
    manager_at.run()

    assert not manager_at.exception
    assert "Income trend (6 months)" in [s.value for s in manager_at.subheader]


def test_staff_is_read_only(staff_at):
    staff_at.switch_page("views/rent.py")
    staff_at.run()

    assert not staff_at.exception
    assert "Income trend (6 months)" not in [s.value for s in staff_at.subheader]
    assert _submit_button_count(staff_at) == 0
    assert "Rent ledger" in [s.value for s in staff_at.subheader]  # still sees the ledger itself
