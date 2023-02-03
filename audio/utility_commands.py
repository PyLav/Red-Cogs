from __future__ import annotations

from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_number

from pylav.core.context import PyLavContext
from pylav.extension.red.utils.decorators import always_hidden
from pylav.logging import getLogger
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Player.commands.utils")

_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
class UtilityCommands(DISCORD_COG_TYPE_MIXIN):
    @always_hidden()
    @commands.command(name="__PyLavPlayer_volume_change_by", hidden=True)
    async def command_volume_change_by(self, context: PyLavContext, change_by: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return
        max_volume = await self.pylav.player_config_manager.get_max_volume(context.guild.id)
        new_vol = context.player.volume + change_by
        if new_vol > max_volume:
            await context.player.set_volume(max_volume, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "Volume limit reached, player volume set to {volume_variable_do_not_translate}%"
                    ).format(volume_variable_do_not_translate=humanize_number(context.player.volume)),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif new_vol < 0:
            await context.player.set_volume(0, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Minimum volume reached, player volume set to 0%"), messageable=context
                ),
                ephemeral=True,
            )
        else:
            await context.player.set_volume(new_vol, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Player volume set to {volume_variable_do_not_translate}%").format(
                        volume_variable_do_not_translate=new_vol
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
