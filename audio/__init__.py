from __future__ import annotations

from red_commons.logging import getLogger

from pylav.types import BotT

from audio.cog import MediaPlayer

LOGGER = getLogger("red.3pt.mp")


async def setup(bot: BotT):
    mp = MediaPlayer(bot)
    await bot.add_cog(mp)

    await mp.initialize()
