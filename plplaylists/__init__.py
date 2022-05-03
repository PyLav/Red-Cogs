from __future__ import annotations

import asyncio

from red_commons.logging import getLogger

from pylav.types import BotT

from plplaylists.cog import PyLavPlaylists

LOGGER = getLogger("red.3pt.PyLavPlaylists")


async def setup(bot: BotT):
    mp = PyLavPlaylists(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
