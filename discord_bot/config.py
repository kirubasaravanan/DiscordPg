import os

from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

# Required to actually run the bot (main.py) — not required to import
# api_client.py, so that module stays testable without a token.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# Optional: a single guild ID for instant command sync during development.
# Unset means a global sync, which can take up to an hour to propagate —
# see https://discord.com/developers/docs/interactions/application-commands.
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID")
