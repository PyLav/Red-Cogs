from __future__ import annotations

import asyncio

from pylav.types import BotT

from plnodes.cog import PyLavNodes


async def setup(bot: BotT):
    plnodes = PyLavNodes(bot)
    await bot.add_cog(plnodes)
    plnodes._init_task = asyncio.create_task(plnodes.initialize())
