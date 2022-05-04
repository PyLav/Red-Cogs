from __future__ import annotations

import asyncio

from pylav.types import BotT

from plnotifier.cog import PyLavNotifier


async def setup(bot: BotT):
    pl_notifier = PyLavNotifier(bot)
    await bot.add_cog(pl_notifier)
    pl_notifier._init_task = asyncio.create_task(pl_notifier.initialize())
