from abc import ABC
from pathlib import Path

import asyncstdlib
import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_number

from pylav.types import PyLavCogMixin
from pylav.utils import PyLavContext
from pylavcogs_shared.utils.decorators import always_hidden

LOGGER = getLogger("red.3pt.PyLavPlayer.commands.utils")

T_ = Translator("PyLavPlayer", Path(__file__))
_ = lambda s: s


@cog_i18n(T_)
class UtilityCommands(PyLavCogMixin, ABC):
    @always_hidden()
    @commands.command(name="__volume_change_by", hidden=True)
    async def command_volume_change_by(self, context: PyLavContext, change_by: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description="Not connected to a voice channel.", messageable=context
                ),
                ephemeral=True,
            )
            return
        config = context.player.config
        max_volume = await asyncstdlib.min(
            [await config.fetch_max_volume(), await self.lavalink.player_manager.global_config.fetch_max_volume()]
        )
        new_vol = context.player.volume + change_by
        if new_vol > max_volume:
            context.player.volume = max_volume
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume limit reached, player volume set to {volume}%.").format(
                        volume=humanize_number(context.player.volume)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif new_vol < 0:
            context.player.volume = 0
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Minimum volume reached, Player volume set to 0%."), messageable=context
                ),
                ephemeral=True,
            )
        await context.player.set_volume(new_vol, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Player volume set to {volume}%.").format(volume=new_vol), messageable=context
            ),
            ephemeral=True,
        )


_ = T_
