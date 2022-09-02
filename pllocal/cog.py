import asyncio
import hashlib
import random
import typing
from functools import partial
from pathlib import Path
from typing import Optional

import asyncstdlib
import discord
from asyncstdlib import heapq
from discord import app_commands
from discord.app_commands import Choice
from rapidfuzz import fuzz
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

import pylavcogs_shared
from pylav import Query
from pylav.sql.models import PlayerModel
from pylav.types import BotT, InteractionT
from pylav.utils import AsyncIter, PyLavContext
from pylavcogs_shared.utils import rgetattr

LOGGER = getLogger("red.3pt.PyLavLocalFiles")

_ = Translator("PyLavLocalFiles", Path(__file__))


async def cache_filled(interaction: InteractionT) -> bool:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    context = await interaction.client.get_context(interaction)
    cog: PyLavLocalFiles = context.bot.get_cog("PyLavLocalFiles")  # type: ignore
    return bool(cog.ready_event.is_set()) and len(cog.cache) > 0


@cog_i18n(_)
class PyLavLocalFiles(commands.Cog):
    """Play local files and folders from the owner configured location"""

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.cache: dict[str, Query] = {}
        self.ready_event = asyncio.Event()

    async def _update_cache(self):
        from pylav.localfiles import LocalFile

        while LocalFile._ROOT_FOLDER is None:
            await asyncio.sleep(1)
        assert LocalFile._ROOT_FOLDER is not None
        temp: dict[str, Query] = {}
        async for file in LocalFile(LocalFile._ROOT_FOLDER).files_in_tree(show_folders=True):
            temp[hashlib.md5(f"{getattr(file._query, 'path', file._query)}".encode()).hexdigest()] = file

        temp = await asyncstdlib.sorted(temp.items(), key=lambda x: str(x[1]._query).lower())  # type: ignore
        self.cache = dict(temp)

    async def initialize(self):
        await self._update_cache()
        self.ready_event.set()

    async def cog_check(self, ctx: PyLavContext):
        return bool(self.ready_event.is_set())

    @commands.group(name="localset")
    async def command_localset(self, ctx: PyLavContext):
        """Configure cog settings"""

    @command_localset.command(name="version")
    async def command_localset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and it's PyLav dependencies"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (self.__class__.__name__, self.__version__),
            ("PyLavCogs-Shared", pylavcogs_shared.__VERSION__),
            ("PyLav", self.bot.lavalink.lib_version),
        ]

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=box(tabulate(data, headers=(_("Library/Cog"), _("Version")), tablefmt="fancy_grid")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_localset.command(name="update")
    @commands.is_owner()
    async def command_localset_update(self, context: PyLavContext) -> None:
        """Update the track list for /local"""
        if isinstance(context, discord.Interaction):
            context = await self.cog.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self._update_cache()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Local track list updated {number} currently present").format(number=len(self.cache)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="local", description=_("Play a local file or folder, supports partial searching"))
    @app_commands.describe(
        entry=_("The local file or folder to play"),
        recursive=_("If entry is a folder, play everything inside of it recursively"),
    )
    @app_commands.guild_only()
    @app_commands.check(cache_filled)
    async def slash_local(
        self,
        interaction: InteractionT,
        entry: str,
        recursive: Optional[bool] = False,
    ):  # sourcery no-metrics
        """Play a local file or folder, supports partial searching"""
        send = partial(interaction.followup.send, wait=True)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        author = interaction.user
        entry = self.cache[entry]
        entry._recursive = recursive
        player = self.lavalink.get_player(interaction.guild.id)
        if player is None:
            config = typing.cast(
                PlayerModel, await self.lavalink.player_config_manager.get_config(interaction.guild.id)
            )
            if (channel := interaction.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.lavalink.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect"),
                            messageable=interaction,
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(interaction.guild.me))
                and permission.connect
                and permission.speak
            ):
                await send(
                    embed=await self.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}").format(
                            channel=channel.mention
                        ),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.lavalink.connect_player(channel=channel, requester=author)

        successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
            entry, requester=author, player=player
        )
        if count:
            if count == 1:
                await player.add(requester=author.id, track=successful[0])
            else:
                await player.bulk_add(requester=author.id, tracks_and_queries=successful)
        single_track = successful[0] if successful else None
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=author)

        if count > 1:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("{track_count} tracks enqueued").format(track_count=count),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        elif count == 1:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("{track} enqueued").format(
                        track=await single_track.get_track_display_name(with_url=True)
                    ),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        else:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("No tracks were found for your query"),
                    messageable=interaction,
                ),
                ephemeral=True,
            )

    @slash_local.autocomplete("entry")
    async def slash_local_autocomplete_entry(self, interaction: InteractionT, current: str):
        entries = []
        if not self.cache:
            return []
        if not current:
            extracted = random.choices(list(self.cache.items()), k=25)
        else:

            async def _filter(x):
                return await asyncio.to_thread(
                    fuzz.token_set_ratio, current, f"{getattr(x[1]._query, 'path', x[1]._query)}"
                )

            extracted = await heapq.nlargest(asyncstdlib.iter(self.cache.items()), n=25, key=_filter)

        async for md5, query in AsyncIter(extracted if current else extracted[::-1]):
            entries.append(
                Choice(name=await query.query_to_string(max_length=99, with_emoji=True, no_extension=True), value=md5)
            )

        return entries
