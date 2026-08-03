"""formatting.py builds plain discord.Embed objects — a data class, not a
live-connection concern — so this is fully real, no mocks needed.
"""

import formatting


def test_faq_answer_embed_shows_answer_and_source():
    embed = formatting.faq_answer_embed("Rent is due on the 5th.", ["rent_policy.md"])
    assert embed.description == "Rent is due on the 5th."
    assert "rent_policy.md" in embed.footer.text


def test_faq_answer_embed_no_footer_when_no_sources():
    embed = formatting.faq_answer_embed("I don't know.", [])
    assert embed.footer.text is None


def test_rent_embed_empty():
    embed = formatting.rent_embed([])
    assert embed.description == "No rent entries on file yet."
    assert len(embed.fields) == 0


def test_rent_embed_shows_pending_first():
    rows = [
        {"month": "2026-07-01", "payment_status": "PAID", "balance": "0.00", "rent_amount": "9500.00", "paid_amount": "9500.00"},
        {"month": "2026-08-01", "payment_status": "PENDING", "balance": "9500.00", "rent_amount": "9500.00", "paid_amount": "0.00"},
    ]

    embed = formatting.rent_embed(rows)

    assert len(embed.fields) == 1
    assert "PENDING" in embed.fields[0].name
    assert "2026-08-01" in embed.fields[0].name


def test_rent_embed_all_paid_shows_recent_history():
    rows = [
        {"month": "2026-07-01", "payment_status": "PAID", "balance": "0.00", "rent_amount": "9500.00", "paid_amount": "9500.00"},
    ]

    embed = formatting.rent_embed(rows)

    assert "all paid up" in embed.description
    assert len(embed.fields) == 1


def test_complaint_created_embed():
    complaint = {
        "id": "9c3e1234-abcd-0000-0000-000000000000",
        "category": "PLUMBING",
        "priority": "HIGH",
        "status": "OPEN",
    }

    embed = formatting.complaint_created_embed(complaint)

    field_values = {f.name: f.value for f in embed.fields}
    assert field_values["Category"] == "Plumbing"
    assert "HIGH" in field_values["Priority"]
    assert "OPEN" in field_values["Status"]
    assert "9c3e1234" in embed.footer.text


def test_rules_embed_truncates_to_discord_limit():
    long_content = "x" * 5000

    embed = formatting.rules_embed(long_content)

    assert len(embed.description) == 4096


def test_complaints_status_embed_empty():
    embed = formatting.complaints_status_embed([])
    assert "haven't filed" in embed.description


def test_complaints_status_embed_orders_newest_first():
    complaints = [
        {"id": "aaaaaaaa-0000", "status": "RESOLVED", "category": "CLEANING", "description": "x", "created_at": "2026-07-01T00:00:00Z"},
        {"id": "bbbbbbbb-0000", "status": "OPEN", "category": "WIFI", "description": "y", "created_at": "2026-08-01T00:00:00Z"},
    ]

    embed = formatting.complaints_status_embed(complaints)

    assert "Wifi" in embed.fields[0].name
    assert "Cleaning" in embed.fields[1].name
