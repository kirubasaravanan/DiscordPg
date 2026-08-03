"""Outbound Discord notifications — the "notification delivery path" that
docs/ROADMAP.md's Phase 5 entry calls for. docs/ROADMAP.md line 139 assigns
actually *wiring* the APScheduler jobs from docs/ARCHITECTURE.md §9 to
Phase 6 (they call the AI summary generator, which doesn't exist yet); this
module is the mechanism those jobs will call once they exist.

Uses Discord's plain HTTP API directly rather than discord_bot/'s
discord.py gateway connection: sending a message never requires the
gateway — only *receiving* interactions does, and that's a separate,
long-lived process (discord_bot/). A backend service sending one outbound
REST call needs nothing more than the same bot token.

Unverified against a live Discord account — no bot token exists in this
environment (see docs/ARCHITECTURE.md §12), same gap as the S3/R2 backend
in Phase 3c. The calls below follow Discord's documented REST API exactly
(create-DM-then-message for a DM, direct POST for a channel).
"""

import httpx

from app.config import get_settings

_DISCORD_API_BASE = "https://discord.com/api/v10"


class NotificationError(Exception):
    """A Discord notification could not be delivered."""


def _client() -> httpx.Client:
    settings = get_settings()
    if not settings.discord_bot_token:
        raise NotificationError("DISCORD_BOT_TOKEN is not configured.")
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    return httpx.Client(base_url=_DISCORD_API_BASE, headers=headers, timeout=10.0)


def _post(client: httpx.Client, path: str, json: dict) -> dict:
    resp = client.post(path, json=json)
    if resp.status_code >= 400:
        raise NotificationError(f"Discord API {path} failed ({resp.status_code}): {resp.text}")
    return resp.json() if resp.content else {}


def send_discord_dm(discord_id: str, message: str) -> None:
    """Direct-messages a linked user — e.g. the daily pending-rent check
    notifying an individual tenant (docs/ARCHITECTURE.md §9).
    """
    with _client() as client:
        channel = _post(client, "/users/@me/channels", {"recipient_id": discord_id})
        _post(client, f"/channels/{channel['id']}/messages", {"content": message})


def send_channel_message(channel_id: str, message: str) -> None:
    """Posts to a fixed channel — e.g. the daily management report
    (docs/ARCHITECTURE.md §9).
    """
    with _client() as client:
        _post(client, f"/channels/{channel_id}/messages", {"content": message})
