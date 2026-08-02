"""Expenses view — OWNER/MANAGER only at the navigation level (app.py hides
it from STAFF entirely; see test_navigation.py), so this only needs to
cover the view's own content, not per-role gating within the page.
"""

from conftest import api_get


def test_owner_sees_kpi_matching_live_data(owner_at, owner_token):
    owner_at.switch_page("views/expenses.py")
    owner_at.run()
    assert not owner_at.exception

    truth = api_get(owner_token, "/dashboard")["expenses"]
    values = {m.label: m.value for m in owner_at.metric}
    assert values["This month"] == f"₹{float(truth['this_month']):,.2f}"


def test_add_expense_form_present(owner_at):
    owner_at.switch_page("views/expenses.py")
    owner_at.run()

    assert not owner_at.exception
    assert [s.label for s in owner_at.selectbox] == ["Category"]
    assert owner_at.selectbox[0].options == ["MAINTENANCE", "UTILITIES", "SALARY", "SUPPLIES", "OTHER"]
    assert "Amount" in [n.label for n in owner_at.number_input]
    assert "Vendor (optional)" in [t.label for t in owner_at.text_input]
    assert "Notes (optional)" in [t.label for t in owner_at.text_input]


def test_recent_expenses_lists_at_least_the_seeded_rows(owner_at, owner_token):
    owner_at.switch_page("views/expenses.py")
    owner_at.run()

    truth = api_get(owner_token, "/expenses", page_size=100)["items"]
    if not truth:
        assert "No expenses recorded yet." in [i.value for i in owner_at.info]
        return
    assert "By category" in [s.value for s in owner_at.subheader]
    assert "Recent expenses" in [s.value for s in owner_at.subheader]


def test_manager_can_reach_expenses(manager_at):
    manager_at.switch_page("views/expenses.py")
    manager_at.run()

    assert not manager_at.exception
    assert manager_at.title[0].value == "Expenses"
