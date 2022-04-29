from __future__ import annotations

import asyncio

from mpnotifier.notifier import MPNotifier


async def setup(bot):
    mp = MPNotifier(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
