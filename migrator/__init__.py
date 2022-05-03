from __future__ import annotations

import asyncio

from pylav.types import BotT

from migrator.cog import AudioToPyLav


async def setup(bot: BotT):
    mp = AudioToPyLav(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
