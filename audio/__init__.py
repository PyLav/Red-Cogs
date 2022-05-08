from __future__ import annotations

import asyncio

from red_commons.logging import getLogger
from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT

from audio.cog import PyLavPlayer

LOGGER = getLogger("red.3pt.PyLavPlayer")

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    plplayer = PyLavPlayer(bot)
    await bot.add_cog(plplayer)
    plplayer._init_task = asyncio.create_task(plplayer.initialize())
