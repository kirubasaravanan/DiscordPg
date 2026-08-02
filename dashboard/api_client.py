"""Thin wrapper over the backend HTTP API. This is the *only* way the
dashboard touches data — no database connection anywhere in this project,
per docs/ARCHITECTURE.md §4.2.
"""

import requests
import streamlit as st

from config import API_BASE_URL

TIMEOUT_SECONDS = 10
MAX_PAGE_SIZE = 100  # matches the backend's page_size cap (app/api/deps.py)


class APIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _extract_error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
        return body.get("error", {}).get("message") or resp.text
    except ValueError:
        return resp.text or f"HTTP {resp.status_code}"


def _clear_session() -> None:
    for key in ("access_token", "refresh_token", "role", "user_email"):
        st.session_state.pop(key, None)


def _refresh_access_token() -> bool:
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return False
    resp = requests.post(
        f"{API_BASE_URL}/auth/refresh", json={"refresh_token": refresh_token}, timeout=TIMEOUT_SECONDS
    )
    if resp.status_code != 200:
        return False
    st.session_state["access_token"] = resp.json()["access_token"]
    return True


def request(method: str, path: str, *, params: dict | None = None, json: dict | None = None, retry: bool = True) -> dict:
    resp = requests.request(
        method, f"{API_BASE_URL}{path}", headers=_headers(), params=params, json=json, timeout=TIMEOUT_SECONDS
    )
    if resp.status_code == 401 and retry:
        if _refresh_access_token():
            return request(method, path, params=params, json=json, retry=False)
        _clear_session()
        raise APIError(401, "Your session expired — please log in again.")
    if resp.status_code >= 400:
        raise APIError(resp.status_code, _extract_error_message(resp))
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


# --- auth -------------------------------------------------------------------


def login(identifier: str, password: str) -> dict:
    resp = requests.post(
        f"{API_BASE_URL}/auth/login", json={"identifier": identifier, "password": password}, timeout=TIMEOUT_SECONDS
    )
    if resp.status_code != 200:
        raise APIError(resp.status_code, _extract_error_message(resp))
    return resp.json()


def logout() -> None:
    try:
        request("POST", "/auth/logout", retry=False)
    except APIError:
        pass  # best-effort — clear local session regardless of server-side outcome
    _clear_session()


# --- dashboard / reports ------------------------------------------------------


def get_dashboard_summary() -> dict:
    return request("GET", "/dashboard")


def get_income_report(months: int = 6) -> dict:
    return request("GET", "/reports/income", params={"months": months})


def get_occupancy_report() -> dict:
    return request("GET", "/reports/occupancy")


def get_complaints_report() -> dict:
    return request("GET", "/reports/complaints")


# --- rent ---------------------------------------------------------------------


def list_rent_ledger(*, payment_status: str | None = None, page_size: int = MAX_PAGE_SIZE) -> dict:
    params: dict = {"page": 1, "page_size": page_size}
    if payment_status:
        params["payment_status"] = payment_status
    return request("GET", "/rent", params=params)


def record_rent_payment(entry_id: str, amount: str) -> dict:
    return request("PATCH", f"/rent/{entry_id}/payment", json={"amount": amount})


# --- complaints -----------------------------------------------------------------


def list_complaints(*, status: str | None = None, page_size: int = MAX_PAGE_SIZE) -> dict:
    params: dict = {"page": 1, "page_size": page_size}
    if status:
        params["status"] = status
    return request("GET", "/complaints", params=params)


def update_complaint(complaint_id: str, *, status: str | None = None, priority: str | None = None) -> dict:
    payload = {}
    if status:
        payload["status"] = status
    if priority:
        payload["priority"] = priority
    return request("PATCH", f"/complaints/{complaint_id}", json=payload)


# --- expenses ---------------------------------------------------------------------


def list_expenses(*, page_size: int = MAX_PAGE_SIZE) -> dict:
    return request("GET", "/expenses", params={"page": 1, "page_size": page_size})


def create_expense(
    *,
    category: str,
    amount: str,
    date: str,
    building_id: str | None = None,
    vendor: str | None = None,
    notes: str | None = None,
) -> dict:
    payload: dict = {"category": category, "amount": amount, "date": date}
    if building_id:
        payload["building_id"] = building_id
    if vendor:
        payload["vendor"] = vendor
    if notes:
        payload["notes"] = notes
    return request("POST", "/expenses", json=payload)


# --- reference data, for enriching displays with names instead of bare ids ------


def list_tenants(*, page_size: int = MAX_PAGE_SIZE) -> dict:
    return request("GET", "/tenants", params={"page": 1, "page_size": page_size})


def list_buildings(*, page_size: int = MAX_PAGE_SIZE) -> dict:
    return request("GET", "/buildings", params={"page": 1, "page_size": page_size})


def list_rooms(*, page_size: int = MAX_PAGE_SIZE) -> dict:
    return request("GET", "/rooms", params={"page": 1, "page_size": page_size})
