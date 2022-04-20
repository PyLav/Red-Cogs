from __future__ import annotations

from abc import ABC
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from audio.cog import MPMixin
from audio.cog.utils import decorators

LOGGER = getLogger("red.3pt.mp.commands.utils")

_ = Translator("MediaPlayer", Path(__file__))


class UtilityCommands(MPMixin, ABC):
    @decorators.always_hidden()
    @commands.command(name="__volume_change_by", hidden=True)
    async def command_volume_change_by(self, context: commands.Context, change_by: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = self.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return

        volume = player.volume + change_by
        await player.set_volume(volume)
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context, description=_("Player volume set to {volume}%.").format(volume=volume)
            ),
            ephemeral=True,
        )
