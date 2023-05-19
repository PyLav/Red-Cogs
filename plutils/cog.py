from __future__ import annotations

import asyncio
import linecache
import logging
import tracemalloc
from io import StringIO
from pathlib import Path

import discord
from discord import AppCommandType
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_number, inline, pagify
from rich.console import Console
from rich.tree import Tree
from tabulate import tabulate

from pylav.compat import json
from pylav.core.context import PyLavContext
from pylav.exceptions.request import HTTPException
from pylav.extension.red.utils.decorators import requires_player
from pylav.helpers.discord.converters.queries import QueryConverter
from pylav.helpers.format.ascii import EightBitANSI
from pylav.logging import getLogger
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Utils")

_ = Translator("PyLavUtils", Path(__file__))


def get_top(snapshot, key_type="lineno", limit=10):
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    top_stats = snapshot.statistics(key_type)
    response = ""
    response += f"Top {limit} lines"
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        response += f"\n\n#{index}: {frame.filename}:{frame.lineno}: {stat.size / 1024:.1f} KiB"
        if line := linecache.getline(frame.filename, frame.lineno).strip():
            response += f"\n    {line}"

    if other := top_stats[limit:]:
        size = sum(stat.size for stat in other)
        response += f"\n\n{len(other)} other: {size / 1024:.1f} KiB"
    total = sum(stat.size for stat in top_stats)
    response += f"\n\nTotal allocated size: {total / 1024:.1f} KiB"
    return response


@cog_i18n(_)
class PyLavUtils(DISCORD_COG_TYPE_MIXIN):
    """Utility commands for PyLav"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="plutils")
    async def command_plutils(self, context: PyLavContext):
        """Utility commands for PyLav"""

    @command_plutils.command(name="version")
    async def command_plutils_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and PyLav"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (EightBitANSI.paint_white(self.__class__.__name__), EightBitANSI.paint_blue(self.__version__)),
            (EightBitANSI.paint_white("PyLav"), EightBitANSI.paint_blue(context.pylav.lib_version)),
        ]

        await context.send(
            embed=await context.pylav.construct_embed(
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Library / Cog"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Version"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils.command(name="slashes")
    async def command_plutils_slashes(self, context: PyLavContext):
        """Show the slashes available in the bot.

        Author: TrustyJAID#0001 via code block on Discord channel.
        """

        def rich_walk_commands(group: list, tree: Tree):
            for command in group:
                if isinstance(command, discord.app_commands.Group):
                    branch = tree.add(command.name, style="green")
                    rich_walk_commands(command.commands, branch)
                elif isinstance(command, discord.app_commands.Command):
                    tree.add(command.name, style="not bold white")
                elif isinstance(command, discord.app_commands.ContextMenu):
                    if command.type == AppCommandType.user:
                        tree.add(
                            _("{command_name_do_not_translate} # User menu").format(
                                command_name_do_not_translate=command.name
                            ),
                            style="not bold cyan",
                        )
                    elif command.type == AppCommandType.message:
                        tree.add(
                            _("{command_name_do_not_translate} # Message menu").format(
                                command_name_do_not_translate=command.name
                            ),
                            style="not bold magenta",
                        )
                    else:
                        tree.add(
                            _("{command_name_do_not_translate} # Unknown menu").format(
                                command_name_do_not_translate=command.name
                            ),
                            style="not bold yellow",
                        )
                else:
                    tree.add(command.name, style="not bold red")

        all_commands = self.bot.tree.get_commands()
        rich_tree = Tree("Slash Commands", style="bold yellow")

        rich_walk_commands(all_commands, rich_tree)
        temp_console = Console(  # Prevent messing with STDOUT's console
            color_system="standard",  # Discord only supports 8-bit in colors
            file=StringIO(),
            force_terminal=True,
            force_interactive=False,
            width=40,
        )
        temp_console.print(rich_tree)
        msg = "\n".join(line.rstrip() for line in temp_console.file.getvalue().split("\n"))  # type: ignore
        await context.send_interactive(messages=pagify(msg), box_lang="ansi")

    @command_plutils.group(name="get")
    @requires_player()
    async def command_plutils_get(self, context: PyLavContext):
        """Get info about specific things"""

    @command_plutils_get.command(name="b64")
    async def command_plutils_get_b64(self, context: PyLavContext):
        """Get the base64 of the current track"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You must be in a voice channel, so I can connect to it."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.pylav.construct_embed(
                description=inline(context.player.current.encoded),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils_get.command(name="author")
    async def command_plutils_get_author(self, context: PyLavContext):
        """Get the author of the current track"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You must be in a voice channel, so I can connect to it."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.pylav.construct_embed(
                description=inline(await context.player.current.author()),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils_get.command(name="title")
    async def command_plutils_get_title(self, context: PyLavContext):
        """Get the title of the current track"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You must be in a voice channel, so I can connect to it."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.pylav.construct_embed(
                description=inline(await context.player.current.title()),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils_get.command(name="source")
    async def command_plutils_get_source(self, context: PyLavContext):
        """Get the source of the current track"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You must be in a voice channel, so I can connect to it."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        await context.send(
            embed=await context.pylav.construct_embed(
                description=inline(await context.player.current.source()),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils_get.command(name="player")
    @commands.is_owner()
    async def command_plutils_get_api(self, context: PyLavContext):
        """Get the API of the current track"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You must be in a voice channel, so I can connect to it."), messageable=context
                ),
                ephemeral=True,
            )
            return

        try:
            node_player = await context.player.fetch_node_player()
        except Exception:  # noqa
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Unable to get player info."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if isinstance(node_player, HTTPException):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Unable to get player info."), messageable=context
                ),
                ephemeral=True,
            )
            return
        data = node_player.to_dict()
        await context.send(
            embed=await context.pylav.construct_embed(
                description=box(json.dumps(data, indent=2), lang="json"),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plutils.command(name="decode")
    async def command_plutils_decode(self, context: PyLavContext, *, base64: str):
        """Decode the track base64 string into a JSON object"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        try:
            data = await self.pylav.decode_track(base64, raise_on_failure=True)
        except Exception:  # noqa
            await context.send(
                embed=await context.pylav.construct_embed(description=_("Invalid base64 string."), messageable=context),
                ephemeral=True,
            )
            return
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=box(lang="json", text=json.dumps(data.info.to_dict(), indent=2, sort_keys=True)),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @commands.is_owner()
    @command_plutils.group(name="cache")
    async def command_plutils_cache(self, context: PyLavContext):
        """Manage the query cache"""

    @command_plutils_cache.command(name="clear")
    async def command_plutils_cache_clear(self, context: PyLavContext):
        """Clear the query cache"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.pylav.query_cache_manager.wipe()
        await context.send(
            embed=await context.pylav.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_plutils_cache.command(name="older")
    async def command_plutils_cache_older(self, context: PyLavContext, days: int):
        """Clear the query cache older than a number of days"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if days > 31:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Days must be less than 31."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif days < 1:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Days must be greater than 1."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await self.pylav.query_cache_manager.delete_older_than(days=days)
        await context.send(
            embed=await context.pylav.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_plutils_cache.command(name="query")
    async def command_plutils_cache_query(self, context: PyLavContext, *, query: QueryConverter):
        """Clear the query cache for a query"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.pylav.query_cache_manager.delete_query(query)
        await context.send(
            embed=await context.pylav.construct_embed(description=_("Query cache cleared."), messageable=context),
            ephemeral=True,
        )

    @command_plutils_cache.command(name="size")
    async def command_plutils_cache_size(self, context: PyLavContext):
        """Get the size of the query cache"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Query cache size: `{size_variable_do_not_translate}`.").format(
                    size_variable_do_not_translate=humanize_number(await self.pylav.query_cache_manager.size())
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.is_owner()
    @command_plutils.command(name="trace", hidden=True)
    async def command_plutils_trace(self, context: PyLavContext, value: int = -1):
        """Start memory tracing

        `[p]plutils trace 0` turns off tracing
        `[p]plutils trace 1` turns on tracing
        `[p]plutils trace` shows the current status of tracing
        """
        import tracemalloc

        if tracemalloc.is_tracing():
            snap = await asyncio.to_thread(tracemalloc.take_snapshot)
            if value == 0:
                tracemalloc.stop()
                await context.send(
                    embed=await context.pylav.construct_embed(
                        description=_("I have stopped memory tracing"),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
        elif not tracemalloc.is_tracing() and value == 1:
            tracemalloc.start(25)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have started memory tracing."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if not tracemalloc.is_tracing():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You need to start tracing first."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            messages = pagify(await asyncio.to_thread(get_top, snap, limit=10), page_length=3500)  # noqa
            await context.send_interactive(messages, box_lang="py")

    @commands.is_owner()
    @command_plutils.command(name="logger")
    async def command_plutils_logger(self, context: PyLavContext, *, level: int):
        """Set the logger level

        Levels are the following:
        0: Critical
        1: Error
        2: Warning
        3: Info
        4: Debug
        5: Verbose
        6: Trace
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        level_map = {
            0: logging.CRITICAL,
            1: logging.ERROR,
            2: logging.WARNING,
            3: logging.INFO,
            4: logging.DEBUG,
            5: logging.DEBUG - 3,
            6: logging.DEBUG - 5,
        }
        if level not in level_map:
            await context.send_help()
            return
        logger = getLogger("PyLav")
        logger.setLevel(level_map[level])
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Logger level set to `{level_variable_do_not_translate}`.").format(
                    level_variable_do_not_translate=logging.getLevelName(logger.level)
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
