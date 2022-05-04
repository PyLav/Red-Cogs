from __future__ import annotations

import asyncio

from pylav.types import BotT

from plconfig.cog import PyLavConfigurator


async def setup(bot: BotT):
    pl_configurator = PyLavConfigurator(bot)
    await bot.add_cog(pl_configurator)
    pl_configurator._init_task = asyncio.create_task(pl_configurator.initialize())
