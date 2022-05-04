from __future__ import annotations

import asyncio

from pylav.types import BotT

from plnotifier.cog import PyLavNotifier


async def setup(bot: BotT):
    mp = PyLavNotifier(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
