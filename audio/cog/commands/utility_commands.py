from __future__ import annotations

import json
from abc import ABC
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, inline

from pylav.track_encoding import decode_track
from pylav.utils import PyLavContext

from audio.cog import MPMixin
from audio.cog.utils import decorators

LOGGER = getLogger("red.3pt.mp.commands.utils")

_ = Translator("MediaPlayer", Path(__file__))


class UtilityCommands(MPMixin, ABC):
    @decorators.always_hidden()
    @commands.command(name="__volume_change_by", hidden=True)
    async def command_volume_change_by(self, context: PyLavContext, change_by: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description="Not connected to a voice channel.", messageable=context
                ),
                ephemeral=True,
            )
            return

        volume = player.volume + change_by
        await player.set_volume(volume, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Player volume set to {volume}%.").format(volume=volume), messageable=context
            ),
            ephemeral=True,
        )

    @commands.group(name="mputils")
    async def command_mputils(self, context: PyLavContext):
        """Utility commands for the MediaPlayer cog."""

    @commands.is_owner()
    @command_mputils.group(name="get")
    async def command_mputils_get(self, context: PyLavContext):
        """Get info about specific things."""

    @command_mputils_get.command(name="b64")
    async def command_mputils_get_b64(self, context: PyLavContext, *, guild: discord.Guild = None):
        """Get the base64 of the current track."""
        if guild is None:
            guild = context.guild

        player = context.lavalink.get_player(guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(player.current.track),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="author")
    async def command_mputils_get_author(self, context: PyLavContext, *, guild: discord.Guild = None):
        """Get the author of the current track."""
        if guild is None:
            guild = context.guild

        player = context.lavalink.get_player(guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(player.current.author),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="title")
    async def command_mputils_get_title(self, context: PyLavContext, *, guild: discord.Guild = None):
        """Get the title of the current track."""
        if guild is None:
            guild = context.guild

        player = context.lavalink.get_player(guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(player.current.title),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="source")
    async def command_mputils_get_source(self, context: PyLavContext, *, guild: discord.Guild = None):
        """Get the source of the current track."""
        if guild is None:
            guild = context.guild

        player = context.lavalink.get_player(guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(player.current.source),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils.command(name="decode")
    async def command_mputils_decode(self, context: PyLavContext, *, base64: str):
        """Decode a tracks base64 string into a JSON object."""

        try:
            data, _ = decode_track(base64)
        except Exception:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Invalid base64 string."), messageable=context
                ),
                ephemeral=True,
            )
            return
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=box(lang="json", text=json.dumps(data["info"], indent=2, sort_keys=True)),
                    messageable=context,
                ),
                ephemeral=True,
            )
