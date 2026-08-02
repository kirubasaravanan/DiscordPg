"""Login form behavior against the real /auth/login endpoint — covers the
staff-only dashboard access rule in dashboard/auth.py's STAFF_ROLES check.
"""

from conftest import APP_PY, OWNER, TENANT
from streamlit.testing.v1 import AppTest


def test_login_form_renders():
    at = AppTest.from_file(APP_PY)
    at.run()

    assert not at.exception
    assert at.title[0].value == "PG OS — Admin Dashboard"
    assert [i.label for i in at.text_input] == ["Email or phone", "Password"]


def test_invalid_password_shows_error():
    at = AppTest.from_file(APP_PY)
    at.run()
    at.text_input[0].input(OWNER[0])
    at.text_input[1].input("WrongPassword123!")
    at.button[0].click().run()

    assert not at.exception
    assert "role" not in at.session_state
    assert at.error[0].value == "Invalid credentials."


def test_empty_fields_show_local_error_without_hitting_api():
    at = AppTest.from_file(APP_PY)
    at.run()
    at.button[0].click().run()

    assert not at.exception
    assert at.error[0].value == "Enter both your email/phone and password."


def test_tenant_login_is_rejected():
    """Tenants have API accounts but use the Discord bot, not this dashboard."""
    at = AppTest.from_file(APP_PY)
    at.run()
    at.text_input[0].input(TENANT[0])
    at.text_input[1].input(TENANT[1])
    at.button[0].click().run()

    assert not at.exception
    assert "role" not in at.session_state
    assert "staff accounts" in at.error[0].value


def test_owner_login_succeeds(owner_at):
    assert owner_at.session_state["role"] == "OWNER"
    assert owner_at.session_state["access_token"]
    assert owner_at.session_state["refresh_token"]
    assert "owner@example.com" in owner_at.sidebar.caption[0].value


def test_staff_login_succeeds(staff_at):
    assert staff_at.session_state["role"] == "STAFF"
