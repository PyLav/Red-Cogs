from __future__ import annotations

import asyncio

from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT

from pllocal.cog import PyLavLocalFiles

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    pl_utils = PyLavLocalFiles(bot)
    await bot.add_cog(pl_utils)
    pl_utils._init_task = asyncio.create_task(pl_utils.initialize())
