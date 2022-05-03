from __future__ import annotations

import asyncio

from pylav.types import BotT

from plmigrator.cog import PyLavMigrator


async def setup(bot: BotT):
    mp = PyLavMigrator(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
