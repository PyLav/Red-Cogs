from __future__ import annotations

import collections
import contextlib
import itertools
import typing
from abc import ABC
from pathlib import Path
from typing import Literal

import asyncstdlib
import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import Config
from redbot.core import commands
from redbot.core import commands as red_commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, box, humanize_list
from tabulate import tabulate

import pylavcogs_shared
from pylav.client import Client
from pylav.constants import BUNDLED_PLAYLIST_IDS
from pylav.converters.playlist import PlaylistConverter
from pylav.converters.query import QueryPlaylistConverter
from pylav.exceptions import InvalidPlaylist
from pylav.query import Query
from pylav.sql.models import PlaylistModel
from pylav.tracks import Track
from pylav.types import BotT, InteractionT
from pylav.utils import AsyncIter, PyLavContext
from pylav.utils.theme import EightBitANSI
from pylavcogs_shared.ui.menus.generic import PaginatingMenu
from pylavcogs_shared.ui.menus.playlist import PlaylistCreationFlow, PlaylistManageFlow
from pylavcogs_shared.ui.prompts.playlists import maybe_prompt_for_playlist
from pylavcogs_shared.ui.sources.playlist import Base64Source, PlaylistListSource
from pylavcogs_shared.utils import rgetattr
from pylavcogs_shared.utils.decorators import always_hidden, invoker_is_dj, requires_player


class CompositeMetaClass(type(red_commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """


_ = Translator("PyLavPlaylists", Path(__file__))

LOGGER_ERROR = getLogger("red.3pt.PyLavPlaylists.error_handler")


@cog_i18n(_)
class PyLavPlaylists(
    red_commands.Cog,
    metaclass=CompositeMetaClass,
):
    """PyLav playlist management commands"""

    lavalink: Client

    __version__ = "1.0.0.0rc1"

    slash_playlist = app_commands.Group(
        name="playlist",
        description=_("Control PyLav playlists"),
    )

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """
        Method for finding users data inside the cog and deleting it.
        """
        await self._config.user_from_id(user_id).clear()

    @slash_playlist.command(name="version")
    @app_commands.guild_only()
    async def slash_playlist_version(self, interaction: InteractionT) -> None:
        """Show the version of the Cog and it's PyLav dependencies"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        data = [
            (EightBitANSI.paint_white(self.__class__.__name__), EightBitANSI.paint_blue(self.__version__)),
            (EightBitANSI.paint_white("PyLavCogs-Shared"), EightBitANSI.paint_blue(pylavcogs_shared.__VERSION__)),
            (EightBitANSI.paint_white("PyLav"), EightBitANSI.paint_blue(context.lavalink.lib_version)),
        ]

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Library/Cog"), bold=True, underline=True),
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

    @slash_playlist.command(name="create", description=_("Create a playlist"))
    @app_commands.describe(
        url=_("The URL of the playlist to create. YouTube, Spotify, SoundCloud, Apple Music playlists or albums"),
        name=_("The name of the playlist"),
    )
    @app_commands.guild_only()
    async def slash_playlist_create(
        self, interaction: InteractionT, url: QueryPlaylistConverter = None, *, name: str = None
    ):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        add_queue = False
        timed_out = False
        if not (name or url):
            playlist_prompt = PlaylistCreationFlow(
                cog=self,
                original_author=context.interaction.user if context.interaction else context.author,
                timeout=120,
            )

            title = _("Let's create a playlist!")
            description = _(
                "(**1**) - Apply changes to playlist.\n"
                "(**2**) - Cancel any changes made.\n"
                "(**3**) - Add a name to the playlist.\n"
                "(**4**) - Link this playlist to an existing playlist/album.\n"
                "(**5**) - Add all tracks from the queue to the playlist.\n\n"
                "If you want the playlist name to be as the original playlist simply set the URL but no name.\n\n"
            )
            await playlist_prompt.start(ctx=context, title=title, description=description)
            timed_out = await playlist_prompt.wait()

            url = playlist_prompt.url
            name = playlist_prompt.name
            add_queue = playlist_prompt.queue
            if url:
                add_queue = False
                url = await Query.from_string(url)
        if url:
            tracks_response = await context.lavalink.get_tracks(url, player=context.player)
            tracks = [track["track"] async for track in AsyncIter(tracks_response["tracks"])]
            url = url.query_identifier
            name = name or tracks_response.get("playlistInfo", {}).get("name", f"{context.message.id}")
        else:
            if add_queue and context.player:
                tracks = context.player.queue.raw_queue
                tracks = [track.track for track in tracks if track.track] if tracks else []
            else:
                tracks = []
            url = None
        if not tracks and timed_out:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    title=_("Playlist not created"),
                    description=_("No tracks were provided in time."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if name is None:
            name = f"{context.message.id}"
        await context.lavalink.playlist_db_manager.create_or_update_user_playlist(
            id=context.message.id, author=context.author.id, name=name, url=url, tracks=tracks
        )
        await context.send(
            embed=await context.lavalink.construct_embed(
                title=_("Playlist created"),
                description=_("Name: `{name}`\nID: `{id}`\nTracks: `{track_count}`").format(
                    name=name, id=context.message.id, track_count=len(tracks)
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @slash_playlist.command(name="list", description=_("List all playlists you have access to on the invoked context"))
    @app_commands.guild_only()
    async def slash_playlist_list(self, interaction: InteractionT):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        playlists = await context.lavalink.playlist_db_manager.get_all_for_user(
            requester=context.author.id,
            vc=rgetattr(context.author, "voice.channel", None),
            guild=context.guild,
            channel=context.channel,
        )
        playlists = list(itertools.chain.from_iterable(playlists))
        if not playlists:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("You have no playlists"), messageable=context
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=PlaylistListSource(cog=self, pages=playlists),
            delete_after_timeout=True,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)

    @slash_playlist.command(
        name="manage",
        description=_("Manage a playlist"),
    )
    @app_commands.describe(
        operation=_("The operation to perform on the playlist, if not specified a menu will be shown for full control"),
        playlist=_("The playlist to perform the operation on"),
    )
    @app_commands.guild_only()
    async def slash_playlist_manage(
        self,
        interaction: InteractionT,
        playlist: PlaylistConverter,
        operation: Literal["Info", "Save", "Play", "Delete"] = None,
    ):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        # Could shortcut any other alias - but the issue comes with clarity and confirmation.
        invoked_with_start = operation == "Play"
        invoked_with_delete = operation == "Delete"
        invoked_with_queue = operation == "Save"
        invoked_with_info = operation == "Info"

        if invoked_with_queue and not context.player.queue.size():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Nothing to save"),
                    description=_("There is nothing in the queue to save"),
                ),
                ephemeral=True,
            )
            return

        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if invoked_with_start:
            await self.command_playlist_play.callback(self, context, playlist=[playlist])  # type: ignore
            return
        if invoked_with_info:
            await PaginatingMenu(
                bot=self.bot,
                cog=self,
                source=Base64Source(
                    guild_id=context.guild.id,
                    cog=self,
                    author=context.author,
                    entries=await playlist.fetch_tracks(),
                    playlist=playlist,
                ),
                delete_after_timeout=True,
                starting_page=0,
                original_author=context.author,
            ).start(context)
            return
        if playlist.id not in BUNDLED_PLAYLIST_IDS:
            manageable = await playlist.can_manage(bot=self.bot, requester=context.author, guild=context.guild)
        else:
            manageable = False
        if invoked_with_delete and not manageable:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("{user}, playlist {playlist_name} cannot be managed by yourself").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )
            return

        if manageable:
            info_description = _(
                "(**1**){space} - Apply changes to playlist.\n"
                "(**2**){space} - Cancel any changes made and close the menu.\n"
                "(**3**){space} - Delete this playlist.\n"
                "(**4**){space} - Remove all tracks from this playlist.\n"
                "(**5**){space} - Update the playlist with the latest tracks.\n"
                "Please note that this action will ignore any tracks added/removed via this menu.\n"
                "(**6**){space} - Change the name of the playlist.\n"
                "(**7**){space} - Link this playlist to an existing playlist/album.\n"
                "(**8**){space} - Add a query to this playlist.\n"
                "(**9**){space} - Remove a query from this playlist.\n"
                "(**10**) - Download the playlist file.\n"
                "(**11**) - Add current playlist to the queue.\n"
                "(**12**) - Show tracks in current playlist.\n"
                "(**13**) - Add tracks from queue to this playlist.\n"
                "(**14**) - Remove duplicate entries in the playlist.\n\n"
                "The add/remove track buttons can be used multiple times to "
                "add/remove multiple tracks and playlists at once.\n\n"
                "A query is anything playable by the play command - any query can be used by the add/remove buttons\n\n"
                "The clear button will always be run first before any other operations.\n"
                "The URL button will always run last - "
                "Linking a playlist via the URL will overwrite any tracks added or removed to this playlist.\n\n"
                "If you interact with a button multiple times other than the add/remove buttons "
                "only the last interaction will take effect.\n\n\n"
            )
        else:
            info_description = _(
                "(**1**) - Close the menu.\n"
                "(**2**) - Update the playlist with the latest tracks.\n"
                "(**3**) - Download the playlist file.\n"
                "(**4**) - Add current playlist to the queue.\n"
                "(**5**) - Show tracks in current playlist.\n\n\n"
            )

        playlist_info = _(
            "**__Currently managing__**:\n"
            "**Name**:{space}{space}{space}{playlist_name}\n"
            "**Scope**:{space}{space}{space}{scope}\n"
            "**Author**:{space}{space}{author}\n"
            "**Tracks**:{space}{space}{space}{tracks} tracks\n"
            "**URL**:{space}{space}{space}{space}{space}{url}\n"
        )
        playlist_prompt = PlaylistManageFlow(
            cog=self,
            original_author=context.author,
            timeout=600,
            playlist=playlist,
            manageable=manageable,
        )
        if not (invoked_with_delete or invoked_with_queue):
            name = await playlist.fetch_name()
            if manageable:
                title = _("Let's manage: {playlist_name}").format(playlist_name=name)
            else:
                title = _("Let's take a look at: {playlist_name}").format(playlist_name=name)
            description = info_description + playlist_info

            description = description.format(
                playlist_name=await playlist.get_name_formatted(with_url=True),
                scope=await playlist.get_scope_name(bot=self.bot, mention=True, guild=context.guild),
                author=await playlist.get_author_name(bot=self.bot, mention=True),
                url=await playlist.fetch_url() or _("N/A"),
                tracks=await playlist.size(),
                space="\N{EN SPACE}",
            )

            await playlist_prompt.start(ctx=context, title=title, description=description)
            await playlist_prompt.completed.wait()

        if manageable and invoked_with_delete:
            playlist_prompt.delete = True
            playlist_prompt.cancelled = False

        if (
            manageable
            and invoked_with_queue
            and not await asyncstdlib.all([playlist_prompt.update, playlist_prompt.url])
        ):
            playlist_prompt.queue = True
            playlist_prompt.cancelled = False

        if playlist_prompt.cancelled:
            return
        if (
            manageable
            and playlist_prompt.queue
            and await asyncstdlib.any([playlist_prompt.update, playlist_prompt.url])
        ):
            playlist_prompt.queue = False
        if manageable and playlist_prompt.delete:
            await playlist.delete()
            await context.send(
                embed=await context.lavalink.construct_embed(
                    title=_("Playlist deleted"),
                    messageable=context,
                    description=_("{user}, playlist {playlist_name} has been deleted").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )
            return
        tracks_added = 0
        tracks_removed = 0
        changed = False
        if manageable:
            if playlist_prompt.clear:
                changed = True
                await playlist.remove_all_tracks()
            if playlist_prompt.name and playlist_prompt.name != await playlist.fetch_name():
                changed = True
                await playlist.update_name(playlist_prompt.name)
            if playlist_prompt.url and playlist_prompt.url != await playlist.fetch_url():
                changed = True
                await playlist.update_url(playlist_prompt.url)
            if (playlist_prompt.add_tracks or playlist_prompt.remove_prompt) and not playlist_prompt.update:
                if playlist_prompt.remove_tracks:
                    response = await self.lavalink.get_tracks(
                        *[await Query.from_string(at) for at in playlist_prompt.remove_tracks], player=context.player
                    )
                    if not response.get("tracks"):
                        pass
                    tracks = response.get("tracks")  # type:ignore
                    for t in tracks:
                        b64 = t["track"]
                        await playlist.remove_track(b64)
                        changed = True
                        tracks_removed += 1
                if playlist_prompt.add_tracks:
                    response = await self.lavalink.get_tracks(
                        *[await Query.from_string(at) for at in playlist_prompt.add_tracks],
                        player=context.player,
                    )
                    if not response.get("tracks"):
                        pass
                    tracks = response.get("tracks")  # type:ignore
                    if tracks:
                        await playlist.add_track([t["track"] for t in tracks])
                        changed = True
                        tracks_added += sum(1 for __ in tracks)
        if playlist_prompt.update:
            if url := await playlist.fetch_url():
                with contextlib.suppress(Exception):
                    tracks: dict = await self.lavalink.get_tracks(
                        await Query.from_string(url), bypass_cache=True, player=context.player
                    )
                    if not tracks.get("tracks"):
                        await context.send(
                            embed=await context.lavalink.construct_embed(
                                messageable=context,
                                description=_(
                                    "Playlist **{playlist_name}** could not be updated with URL: <{url}>"
                                ).format(playlist_name=await playlist.get_name_formatted(with_url=True), url=url),
                            ),
                            ephemeral=True,
                        )
                        return
                    if tracks := typing.cast(list[str], [track["track"] for track in tracks["tracks"] if "track" in track]):  # type: ignore
                        changed = True
                        await playlist.update_tracks(tracks)
            elif playlist.id in BUNDLED_PLAYLIST_IDS:
                changed = True
                await self.lavalink.playlist_db_manager.update_bundled_playlists(playlist.id)
        if manageable:
            if playlist_prompt.dedupe:
                track = await playlist.fetch_tracks()
                new_tracks = list(dict.fromkeys(track))
                if diff := len(track) - len(new_tracks):
                    changed = True
                    await playlist.update_tracks(new_tracks)
                    tracks_removed += diff
            if playlist_prompt.queue:
                changed = True
                if context.player:
                    tracks: collections.deque[Track] = context.player.queue.raw_queue
                    if tracks:
                        queue_tracks = [track.encoded for track in tracks if track.encoded]
                        await playlist.add_track(queue_tracks)
                        tracks_added += len(queue_tracks)

        if changed:
            extras = ""
            if tracks_removed:
                extras += _("\n{track_count} {track_plural} removed from the playlist").format(
                    track_count=tracks_removed, track_plural=_("track") if tracks_removed == 1 else _("tracks")
                )
            if tracks_added:
                extras += _("\n{track_count} {track_plural} added to the playlist").format(
                    track_count=tracks_added, track_plural=_("track") if tracks_added == 1 else _("tracks")
                )
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Playlist updated"),
                    description=_("{user}, playlist {playlist_name} has been updated.{extras}").format(
                        user=context.author.mention,
                        playlist_name=await playlist.get_name_formatted(with_url=True),
                        extras=extras,
                    ),
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Playlist unchanged"),
                    description=_("{user}, playlist {playlist_name} has not been updated").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )

    @slash_playlist.command(
        name="play",
        description=_("Enqueue a playlist"),
    )
    @app_commands.describe(playlist=_("The playlist to enqueue"))
    @app_commands.guild_only()
    @invoker_is_dj(slash=True)
    async def slash_playlist_play(self, interaction: InteractionT, playlist: PlaylistConverter):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        await self.command_playlist_play.callback(self, context, playlist=[playlist])  # type: ignore

    @slash_playlist.command(
        name="delete",
        description=_("Delete a playlist"),
    )
    @app_commands.describe(playlist=_("The playlist to delete"))
    @app_commands.guild_only()
    async def slash_playlist_delete(self, interaction: InteractionT, playlist: PlaylistConverter):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if playlist.id not in BUNDLED_PLAYLIST_IDS:
            manageable = await playlist.can_manage(bot=self.bot, requester=context.author, guild=context.guild)
        else:
            manageable = False
        if not manageable:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("{user}, playlist {playlist_name} cannot be managed by yourself").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )
            return
        await playlist.delete()
        await context.send(
            embed=await context.lavalink.construct_embed(
                title=_("Playlist deleted"),
                messageable=context,
                description=_("{user}, playlist {playlist_name} has been deleted").format(
                    user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                ),
            ),
            ephemeral=True,
        )

    @slash_playlist.command(
        name="info",
        description=_("Display info about a playlist"),
    )
    @app_commands.describe(playlist=_("The playlist show info about"))
    @app_commands.guild_only()
    async def slash_playlist_info(self, interaction: InteractionT, playlist: PlaylistConverter):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return

        await PaginatingMenu(
            bot=self.bot,
            cog=self,
            source=Base64Source(
                guild_id=context.guild.id,
                cog=self,
                author=context.author,
                entries=await playlist.fetch_tracks(),
                playlist=playlist,
            ),
            delete_after_timeout=True,
            starting_page=0,
            original_author=context.author,
        ).start(context)

    @slash_playlist.command(name="save", description=_("Add the currently player queue to a playlist"))
    @app_commands.describe(playlist=_("The playlist to append the queue to"))
    @app_commands.guild_only()
    @requires_player(slash=True)
    async def slash_playlist_save(self, interaction: InteractionT, playlist: PlaylistConverter):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.queue.size():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Nothing to save"),
                    description=_("There is nothing in the queue to save"),
                ),
                ephemeral=True,
            )
            return
        playlists: list[PlaylistModel] = playlist
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if playlist.id not in BUNDLED_PLAYLIST_IDS:
            manageable = await playlist.can_manage(bot=self.bot, requester=context.author, guild=context.guild)
        else:
            manageable = False
        if not manageable:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("{user}, playlist {playlist_name} cannot be managed by yourself").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )
            return
        tracks_added = 0
        changed = False
        if context.player:
            if tracks := context.player.queue.raw_queue:
                queue_tracks = [track.track for track in tracks if track.track]
                await playlist.add_track(queue_tracks)
                tracks_added += len(queue_tracks)
                changed = True
        if changed:
            extras = ""
            if tracks_added:
                extras += _("\n{track_count} {track_plural} added to the playlist").format(
                    track_count=tracks_added, track_plural=_("track") if tracks_added == 1 else _("tracks")
                )

            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Playlist updated"),
                    description=_("{user}, playlist {playlist_name} has been updated.{extras}").format(
                        user=context.author.mention,
                        playlist_name=await playlist.get_name_formatted(with_url=True),
                        extras=extras,
                    ),
                ),
                ephemeral=True,
            )

        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    title=_("Playlist unchanged"),
                    description=_("{user}, playlist {playlist_name} has not been updated").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )

    @slash_playlist.command(name="upload", description=_("Upload a playlist to the bot"))
    @app_commands.describe(
        url=_("The URL of the playlist to upload"),
    )
    @app_commands.guild_only()
    @invoker_is_dj(slash=True)
    async def slash_playlist_upload(self, interaction: InteractionT, url: str = None):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        valid_playlist_urls = set()
        if url:
            if isinstance(url, str):
                url = url.strip("<>")
                valid_playlist_urls.add(url)
            else:
                valid_playlist_urls.update([r.strip("<>") for r in url])
        elif not context.message.attachments:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("You must either provide a URL or attach a playlist file to upload a playlist"),
                ),
                ephemeral=True,
            )
            return
        if context.message.attachments:
            for file in context.message.attachments:
                if file.filename.endswith(".pylav"):
                    valid_playlist_urls.add(file.url)
        if not valid_playlist_urls:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context, description=_("No valid playlist file provided")
                ),
                ephemeral=True,
            )
            return
        elif len(valid_playlist_urls) > 1:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("Multiple playlist files provided - Currently only 1 per message is allowed"),
                ),
                ephemeral=True,
            )
            return
        invalid_playlists_urls = set()
        saved_playlists = []
        for url in valid_playlist_urls:
            try:
                playlist = await PlaylistModel.from_yaml(context=context, url=url, scope=context.author.id)
                saved_playlists.append(f"{bold(await playlist.fetch_name())} ({playlist.id})")
            except InvalidPlaylist:
                invalid_playlists_urls.add(url)

        if not saved_playlists:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context, description=_("Failed to save any of the requested playlists")
                ),
                ephemeral=True,
            )
            return
        if invalid_playlists_urls:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    messageable=context,
                    description=_("Failed to save the following playlists:\n{invalid_playlists}").format(
                        invalid_playlists=humanize_list(list(invalid_playlists_urls))
                    ),
                ),
                ephemeral=True,
            )
        await context.send(
            embed=await context.lavalink.construct_embed(
                messageable=context,
                description=_("Successfully saved the following playlists:\n{saved_playlists}").format(
                    saved_playlists=humanize_list(saved_playlists)
                ),
            ),
            ephemeral=True,
        )

    @commands.command(name="__command_playlist_play", hidden=True)
    @always_hidden()
    async def command_playlist_play(self, context: PyLavContext, *, playlist: PlaylistConverter):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if (player := context.player) is None:
            config = self.lavalink.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(context, "author.voice.channel", None)
                if not channel:
                    await context.send(
                        embed=await context.lavalink.construct_embed(
                            messageable=context, description=_("You must be in a voice channel to allow me to connect")
                        ),
                        ephemeral=True,
                    )
                    return
            if not ((permission := channel.permissions_for(context.me)) and permission.connect and permission.speak):
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await context.connect_player(channel=channel, self_deaf=True)
        track_count = await playlist.size()
        await player.bulk_add(
            requester=context.author.id,
            tracks_and_queries=[
                Track(node=player.node, data=track, requester=context.author.id, query=await Query.from_base64(track))
                async for i, track in AsyncIter(await playlist.fetch_tracks()).enumerate()
            ],
        )
        bundle_prefix = _("Playlist")
        playlist_name = f"\n\n**{bundle_prefix}**:  {await playlist.get_name_formatted(with_url=True)}"
        await context.send(
            embed=await context.lavalink.construct_embed(
                messageable=context,
                description=_("{track_count} tracks enqueued.{playlist_name}").format(
                    track_count=track_count, playlist_name=playlist_name
                ),
            ),
            ephemeral=True,
        )

        if not player.is_playing:
            await player.next(requester=context.author)
