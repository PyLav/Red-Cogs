from abc import ABC
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_number

from pylav import getLogger
from pylav.red_utils.utils.decorators import always_hidden
from pylav.types import PyLavCogMixin
from pylav.utils import PyLavContext

LOGGER = getLogger("PyLav.cog.Player.commands.utils")

_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
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
                    description=_("Not connected to a voice channel"), messageable=context
                ),
                ephemeral=True,
            )
            return
        max_volume = await self.lavalink.player_config_manager.get_max_volume(context.guild.id)
        new_vol = context.player.volume + change_by
        if new_vol > max_volume:
            await context.player.set_volume(max_volume, requester=context.author)
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume limit reached, player volume set to {volume}%").format(
                        volume=humanize_number(context.player.volume)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif new_vol < 0:
            await context.player.set_volume(0, requester=context.author)
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Minimum volume reached, player volume set to 0%"), messageable=context
                ),
                ephemeral=True,
            )
        else:
            await context.player.set_volume(new_vol, requester=context.author)
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player volume set to {volume}%").format(volume=new_vol), messageable=context
                ),
                ephemeral=True,
            )
