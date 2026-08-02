"""Complaints view — the category-breakdown report is OWNER/MANAGER only
(REPORT_ROLES in dashboard.py), but triage (status/priority updates) is
open to all three staff roles (UPDATE_ROLES in complaints.py), unlike Rent.
"""

from conftest import api_get


def _save_button_count(at):
    return len([b for b in at.button if b.label == "Save"])


def test_owner_sees_kpis_matching_live_data(owner_at, owner_token):
    owner_at.switch_page("views/complaints.py")
    owner_at.run()
    assert not owner_at.exception

    truth = api_get(owner_token, "/dashboard")["complaints"]
    values = {m.label: m.value for m in owner_at.metric}
    assert values["Open"] == str(truth["open"])
    assert values["In progress"] == str(truth["in_progress"])
    assert values["Urgent"] == str(truth["urgent"])


def test_owner_sees_category_breakdown(owner_at):
    owner_at.switch_page("views/complaints.py")
    owner_at.run()

    assert not owner_at.exception
    assert "By category" in [s.value for s in owner_at.subheader]


def test_staff_can_triage_but_not_see_category_breakdown(staff_at, owner_token):
    staff_at.switch_page("views/complaints.py")
    staff_at.run()

    assert not staff_at.exception
    assert "By category" not in [s.value for s in staff_at.subheader]
    assert "Queue" in [s.value for s in staff_at.subheader]

    complaints = api_get(owner_token, "/complaints", page_size=100)["items"]
    assert _save_button_count(staff_at) == len(complaints)


def test_status_filter_options_match_backend_enum(owner_at):
    owner_at.switch_page("views/complaints.py")
    owner_at.run()

    filter_box = owner_at.selectbox[0]
    assert filter_box.label == "Filter by status"
    assert filter_box.options == ["All", "OPEN", "IN_PROGRESS", "REOPENED", "RESOLVED", "CLOSED"]
