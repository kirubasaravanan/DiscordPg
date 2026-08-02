import streamlit as st

import api_client

STAFF_ROLES = ("OWNER", "MANAGER", "STAFF")


def is_logged_in() -> bool:
    return "access_token" in st.session_state


def current_role() -> str | None:
    return st.session_state.get("role")


def current_user_email() -> str | None:
    return st.session_state.get("user_email")


def render_login_form() -> None:
    st.title("PG OS — Admin Dashboard")
    st.caption("Sign in with an OWNER, MANAGER, or STAFF account.")

    with st.form("login_form"):
        identifier = st.text_input("Email or phone")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if not submitted:
        return

    if not identifier or not password:
        st.error("Enter both your email/phone and password.")
        return

    try:
        tokens = api_client.login(identifier, password)
    except api_client.APIError as exc:
        st.error(exc.message)
        return

    if tokens["role"] not in STAFF_ROLES:
        st.error("This dashboard is for staff accounts. Tenants use the Discord bot instead.")
        return

    st.session_state["access_token"] = tokens["access_token"]
    st.session_state["refresh_token"] = tokens["refresh_token"]
    st.session_state["role"] = tokens["role"]
    st.session_state["user_email"] = identifier
    st.rerun()


def require_login() -> bool:
    """True if already logged in. Otherwise renders the login form and
    returns False — the caller should st.stop() right after.
    """
    if is_logged_in():
        return True
    render_login_form()
    return False


def render_sidebar_account_info() -> None:
    with st.sidebar:
        st.caption(f"Signed in as **{current_user_email()}** ({current_role()})")
        if st.button("Log out", width="stretch"):
            api_client.logout()
            st.rerun()
