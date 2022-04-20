from __future__ import annotations

from red_commons.logging import getLogger
from redbot.core.bot import Red

from audio.cog import MediaPlayer

LOGGER = getLogger("red.3pt.mp")


async def setup(bot: Red):
    mp = MediaPlayer(bot)
    await bot.add_cog(mp)

    await mp.initialize()
