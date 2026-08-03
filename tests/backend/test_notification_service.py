"""Only the config-validation path is testable for real here — actually
sending a Discord message needs a live bot token, which doesn't exist in
this environment (see docs/ARCHITECTURE.md §12, same gap as the S3 backend
in Phase 3c). No live-send test is faked with a mock in its place.
"""

import pytest

from app.config import Settings
from app.services import notification_service


def test_send_discord_dm_without_token_raises_clear_error(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: Settings(discord_bot_token=None))

    with pytest.raises(notification_service.NotificationError, match="DISCORD_BOT_TOKEN"):
        notification_service.send_discord_dm("123", "hello")


def test_send_channel_message_without_token_raises_clear_error(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: Settings(discord_bot_token=None))

    with pytest.raises(notification_service.NotificationError, match="DISCORD_BOT_TOKEN"):
        notification_service.send_channel_message("456", "hello")
