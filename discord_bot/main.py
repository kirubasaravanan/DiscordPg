"""Bot entrypoint. Not verified against a live Discord connection in this
environment — no bot token exists here (see docs/ARCHITECTURE.md §12).
Everything below follows discord.py's documented setup pattern; the actual
gateway connection, command sync, and modal/interaction round-trip need a
real token to exercise.
"""

import logging

import discord
from discord.ext import commands

from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pgos-bot")

# No privileged intents (message content, members, presences) needed — slash
# commands deliver interaction.user directly in the interaction payload, not
# via the gateway's member/message cache.
intents = discord.Intents.default()


class PGOSBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)  # prefix unused — slash commands only

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.tenant_commands")
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d commands to guild %s (instant propagation)", len(synced), DISCORD_GUILD_ID)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d commands globally (can take up to an hour to propagate)", len(synced))


bot = PGOSBot()


@bot.event
async def on_ready() -> None:
    user = bot.user
    logger.info("Logged in as %s (id=%s)", user, user.id if user else "unknown")


def main() -> None:
    if not DISCORD_BOT_TOKEN:
        raise SystemExit(
            "DISCORD_BOT_TOKEN is not set. Copy .env.example to .env and fill in a real token from "
            "https://discord.com/developers/applications before running the bot."
        )
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
