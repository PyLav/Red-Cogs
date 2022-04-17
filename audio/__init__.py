from __future__ import annotations

from redbot.core.bot import Red

from audio.cog import MediaPlayer


async def setup(bot: Red):
    cog = MediaPlayer(bot)
    await bot.add_cog(cog)
    await cog.initialize()
