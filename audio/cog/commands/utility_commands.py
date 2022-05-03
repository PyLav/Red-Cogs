from abc import ABC
from pathlib import Path

import discord
import ujson
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_number, inline

from pylav.converters import QueryConverter
from pylav.track_encoding import decode_track
from pylav.utils import PyLavContext

from audio.cog.abc import MPMixin
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
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description="Not connected to a voice channel.", messageable=context
                ),
                ephemeral=True,
            )
            return
        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        max_volume = min(await config.get_max_volume(), await self.lavalink.player_manager.global_config.fetch_volume())
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

    @commands.group(name="mputils")
    async def command_mputils(self, context: PyLavContext):
        """Utility commands for the MediaPlayer cog."""

    @commands.is_owner()
    @command_mputils.group(name="get")
    async def command_mputils_get(self, context: PyLavContext):
        """Get info about specific things."""

    @command_mputils_get.command(name="b64")
    async def command_mputils_get_b64(self, context: PyLavContext):
        """Get the base64 of the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(context.player.current.track),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="author")
    async def command_mputils_get_author(self, context: PyLavContext):
        """Get the author of the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(context.player.current.author),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="title")
    async def command_mputils_get_title(self, context: PyLavContext):
        """Get the title of the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(context.player.current.title),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils_get.command(name="source")
    async def command_mputils_get_source(self, context: PyLavContext):
        """Get the source of the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=inline(context.player.current.source),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_mputils.command(name="decode")
    async def command_mputils_decode(self, context: PyLavContext, *, base64: str):
        """Decode a tracks base64 string into a JSON object."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        try:
            data, __ = decode_track(base64)
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
                    description=box(lang="json", text=ujson.dumps(data["info"], indent=2, sort_keys=True)),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_mputils.group(name="cache")
    async def command_mputils_cache(self, context: PyLavContext):
        """Manage the query cache."""

    @command_mputils_cache.command(name="clear")
    async def command_mputils_cache_clear(self, context: PyLavContext):
        """Clear the query cache."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.lavalink.query_cache_manager.wipe()
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_mputils_cache.command(name="older")
    async def command_mputils_cache_older(self, context: PyLavContext, days: int):
        """Clear the query cache older than a number of days."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.lavalink.query_cache_manager.delete_older_than(days=days)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_mputils_cache.command(name="query")
    async def command_mputils_cache_query(self, context: PyLavContext, *, query: QueryConverter):
        """Clear the query cache for a query."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.lavalink.query_cache_manager.delete_query(query)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_mputils_cache.command(name="size")
    async def command_mputils_cache_size(self, context: PyLavContext):
        """Get the size of the query cache."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Query cache size: `{size}`.").format(
                    size=humanize_number(await self.lavalink.query_cache_manager.size())
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
