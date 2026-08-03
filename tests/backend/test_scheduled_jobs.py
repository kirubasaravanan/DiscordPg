"""scheduled_jobs.py's job bodies, against real Postgres with
notification_service/ai_client substituted at their own boundary —
those modules' real HTTP contracts are tested separately
(test_notification_service.py, test_ai_client.py); these tests verify the
jobs' own orchestration logic (who gets notified, what gets skipped,
graceful degradation on failure) deterministically, not dependent on
whatever Discord/AI configuration happens to be in the ambient .env.
"""

import datetime
import decimal

from app.config import Settings
from app.models import PaymentStatus, RentLedger
from app.services import notification_service, scheduled_jobs
from app.services.ai_client import AIServiceError

NO_CHANNEL = Settings(discord_management_channel_id=None)
WITH_CHANNEL = Settings(discord_management_channel_id="mgmt-channel")


def _rent_row(db_session, tenant, *, status, balance="500.00"):
    row = RentLedger(
        tenant_id=tenant.id,
        month=datetime.date(2026, 8, 1),
        rent_amount=decimal.Decimal("9500.00"),
        paid_amount=decimal.Decimal("9500.00") - decimal.Decimal(balance),
        balance=decimal.Decimal(balance),
        due_date=datetime.date(2026, 8, 5),
        payment_status=status,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_check_pending_rent_notifies_linked_tenants(db_session, tenant_with_user, monkeypatch):
    tenant, user = tenant_with_user
    user.discord_id = "111122223333"
    db_session.flush()
    _rent_row(db_session, tenant, status=PaymentStatus.PENDING)

    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)
    sent = []
    monkeypatch.setattr(notification_service, "send_discord_dm", lambda discord_id, message: sent.append((discord_id, message)))

    scheduled_jobs.check_pending_rent(db_session)

    assert len(sent) == 1
    assert sent[0][0] == "111122223333"
    assert "500.00" in sent[0][1]


def test_check_pending_rent_skips_unlinked_tenants(db_session, tenant_with_user, monkeypatch):
    tenant, user = tenant_with_user
    assert user.discord_id is None
    _rent_row(db_session, tenant, status=PaymentStatus.OVERDUE)

    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)
    sent = []
    monkeypatch.setattr(notification_service, "send_discord_dm", lambda *a: sent.append(a))

    scheduled_jobs.check_pending_rent(db_session)

    assert sent == []


def test_check_pending_rent_survives_a_notification_failure(db_session, tenant_with_user, monkeypatch):
    tenant, user = tenant_with_user
    user.discord_id = "444455556666"
    db_session.flush()
    _rent_row(db_session, tenant, status=PaymentStatus.PENDING)

    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)

    def _raise(discord_id, message):
        raise notification_service.NotificationError("simulated failure")

    monkeypatch.setattr(notification_service, "send_discord_dm", _raise)

    scheduled_jobs.check_pending_rent(db_session)  # must not raise


def test_check_pending_rent_posts_management_summary_when_channel_configured(db_session, tenant_with_user, monkeypatch):
    tenant, user = tenant_with_user
    user.discord_id = "777788889999"
    db_session.flush()
    _rent_row(db_session, tenant, status=PaymentStatus.PENDING)

    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: WITH_CHANNEL)
    monkeypatch.setattr(notification_service, "send_discord_dm", lambda *a: None)
    channel_posts = []
    monkeypatch.setattr(
        notification_service, "send_channel_message", lambda channel_id, message: channel_posts.append((channel_id, message))
    )

    scheduled_jobs.check_pending_rent(db_session)

    assert len(channel_posts) == 1
    assert channel_posts[0][0] == "mgmt-channel"


def test_check_pending_rent_skips_management_post_when_no_channel_configured(db_session, tenant_with_user, monkeypatch):
    tenant, user = tenant_with_user
    user.discord_id = "888800001111"
    db_session.flush()
    _rent_row(db_session, tenant, status=PaymentStatus.PENDING)

    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)
    monkeypatch.setattr(notification_service, "send_discord_dm", lambda *a: None)
    channel_posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda *a: channel_posts.append(a))

    scheduled_jobs.check_pending_rent(db_session)

    assert channel_posts == []


def test_generate_management_report_posts_ai_summary(db_session, monkeypatch):
    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: WITH_CHANNEL)
    monkeypatch.setattr(scheduled_jobs.ai_client, "generate_summary", lambda stats: "Everything is fine.")
    posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda channel_id, message: posts.append((channel_id, message)))

    scheduled_jobs.generate_management_report(db_session)

    assert posts == [("mgmt-channel", "Everything is fine.")]


def test_generate_management_report_falls_back_when_ai_unavailable(db_session, monkeypatch):
    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: WITH_CHANNEL)

    def _raise(stats):
        raise AIServiceError("down")

    monkeypatch.setattr(scheduled_jobs.ai_client, "generate_summary", _raise)
    posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda channel_id, message: posts.append((channel_id, message)))

    scheduled_jobs.generate_management_report(db_session)

    assert len(posts) == 1
    assert "AI summary unavailable" in posts[0][1]


def test_generate_management_report_skips_when_no_channel_configured(db_session, monkeypatch):
    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)
    posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda *a: posts.append(a))

    scheduled_jobs.generate_management_report(db_session)

    assert posts == []


def test_generate_income_report_posts_summary(db_session, monkeypatch):
    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: WITH_CHANNEL)
    posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda channel_id, message: posts.append((channel_id, message)))

    scheduled_jobs.generate_income_report(db_session)

    assert len(posts) == 1
    assert posts[0][0] == "mgmt-channel"
    assert "Income report" in posts[0][1]


def test_generate_income_report_skips_when_no_channel_configured(db_session, monkeypatch):
    monkeypatch.setattr(scheduled_jobs, "get_settings", lambda: NO_CHANNEL)
    posts = []
    monkeypatch.setattr(notification_service, "send_channel_message", lambda *a: posts.append(a))

    scheduled_jobs.generate_income_report(db_session)

    assert posts == []
