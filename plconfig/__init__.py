from __future__ import annotations

import asyncio

from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT

from plconfig.cog import PyLavConfigurator

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    pl_configurator = PyLavConfigurator(bot)
    await bot.add_cog(pl_configurator)
    pl_configurator._init_task = asyncio.create_task(pl_configurator.initialize())
