from __future__ import annotations

from discord import Object
from red_commons.logging import getLogger
from redbot.core.bot import Red

from audio.cog import MediaPlayer

LOGGER = getLogger("red.3pt.mp")


async def setup(bot: Red):
    mp = MediaPlayer(bot)
    await bot.add_cog(mp)

    LOGGER.info("Guild Slash is enabled for %s", 133049272517001216)
    bot.tree.add_command(mp.slash_play, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_now, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_skip, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_stop, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_queue, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_disconnect, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_shuffle, guild=Object(id=133049272517001216))
    bot.tree.add_command(mp.slash_repeat, guild=Object(id=133049272517001216))

    await mp.initialize()
