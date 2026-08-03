"""The 4 tenant-facing commands from CLAUDE.md's Discord Bot Requirements,
plus /link. Every command is a thin wrapper: resolve the caller's Discord
id, call api_client, format the result — no business logic lives here,
per docs/ARCHITECTURE.md §4.1 ("every command call is a call to a FastAPI
endpoint"). All responses are ephemeral (visible only to the caller) since
rent balances and complaint details are personal, not public-channel
content.
"""

import discord
from discord import app_commands
from discord.ext import commands

import api_client
import formatting


class LinkModal(discord.ui.Modal, title="Link your PG OS account"):
    """A modal, not inline slash-command options, so the password never
    appears in a message or command-invocation log — Discord has no native
    masked/password field for modals, but this at least keeps it out of
    chat history and out of any bot that logs command arguments.
    """

    identifier = discord.ui.TextInput(label="Email or phone", placeholder="you@example.com", max_length=255)
    password = discord.ui.TextInput(label="Password", style=discord.TextStyle.short, max_length=255)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        discord_id = str(interaction.user.id)
        try:
            session = await api_client.link(discord_id, self.identifier.value, self.password.value)
        except api_client.APIError as exc:
            await interaction.response.send_message(f"Couldn't link your account: {exc.message}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Linked as **{session.identifier}** ({session.role}). "
            "Try `/rent`, `/complaint`, `/rules`, or `/status`.",
            ephemeral=True,
        )


_FAILED = object()


async def _run(interaction: discord.Interaction, coro):
    """Awaits an api_client call; on failure, sends the (single) ephemeral
    response itself and returns a sentinel so the caller knows to stop.
    NotLinkedError and APIError never propagate past this point.
    """
    try:
        return await coro
    except api_client.NotLinkedError:
        await interaction.response.send_message("Run `/link` first to connect your PG OS account.", ephemeral=True)
        return _FAILED
    except api_client.APIError as exc:
        await interaction.response.send_message(f"Couldn't complete that: {exc.message}", ephemeral=True)
        return _FAILED


class TenantCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="link", description="Link your Discord account to your PG OS account")
    async def link(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(LinkModal())

    @app_commands.command(name="rent", description="Show your pending rent")
    async def rent(self, interaction: discord.Interaction) -> None:
        rows = await _run(interaction, api_client.get_tenant_rent(str(interaction.user.id)))
        if rows is _FAILED:
            return
        await interaction.response.send_message(embed=formatting.rent_embed(rows), ephemeral=True)

    @app_commands.command(name="complaint", description="File a maintenance or service complaint")
    @app_commands.describe(description="What's the issue?")
    async def complaint(self, interaction: discord.Interaction, description: str) -> None:
        created = await _run(interaction, api_client.file_complaint(str(interaction.user.id), description))
        if created is _FAILED:
            return
        await interaction.response.send_message(embed=formatting.complaint_created_embed(created), ephemeral=True)

    @app_commands.command(name="rules", description="Show the PG house rules")
    async def rules(self, interaction: discord.Interaction) -> None:
        content = await _run(interaction, api_client.get_rules(str(interaction.user.id)))
        if content is _FAILED:
            return
        await interaction.response.send_message(embed=formatting.rules_embed(content), ephemeral=True)

    @app_commands.command(name="status", description="Show the status of your complaints")
    async def status(self, interaction: discord.Interaction) -> None:
        complaints = await _run(interaction, api_client.list_own_complaints(str(interaction.user.id)))
        if complaints is _FAILED:
            return
        await interaction.response.send_message(embed=formatting.complaints_status_embed(complaints), ephemeral=True)

    @app_commands.command(name="ask", description="Ask a question about PG rules, rent policy, or maintenance")
    @app_commands.describe(question="What do you want to know?")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        result = await _run(interaction, api_client.ask_faq(str(interaction.user.id), question))
        if result is _FAILED:
            return
        embed = formatting.faq_answer_embed(result["answer"], result["cited_sources"])
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TenantCommands(bot))
