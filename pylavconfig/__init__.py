from __future__ import annotations

import asyncio

from pylav.types import BotT

from pylavconfig.cog import PyLavConfigurator


async def setup(bot: BotT):
    mp = PyLavConfigurator(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
