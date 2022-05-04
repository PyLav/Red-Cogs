from __future__ import annotations

import asyncio

from red_commons.logging import getLogger

from pylav.types import BotT

from plplaylists.cog import PyLavPlaylists

LOGGER = getLogger("red.3pt.PyLavPlaylists")


async def setup(bot: BotT):
    pl_playlists = PyLavPlaylists(bot)
    await bot.add_cog(pl_playlists)
    pl_playlists._init_task = asyncio.create_task(pl_playlists.initialize())
