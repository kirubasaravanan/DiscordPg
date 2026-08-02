"""Shared presentation helpers so the 4 views don't re-derive the same
status-color mapping and chart palette. Status tones follow the dataviz
skill's rule: icon + label always paired, never color alone.
"""

import functools

import streamlit as st

import api_client

GOOD = "good"
WARNING = "warning"
CRITICAL = "critical"
NEUTRAL = "neutral"

_BADGE_STYLE = {
    GOOD: ("green", ":material/check_circle:"),
    WARNING: ("orange", ":material/warning:"),
    CRITICAL: ("red", ":material/error:"),
    NEUTRAL: ("gray", ":material/circle:"),
}

PAYMENT_STATUS_TONE = {"PAID": GOOD, "PARTIAL": WARNING, "PENDING": NEUTRAL, "OVERDUE": CRITICAL}
COMPLAINT_STATUS_TONE = {
    "OPEN": WARNING,
    "IN_PROGRESS": NEUTRAL,
    "RESOLVED": GOOD,
    "CLOSED": GOOD,
    "REOPENED": WARNING,
}
PRIORITY_TONE = {"LOW": NEUTRAL, "MEDIUM": NEUTRAL, "HIGH": WARNING, "URGENT": CRITICAL}

# Validated categorical order and sequential ramp from the dataviz skill's
# references/palette.md, for the Plotly charts where exact hex control
# matters — st.badge/st.metric below use Streamlit's own named-color tokens
# instead, the safer choice for the parts they control.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a"]  # first 3 slots validate all-pairs
SEQUENTIAL_BLUE = "#2a78d6"
TRACK_GRAY = "#e1e0d9"


def status_badge(label: str, tone: str) -> None:
    color, icon = _BADGE_STYLE.get(tone, _BADGE_STYLE[NEUTRAL])
    st.badge(label, icon=icon, color=color)


def format_inr(amount) -> str:
    return f"₹{float(amount):,.2f}"


def api_page(fn):
    """Wraps a view's render function: APIError becomes a clean st.error
    instead of a stack trace, and 401s bounce back to the login form.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except api_client.APIError as exc:
            if exc.status_code == 401:
                st.warning("Your session expired — please log in again.")
                st.rerun()
            st.error(f"Couldn't load this page: {exc.message}")
            st.stop()

    return wrapper
