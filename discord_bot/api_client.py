"""Thin async wrapper over the backend HTTP API. Like dashboard/api_client.py,
this is the *only* way the bot touches data — no database connection
anywhere in this project, per docs/ARCHITECTURE.md §4.1.

Async (httpx.AsyncClient) rather than the dashboard's sync `requests`,
because this runs inside discord.py's asyncio event loop — a blocking call
here would stall every other command the bot is handling concurrently.

Sessions are per-Discord-user (not a single global session like the
dashboard's st.session_state, since one bot process serves many users at
once) and held in memory only — lost on restart, recovered by running
/link again. That's an accepted v1 tradeoff, not a bug: see
docs/ARCHITECTURE.md §12.
"""

from dataclasses import dataclass

import httpx

from config import API_BASE_URL

TIMEOUT_SECONDS = 10.0


class APIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class NotLinkedError(Exception):
    """Raised when a command needs a session but this Discord user hasn't
    run /link yet (or their session was cleared after an expired refresh
    token) — callers show a "run /link first" message, not a raw error.
    """


@dataclass
class Session:
    access_token: str
    refresh_token: str
    role: str
    identifier: str


_sessions: dict[str, Session] = {}


def get_session(discord_id: str) -> Session | None:
    return _sessions.get(discord_id)


def clear_session(discord_id: str) -> None:
    _sessions.pop(discord_id, None)


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return body.get("error", {}).get("message") or resp.text
    except ValueError:
        return resp.text or f"HTTP {resp.status_code}"


async def login(identifier: str, password: str) -> dict:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        resp = await client.post("/auth/login", json={"identifier": identifier, "password": password})
    if resp.status_code != 200:
        raise APIError(resp.status_code, _extract_error_message(resp))
    return resp.json()


async def _refresh_access_token(discord_id: str) -> bool:
    session = _sessions.get(discord_id)
    if session is None:
        return False
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        resp = await client.post("/auth/refresh", json={"refresh_token": session.refresh_token})
    if resp.status_code != 200:
        return False
    session.access_token = resp.json()["access_token"]
    return True


async def request(
    discord_id: str,
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    retry: bool = True,
) -> dict:
    session = _sessions.get(discord_id)
    if session is None:
        raise NotLinkedError()

    headers = {"Authorization": f"Bearer {session.access_token}"}
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        resp = await client.request(method, path, headers=headers, json=json, params=params)

    if resp.status_code == 401 and retry:
        if await _refresh_access_token(discord_id):
            return await request(discord_id, method, path, json=json, params=params, retry=False)
        clear_session(discord_id)
        raise NotLinkedError()
    if resp.status_code >= 400:
        raise APIError(resp.status_code, _extract_error_message(resp))
    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


async def link(discord_id: str, identifier: str, password: str) -> Session:
    """Logs in, then links this Discord account to the resulting user in
    one step — /link is the only place a raw password is ever handled.
    Rolls the provisional session back if linking itself fails (e.g. this
    Discord account is already linked to a *different* PG OS user), so a
    failed /link never leaves a half-authenticated session behind.
    """
    tokens = await login(identifier, password)
    session = Session(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        role=tokens["role"],
        identifier=identifier,
    )
    _sessions[discord_id] = session
    try:
        await request(discord_id, "POST", "/auth/link-discord", json={"discord_id": discord_id})
    except (APIError, NotLinkedError):
        _sessions.pop(discord_id, None)
        raise
    return session


# --- rules --------------------------------------------------------------


async def get_rules(discord_id: str) -> str:
    data = await request(discord_id, "GET", "/rules")
    return data["content"]


# --- tenant self-service --------------------------------------------------


async def get_tenant_rent(discord_id: str) -> list[dict]:
    data = await request(discord_id, "GET", "/tenant/rent", params={"page_size": 100})
    return data["items"]


async def file_complaint(discord_id: str, description: str) -> dict:
    return await request(discord_id, "POST", "/tenant/complaints", json={"description": description})


async def list_own_complaints(discord_id: str) -> list[dict]:
    data = await request(discord_id, "GET", "/tenant/complaints", params={"page_size": 100})
    return data["items"]
