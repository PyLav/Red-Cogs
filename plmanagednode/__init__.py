from __future__ import annotations

from redbot.core.utils import get_end_user_data_statement

from pylav.extension.red.utils.required_methods import pylav_auto_setup
from pylav.type_hints.bot import DISCORD_BOT_TYPE

from plmanagednode.cog import PyLavManagedNode

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: DISCORD_BOT_TYPE):
    await pylav_auto_setup(bot, PyLavManagedNode)
