from __future__ import annotations

import asyncio

from red_commons.logging import getLogger
from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT

from plplaylists.cog import PyLavPlaylists

LOGGER = getLogger("red.3pt.PyLavPlaylists")

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    pl_playlists = PyLavPlaylists(bot)
    await bot.add_cog(pl_playlists)
    pl_playlists._init_task = asyncio.create_task(pl_playlists.initialize())
