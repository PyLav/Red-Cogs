from __future__ import annotations

import asyncio

from pylavconfig.cog import PyLavConfigurator


async def setup(bot):
    mp = PyLavConfigurator(bot)
    await bot.add_cog(mp)
    mp._init_task = asyncio.create_task(mp.initialize())
