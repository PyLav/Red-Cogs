from __future__ import annotations

import asyncio

from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT

from plnodes.cog import PyLavNodes

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    plnodes = PyLavNodes(bot)
    await bot.add_cog(plnodes)
    plnodes._init_task = asyncio.create_task(plnodes.initialize())
