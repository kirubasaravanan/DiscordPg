"""Turns api_client's plain dicts into discord.Embed objects. Kept apart
from cogs/tenant_commands.py so this logic is testable without a live
Discord connection — discord.Embed is a plain data class, no gateway
needed to construct or inspect one.

Status is always icon + label together, never the emoji alone, mirroring
the dataviz skill's status-color rule applied to the dashboard (Phase 4) —
same convention, different medium.
"""

import discord

STATUS_EMOJI = {"PENDING": "⚪", "PARTIAL": "🟠", "PAID": "🟢", "OVERDUE": "🔴"}
COMPLAINT_STATUS_EMOJI = {"OPEN": "🟠", "IN_PROGRESS": "⚪", "RESOLVED": "🟢", "CLOSED": "🟢", "REOPENED": "🟠"}
PRIORITY_EMOJI = {"LOW": "⚪", "MEDIUM": "⚪", "HIGH": "🟠", "URGENT": "🔴"}


def rent_embed(rows: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="Your rent", color=discord.Color.blurple())
    if not rows:
        embed.description = "No rent entries on file yet."
        return embed

    pending = [r for r in rows if r["payment_status"] != "PAID"]
    if pending:
        target = sorted(pending, key=lambda r: r["month"], reverse=True)
    else:
        embed.description = "You're all paid up. Showing your most recent entries:"
        target = sorted(rows, key=lambda r: r["month"], reverse=True)

    for row in target[:5]:
        emoji = STATUS_EMOJI.get(row["payment_status"], "⚪")
        embed.add_field(
            name=f"{row['month']} — {emoji} {row['payment_status']}",
            value=f"₹{row['balance']} due of ₹{row['rent_amount']} (paid ₹{row['paid_amount']})",
            inline=False,
        )
    return embed


def complaint_created_embed(complaint: dict) -> discord.Embed:
    embed = discord.Embed(title="Complaint filed", color=discord.Color.orange())
    embed.add_field(name="Category", value=complaint["category"].title(), inline=True)
    priority_emoji = PRIORITY_EMOJI.get(complaint["priority"], "")
    embed.add_field(name="Priority", value=f"{priority_emoji} {complaint['priority']}", inline=True)
    status_emoji = COMPLAINT_STATUS_EMOJI.get(complaint["status"], "")
    embed.add_field(name="Status", value=f"{status_emoji} {complaint['status']}", inline=True)
    embed.set_footer(text=f"Ticket #{complaint['id'][:8]}")
    return embed


def rules_embed(content: str) -> discord.Embed:
    # Discord embed descriptions cap at 4096 chars; PG rules should stay
    # well under that, but truncate defensively rather than error.
    return discord.Embed(title="PG House Rules", description=content[:4096], color=discord.Color.green())


def faq_answer_embed(answer: str, cited_sources: list[str]) -> discord.Embed:
    embed = discord.Embed(title="PG OS FAQ", description=answer[:4096], color=discord.Color.blurple())
    if cited_sources:
        embed.set_footer(text="Source: " + ", ".join(cited_sources))
    return embed


def complaints_status_embed(complaints: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="Your complaints", color=discord.Color.blurple())
    if not complaints:
        embed.description = "You haven't filed any complaints."
        return embed

    ordered = sorted(complaints, key=lambda c: c["created_at"], reverse=True)[:10]
    for c in ordered:
        emoji = COMPLAINT_STATUS_EMOJI.get(c["status"], "⚪")
        embed.add_field(
            name=f"{emoji} {c['status']} — {c['category'].title()}",
            value=f"{c['description'][:100]}\nTicket #{c['id'][:8]}",
            inline=False,
        )
    return embed
