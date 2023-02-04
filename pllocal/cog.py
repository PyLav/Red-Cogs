from __future__ import annotations

import asyncio
import contextlib
import hashlib
import heapq
import os.path
import pathlib
import re
import typing
from functools import partial
from itertools import islice
from pathlib import Path

import discord
from discord import app_commands
from discord.app_commands import Choice
from rapidfuzz import fuzz
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate
from watchfiles import Change, awatch

from pylav.core.context import PyLavContext
from pylav.extension.red.utils import rgetattr
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.query.local_files import LocalFile
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

LOGGER = getLogger("PyLav.cog.LocalFiles")


_ = Translator("PyLavLocalFiles", Path(__file__))

REGEX_FILE_NAME = re.compile(r"[.\-_/\\ ]+")


async def cache_filled(interaction: DISCORD_INTERACTION_TYPE) -> bool:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    context = await interaction.client.get_context(interaction)
    cog: PyLavLocalFiles = context.bot.get_cog("PyLavLocalFiles")  # type: ignore
    return bool(cog.ready_event.is_set()) and len(cog.cache) > 0


@cog_i18n(_)
class PyLavLocalFiles(DISCORD_COG_TYPE_MIXIN):
    """Play local files and folders from the owner configured location"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.cache: dict[str, Query] = {}
        self.ready_event = asyncio.Event()
        self.__load_locals_task: asyncio.Task | None = None
        self.__monitor_task = asyncio.create_task(self.file_watcher())

    async def file_watcher(self):
        await self.pylav.wait_until_ready()
        # noinspection PyProtectedMember
        with contextlib.suppress(Exception):
            async for changes in awatch(pathlib.Path(LocalFile._ROOT_FOLDER), recursive=True):
                await self._process_changes(changes)

    async def _process_changes(self, changes: set[tuple[Change, str]]) -> None:
        for change, path in changes:
            if change == Change.added:
                await self._process_added(path)
                LOGGER.verbose(f"Added {path}")
            elif change == Change.modified:
                await self._process_modified(path)
                LOGGER.verbose(f"Modified {path}")
            elif change == Change.deleted:
                await self._process_deleted(path)
                LOGGER.verbose(f"Deleted {path}")

    async def _process_added(self, path: str) -> None:
        query = await Query.from_string(path)
        # noinspection PyProtectedMember
        self.cache[hashlib.md5(f"{query._query}".encode()).hexdigest()] = query
        if os.path.isdir(path):
            return
        with contextlib.suppress(Exception):
            await self.pylav.get_tracks(query)

    async def _process_modified(self, path: str) -> None:
        query = await Query.from_string(path)
        # noinspection PyProtectedMember
        self.cache[hashlib.md5(f"{query._query}".encode()).hexdigest()] = query
        if os.path.isdir(path):
            return
        with contextlib.suppress(Exception):
            await self.pylav.get_tracks(query, bypass_cache=True)

    async def _process_deleted(self, path: str) -> None:
        query = await Query.from_string(path)
        # noinspection PyProtectedMember
        self.cache.pop(hashlib.md5(f"{query._query}".encode()).hexdigest(), None)

    @staticmethod
    def _filter_is_folder_alphabetical(x: list[Query]) -> tuple[int, str]:
        # noinspection PyProtectedMember
        string = f"{x[1]._query}"
        return -1 if os.path.isdir(string) else 2, string

    async def _update_cache(self):
        await self.pylav.wait_until_ready()
        temp: dict[str, Query] = {}
        # noinspection PyProtectedMember
        async for file in LocalFile(LocalFile._ROOT_FOLDER).files_in_tree(show_folders=True):
            # noinspection PyProtectedMember
            temp[hashlib.md5(f"{file._query}".encode()).hexdigest()] = file

        extracted: typing.Iterable[tuple[str, Query]] = heapq.nsmallest(len(temp.items()), temp.items(), key=self._filter_is_folder_alphabetical)  # type: ignore
        self.cache = dict(extracted)
        self.__load_local_files()

    def __load_local_files(self):
        LOGGER.debug("Loading local files into cache")
        if self.__load_locals_task is not None:
            self.__load_locals_task.cancel()
        self.__load_locals_task = asyncio.create_task(
            self.pylav.get_all_tracks_for_queries(
                *self.cache.values(), partial=False, enqueue=False, requester=self.bot.user, player=None
            )
        )
        self.__load_locals_task.add_done_callback(self.__load_local_files_done_callback)
        self.__load_locals_task.set_name("Load Local Files Task")

    @staticmethod
    def __load_local_files_done_callback(task: asyncio.Task) -> None:
        if (exc := task.exception()) is not None:
            name = task.get_name()
            LOGGER.warning("%s encountered an exception!", name)
            LOGGER.debug("%s encountered an exception!", name, exc_info=exc)

    async def initialize(self):
        await self._update_cache()
        self.ready_event.set()

    async def cog_unload(self) -> None:
        if self.__load_locals_task is not None:
            self.__load_locals_task.cancel()
        if self.__monitor_task is not None:
            self.__monitor_task.cancel()

    async def cog_check(self, ctx: PyLavContext):
        return bool(self.ready_event.is_set())

    @commands.group(name="pllocalset")
    async def command_pllocalset(self, ctx: PyLavContext):
        """Configure cog settings"""

    @command_pllocalset.command(name="version")
    async def command_pllocalset_version(self, context: PyLavContext) -> None:
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

    @command_pllocalset.command(name="update")
    @commands.is_owner()
    async def command_pllocalset_update(self, context: PyLavContext) -> None:
        """Update the track list for /local"""
        if isinstance(context, discord.Interaction):
            context = await self.cog.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self._update_cache()
        await context.send(
            embed=await self.pylav.construct_embed(
                description=shorten_string(
                    max_length=100,
                    string=_(
                        "I have updated my local track cache. There are now {number_variable_do_not_translate} tracks present."
                    ).format(number_variable_do_not_translate=len(self.cache)),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="local",
        description=shorten_string(max_length=100, string=_("Play a local file or folder, supports partial searching")),
    )
    @app_commands.describe(
        entry=shorten_string(max_length=100, string=_("The local file or folder to play")),
        recursive=shorten_string(
            max_length=100, string=_("If entry is a folder, play everything inside of it recursively")
        ),
    )
    @app_commands.guild_only()
    @app_commands.check(cache_filled)
    async def slash_local(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        entry: str,
        recursive: bool | None = False,
    ):  # sourcery no-metrics
        """Play a local file or folder, supports partial searching"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        send = partial(interaction.followup.send, wait=True)
        author = interaction.user
        if entry not in self.cache:
            await send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "{user_input_query_variable_do_not_translate} is not a valid local file or folder."
                    ).format(user_input_query_variable_do_not_translate=entry),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
            return
        entry = self.cache[entry]
        entry._recursive = recursive
        player = self.pylav.get_player(interaction.guild.id)
        if player is None:
            config = self.pylav.player_config_manager.get_config(interaction.guild.id)
            if (channel := interaction.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel, so I can connect to it."),
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
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=author)

        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            entry, requester=author, player=player, partial=True
        )
        if count:
            if count == 1:
                await player.add(requester=author.id, track=successful[0])
            else:
                await player.bulk_add(requester=author.id, tracks_and_queries=successful)
        single_track = successful[0] if successful else None
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=author)

        match count:
            case 0:
                description = _("No tracks were found for your query.")
            case 1:
                description = _("{track_name_variable_do_not_translate} enqueued.").format(
                    track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True)
                )
            case __:
                description = _("I have enqueued {track_count_variable_do_not_translate} tracks.").format(
                    track_count_variable_do_not_translate=count
                )
        await send(
            embed=await self.pylav.construct_embed(
                description=description,
                messageable=interaction,
            ),
            ephemeral=True,
        )

    @slash_local.autocomplete("entry")
    async def slash_local_autocomplete_entry(self, interaction: DISCORD_INTERACTION_TYPE, current: str):
        if not self.cache:
            return []

        if not current:
            extracted = list(islice(self.cache.items(), 25))
        else:
            current = re.sub(REGEX_FILE_NAME, r" ", current)

            def _filter_partial_ratio(x: tuple[str, Query]):
                # noinspection PyProtectedMember
                path = f"{x[1]._query}"
                # noinspection PyProtectedMember
                return (
                    fuzz.partial_ratio(re.sub(REGEX_FILE_NAME, r" ", path), current, score_cutoff=75),
                    10 if os.path.isdir(path) else 0,
                    [-ord(i) for i in path],
                )

            extracted = heapq.nlargest(25, self.cache.items(), key=_filter_partial_ratio)
        entries = []
        for md5, query in extracted:
            entries.append(
                Choice(
                    name=await query.query_to_string(
                        max_length=90, with_emoji=True, no_extension=True, add_ellipsis=True
                    ),
                    value=md5,
                )
            )
        return entries
