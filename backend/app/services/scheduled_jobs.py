"""APScheduler job bodies (docs/ARCHITECTURE.md §9). Registered with real
cron triggers in app/main.py's lifespan. Each function opens and closes its
own DB session — jobs run outside any request, so there's no request-scoped
`get_db` to depend on — and catches its own exceptions so one bad run
(Discord down, AI down, whatever) never crashes the scheduler or blocks the
next job.

Unverified against a live Discord/Ollama in this environment — see
docs/AI_DESIGN.md §7 and docs/ARCHITECTURE.md §12 items 25, 27.
"""

import datetime
import decimal
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import SessionLocal
from app.models import PaymentStatus, RentLedger, Tenant, User
from app.services import ai_client, dashboard_service, notification_service

logger = logging.getLogger(__name__)


def _json_safe(value):
    """Recursively converts Decimal/date/datetime to JSON-native types —
    dashboard_service's stats dicts contain Decimal values that ai_client's
    plain json.dumps-based POST can't serialize as-is.
    """
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _format_stats_fallback(stats: dict) -> str:
    """Plain-text stand-in for build_management_summary() when the AI
    service is unavailable — management still gets a report, just not a
    narrated one. Same graceful-degradation philosophy as
    complaint_service._classify()'s fallback.
    """
    occ, rent, comp, exp = stats["occupancy"], stats["rent"], stats["complaints"], stats["expenses"]
    return (
        f"Daily summary (AI summary unavailable): {occ['occupied_beds']}/{occ['total_beds']} beds occupied. "
        f"Rent collected this month: ₹{rent['collected_this_month']:.2f}, "
        f"pending: ₹{rent['pending_this_month']:.2f}, overdue entries: {rent['overdue_count']}. "
        f"Complaints — open: {comp['open']}, in progress: {comp['in_progress']}, urgent: {comp['urgent']}. "
        f"Expenses this month: ₹{exp['this_month']:.2f}."
    )


def build_management_summary(db: Session) -> str:
    """Shared by GET /api/v1/reports/summary (on-demand) and the daily
    21:00 job — one function, two callers, so they never drift apart.
    """
    stats = dashboard_service.get_dashboard_summary(db)
    try:
        return ai_client.generate_summary(_json_safe(stats))
    except ai_client.AIServiceError as exc:
        logger.warning("AI summary unavailable, using fallback: %s", exc)
        return _format_stats_fallback(stats)


def check_pending_rent(db: Session | None = None) -> None:
    """Daily 08:00. No AI involved — a plain query + notification fan-out.

    `db` is normally omitted (APScheduler calls this with no arguments,
    exactly like the production path always has) — the parameter exists
    so tests can inject the same isolated, rolled-back-after-test session
    every other fixture uses, matching app/database/seed.py's `seed()`.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        rows = (
            db.query(RentLedger)
            .filter(RentLedger.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.OVERDUE]))
            .all()
        )
        notified = 0
        for row in rows:
            tenant = db.get(Tenant, row.tenant_id)
            if tenant is None or tenant.user_id is None:
                continue
            user = db.get(User, tenant.user_id)
            if user is None or not user.discord_id:
                continue  # tenant hasn't run /link — nothing to notify
            message = (
                f"Reminder: your rent for {row.month:%B %Y} has a balance of "
                f"₹{row.balance:.2f} ({row.payment_status.value}). Check /rent in Discord for details."
            )
            try:
                notification_service.send_discord_dm(user.discord_id, message)
                notified += 1
            except notification_service.NotificationError as exc:
                logger.warning("Could not notify tenant %s of pending rent: %s", tenant.id, exc)

        settings = get_settings()
        if rows and settings.discord_management_channel_id:
            summary = f"Pending rent check: {len(rows)} entries need attention, {notified} tenant(s) notified."
            try:
                notification_service.send_channel_message(settings.discord_management_channel_id, summary)
            except notification_service.NotificationError as exc:
                logger.warning("Could not post pending-rent summary to management channel: %s", exc)
    except Exception:
        logger.exception("check_pending_rent job failed")
    finally:
        if owns_session:
            db.close()


def generate_management_report(db: Session | None = None) -> None:
    """Daily 21:00. See check_pending_rent() for why `db` is optional."""
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        settings = get_settings()
        if not settings.discord_management_channel_id:
            logger.info("DISCORD_MANAGEMENT_CHANNEL_ID not set — skipping management report.")
            return
        summary = build_management_summary(db)
        notification_service.send_channel_message(settings.discord_management_channel_id, summary)
    except Exception:
        logger.exception("generate_management_report job failed")
    finally:
        if owns_session:
            db.close()


def generate_income_report(db: Session | None = None) -> None:
    """Monthly, 1st at 09:00 — the prior/current month's rent vs. expenses.
    See check_pending_rent() for why `db` is optional.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        settings = get_settings()
        if not settings.discord_management_channel_id:
            logger.info("DISCORD_MANAGEMENT_CHANNEL_ID not set — skipping income report.")
            return
        row = dashboard_service.get_income_report(db, months=1)[0]
        message = (
            f"Income report for {row['month']:%B %Y}: rent collected ₹{row['rent_collected']:.2f}, "
            f"expenses ₹{row['expenses']:.2f}, net ₹{row['net']:.2f}."
        )
        notification_service.send_channel_message(settings.discord_management_channel_id, message)
    except Exception:
        logger.exception("generate_income_report job failed")
    finally:
        if owns_session:
            db.close()
