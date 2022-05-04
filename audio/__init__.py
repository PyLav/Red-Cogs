from __future__ import annotations

import asyncio

from red_commons.logging import getLogger

from pylav.types import BotT

from audio.cog import PyLavPlayer

LOGGER = getLogger("red.3pt.PyLavPlayer")


async def setup(bot: BotT):
    plplayer = PyLavPlayer(bot)
    await bot.add_cog(plplayer)
    plplayer._init_task = asyncio.create_task(plplayer.initialize())
