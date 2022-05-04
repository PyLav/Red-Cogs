from __future__ import annotations

import asyncio

from pylav.types import BotT

from plmigrator.cog import PyLavMigrator


async def setup(bot: BotT):
    pl_migrator = PyLavMigrator(bot)
    await bot.add_cog(pl_migrator)
    pl_migrator._init_task = asyncio.create_task(pl_migrator.initialize())
