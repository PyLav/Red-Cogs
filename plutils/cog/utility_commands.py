from pathlib import Path

import discord
import ujson
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_number, inline

from pylav import Client
from pylav.converters import QueryConverter
from pylav.track_encoding import decode_track
from pylav.types import BotT
from pylav.utils import PyLavContext

LOGGER = getLogger("red.3pt.PyLavUtils.commands.utils")

_ = Translator("PyLavUtils", Path(__file__))


class UtilityCommands:
    lavalink: Client
    bot: BotT

    @commands.group(name="plutils")
    async def command_plutils(self, context: PyLavContext):
        """Utility commands for the MediaPlayer cog."""

    @commands.is_owner()
    @command_plutils.group(name="get")
    async def command_plutils_get(self, context: PyLavContext):
        """Get info about specific things."""

    @command_plutils.command(name="b64")
    async def command_plutils_get_b64(self, context: PyLavContext):
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

    @command_plutils_get.command(name="author")
    async def command_plutils_get_author(self, context: PyLavContext):
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

    @command_plutils_get.command(name="title")
    async def command_plutils_get_title(self, context: PyLavContext):
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

    @command_plutils_get.command(name="source")
    async def command_plutils_get_source(self, context: PyLavContext):
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

    @command_plutils.command(name="decode")
    async def command_plutils_decode(self, context: PyLavContext, *, base64: str):
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

    @command_plutils.group(name="cache")
    async def command_plutils_cache(self, context: PyLavContext):
        """Manage the query cache."""

    @command_plutils_cache.command(name="clear")
    async def command_plutils_cache_clear(self, context: PyLavContext):
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

    @command_plutils_cache.command(name="older")
    async def command_plutils_cache_older(self, context: PyLavContext, days: int):
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

    @command_plutils_cache.command(name="query")
    async def command_plutils_cache_query(self, context: PyLavContext, *, query: QueryConverter):
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

    @command_plutils_cache.command(name="size")
    async def command_plutils_cache_size(self, context: PyLavContext):
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
