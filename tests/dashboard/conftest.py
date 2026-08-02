"""Shared fixtures for dashboard integration tests.

These drive the real Streamlit view scripts via streamlit.testing.v1.AppTest
against a live backend — no mocks, per this project's testing convention
(see docs/ARCHITECTURE.md §4.2 and §13). They require the FastAPI backend
and PostgreSQL to be running and seeded (`uv run python -m app.database.seed`
from backend/); _require_live_backend skips the whole session with a clear
reason if the backend isn't reachable, rather than failing confusingly.
"""

import re

import pytest
import requests
from streamlit.testing.v1 import AppTest

from config import API_BASE_URL

APP_PY = "app.py"
HEALTH_URL = re.sub(r"/api/v1/?$", "", API_BASE_URL) + "/health"

# Matches backend/app/database/seed.py's dev users exactly.
OWNER = ("owner@example.com", "Owner-Dev-Pass123!")
MANAGER = ("manager@example.com", "Manager-Dev-Pass123!")
STAFF = ("staff@example.com", "Staff-Dev-Pass123!")
TENANT = ("arjun.mehta@example.com", "Tenant-Dev-Pass123!")


@pytest.fixture(scope="session", autouse=True)
def _require_live_backend():
    try:
        resp = requests.get(HEALTH_URL, timeout=3)
        resp.raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"backend not reachable at {HEALTH_URL} ({exc}) — start it before running these tests")


def login(identifier: str, password: str) -> AppTest:
    """A fresh AppTest for the dashboard entrypoint, logged in as the given user."""
    at = AppTest.from_file(APP_PY)
    at.run()
    at.text_input[0].input(identifier)
    at.text_input[1].input(password)
    at.button[0].click().run()
    assert not at.exception, f"login run raised: {at.exception}"
    return at


@pytest.fixture
def owner_at() -> AppTest:
    return login(*OWNER)


@pytest.fixture
def manager_at() -> AppTest:
    return login(*MANAGER)


@pytest.fixture
def staff_at() -> AppTest:
    return login(*STAFF)


def api_login(identifier: str, password: str) -> str:
    """A direct (non-Streamlit) login, for fetching ground truth to assert the UI against."""
    resp = requests.post(
        f"{API_BASE_URL}/auth/login", json={"identifier": identifier, "password": password}, timeout=5
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api_get(token: str, path: str, **params) -> dict:
    resp = requests.get(f"{API_BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"}, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


@pytest.fixture
def owner_token() -> str:
    return api_login(*OWNER)
