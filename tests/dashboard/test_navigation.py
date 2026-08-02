"""Role-based page visibility (app.py): Occupancy/Rent/Complaints are open
to all three staff roles; Expenses is registered with st.navigation only
for OWNER/MANAGER. This confirms it's not just hidden from the sidebar —
st.navigation makes an unregistered page unreachable even via a direct
switch_page call, which is the actual security boundary (the backend's own
RBAC on /api/v1/expenses is the other layer — see test_expenses.py's
sibling coverage in tests/backend/test_expenses.py).
"""

VIEWS_AND_TITLES = [
    ("views/occupancy.py", "Occupancy"),
    ("views/rent.py", "Rent"),
    ("views/complaints.py", "Complaints"),
    ("views/expenses.py", "Expenses"),
]


def test_owner_can_reach_all_four_views(owner_at):
    for path, expected_title in VIEWS_AND_TITLES:
        owner_at.switch_page(path)
        owner_at.run()
        assert not owner_at.exception, f"{path} raised: {owner_at.exception}"
        assert owner_at.title[0].value == expected_title


def test_staff_can_reach_three_views(staff_at):
    for path, expected_title in VIEWS_AND_TITLES[:3]:
        staff_at.switch_page(path)
        staff_at.run()
        assert not staff_at.exception, f"{path} raised: {staff_at.exception}"
        assert staff_at.title[0].value == expected_title


def test_staff_cannot_reach_expenses_view(staff_at):
    """Expenses was never added to STAFF's `pages` list in app.py, so
    st.navigation silently falls back to the default page (Occupancy)
    instead of executing expenses.py at all.
    """
    staff_at.switch_page("views/expenses.py")
    staff_at.run()

    assert not staff_at.exception
    assert staff_at.title[0].value == "Occupancy"
    assert "This month" not in [m.label for m in staff_at.metric]
