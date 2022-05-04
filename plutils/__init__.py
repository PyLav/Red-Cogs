from __future__ import annotations

import asyncio

from pylav.types import BotT

from plutils.cog import PyLavUtils


async def setup(bot: BotT):
    pl_utils = PyLavUtils(bot)
    await bot.add_cog(pl_utils)
    pl_utils._init_task = asyncio.create_task(pl_utils.initialize())
