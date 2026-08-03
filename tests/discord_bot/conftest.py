import re

import httpx
import pytest

from config import API_BASE_URL

HEALTH_URL = re.sub(r"/api/v1/?$", "", API_BASE_URL) + "/health"

OWNER = ("owner@example.com", "Owner-Dev-Pass123!")
MANAGER = ("manager@example.com", "Manager-Dev-Pass123!")
STAFF = ("staff@example.com", "Staff-Dev-Pass123!")
TENANT = ("arjun.mehta@example.com", "Tenant-Dev-Pass123!")


@pytest.fixture(scope="session", autouse=True)
def _require_live_backend():
    try:
        resp = httpx.get(HEALTH_URL, timeout=3)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"backend not reachable at {HEALTH_URL} ({exc}) — start it before running these tests")
