from __future__ import annotations

from redbot.core.bot import Red

from audio.cog import MediaPlayer


async def setup(bot: Red):
    media_player = MediaPlayer(bot)
    await bot.add_cog(media_player)
    await media_player.initialize()
