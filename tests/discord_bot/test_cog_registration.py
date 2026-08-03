"""Confirms the command tree registers correctly — names, descriptions,
parameters — which is everything about slash-command setup that doesn't
require an actual Discord gateway connection or bot token. What remains
unverified (registering these with Discord itself via tree.sync(), and a
real modal/interaction round-trip) needs a live token — see
docs/ARCHITECTURE.md §12.
"""

import discord
from discord.ext import commands


async def _load_bot() -> commands.Bot:
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
    await bot.load_extension("cogs.tenant_commands")
    return bot


async def test_all_five_commands_register():
    bot = await _load_bot()

    names = {c.name for c in bot.tree.get_commands()}

    assert names == {"link", "rent", "complaint", "rules", "status"}


async def test_complaint_command_has_description_parameter():
    bot = await _load_bot()

    complaint_cmd = next(c for c in bot.tree.get_commands() if c.name == "complaint")

    param_names = [p.name for p in complaint_cmd.parameters]
    assert param_names == ["description"]
    assert complaint_cmd.parameters[0].required


async def test_no_command_takes_extra_user_supplied_arguments():
    """link/rent/rules/status take no arguments — the Discord user id they
    act on always comes from interaction.user, never a client-supplied
    value, mirroring the backend's own tenant-scoping rule
    (docs/ARCHITECTURE.md §7).
    """
    bot = await _load_bot()

    for name in ("link", "rent", "rules", "status"):
        cmd = next(c for c in bot.tree.get_commands() if c.name == name)
        assert cmd.parameters == []
