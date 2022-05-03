from __future__ import annotations

import asyncio

from pylav.types import BotT

from plnotifier.notifier import MPNotifier


async def setup(bot: BotT):
    mp = MPNotifier(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
