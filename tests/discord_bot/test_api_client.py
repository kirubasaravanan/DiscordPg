"""Tests api_client.py — the bot's only path to data — against the real
running backend, no mocks, consistent with this project's testing
philosophy. Nothing here touches discord.py or a live Discord connection;
that boundary is exactly what makes this module independently testable
without a bot token (see docs/ARCHITECTURE.md §12).
"""

import uuid

import pytest
from conftest import OWNER, STAFF, TENANT

import api_client


def _fresh_discord_id() -> str:
    """A random snowflake-shaped id so repeated test runs never collide
    with a discord_id a previous run already linked to the same account.
    """
    return uuid.uuid4().hex[:18]


async def test_login_success():
    tokens = await api_client.login(*OWNER)
    assert tokens["role"] == "OWNER"
    assert tokens["access_token"]


async def test_login_invalid_credentials():
    with pytest.raises(api_client.APIError) as exc_info:
        await api_client.login(OWNER[0], "wrong-password")
    assert exc_info.value.status_code == 401


async def test_request_without_session_raises_not_linked():
    with pytest.raises(api_client.NotLinkedError):
        await api_client.request(_fresh_discord_id(), "GET", "/rules")


async def test_link_creates_a_session():
    discord_id = _fresh_discord_id()

    session = await api_client.link(discord_id, *STAFF)

    assert session.role == "STAFF"
    assert api_client.get_session(discord_id) is session


async def test_link_with_bad_password_leaves_no_session():
    discord_id = _fresh_discord_id()

    with pytest.raises(api_client.APIError):
        await api_client.link(discord_id, OWNER[0], "wrong-password")

    assert api_client.get_session(discord_id) is None


async def test_clear_session():
    discord_id = _fresh_discord_id()
    await api_client.link(discord_id, *OWNER)

    api_client.clear_session(discord_id)

    assert api_client.get_session(discord_id) is None


async def test_get_rules_after_link():
    discord_id = _fresh_discord_id()
    await api_client.link(discord_id, *OWNER)

    content = await api_client.get_rules(discord_id)

    assert "Rent" in content


async def test_tenant_rent_and_complaint_round_trip():
    discord_id = _fresh_discord_id()
    await api_client.link(discord_id, *TENANT)

    rent_rows = await api_client.get_tenant_rent(discord_id)
    assert isinstance(rent_rows, list)

    created = await api_client.file_complaint(discord_id, "pytest bot round-trip test complaint")
    assert created["status"] == "OPEN"
    assert created["description"] == "pytest bot round-trip test complaint"

    complaints = await api_client.list_own_complaints(discord_id)
    assert any(c["id"] == created["id"] for c in complaints)


async def test_ask_faq_reaches_the_endpoint():
    """Doesn't assert on the AI's actual answer — ai_engine reachability
    isn't this suite's concern (see tests/backend/test_ai_client.py, which
    orchestrates a real ai_engine + fake-Ollama pair for that). Just
    confirms the bot's api_client calls /tenant/faq correctly and gets
    back either a well-shaped answer or a clean 503, never anything else.
    """
    discord_id = _fresh_discord_id()
    await api_client.link(discord_id, *TENANT)

    try:
        result = await api_client.ask_faq(discord_id, "When is rent due?")
    except api_client.APIError as exc:
        assert exc.status_code == 503
        return

    assert isinstance(result["answer"], str)
    assert isinstance(result["cited_sources"], list)


async def test_non_tenant_role_gets_403_on_tenant_endpoints():
    discord_id = _fresh_discord_id()
    await api_client.link(discord_id, *STAFF)

    with pytest.raises(api_client.APIError) as exc_info:
        await api_client.get_tenant_rent(discord_id)

    assert exc_info.value.status_code == 403
