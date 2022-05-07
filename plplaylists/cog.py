from __future__ import annotations

import collections
import contextlib
import itertools
from abc import ABC
from pathlib import Path
from typing import Literal

import discord
from red_commons.logging import getLogger
from redbot.core import Config
from redbot.core import commands
from redbot.core import commands as red_commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, humanize_list

from pylav import Client, InvalidPlaylist, Query, Track, exceptions
from pylav.constants import BUNDLED_PLAYLIST_IDS
from pylav.converters import PlaylistConverter, QueryPlaylistConverter
from pylav.sql.models import PlaylistModel
from pylav.types import BotT
from pylav.utils import AsyncIter, CogMixin, PyLavContext
from pylavcogs_shared.errors import MediaPlayerNotFoundError, UnauthorizedChannelError
from pylavcogs_shared.ui.menus.generic import PaginatingMenu
from pylavcogs_shared.ui.menus.playlist import PlaylistCreationFlow, PlaylistManageFlow
from pylavcogs_shared.ui.prompts.playlists import maybe_prompt_for_playlist
from pylavcogs_shared.ui.sources.playlist import Base64Source
from pylavcogs_shared.utils import rgetattr
from pylavcogs_shared.utils.decorators import always_hidden


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
    CogMixin,
    metaclass=CompositeMetaClass,
):
    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.lavalink = Client(bot=self.bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        self.config = Config.get_conf(self, identifier=208903205982044161)
        self._init_task = None

    async def initialize(self) -> None:
        await self.lavalink.register(self)
        await self.lavalink.initialize()

    async def cog_unload(self) -> None:
        if self._init_task is not None:
            self._init_task.cancel()
        await self.bot.lavalink.unregister(cog=self)

    async def cog_check(self, ctx: PyLavContext) -> bool:
        if not ctx.guild:
            return True
        if ctx.player:
            config = ctx.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(ctx.guild.id)
        if config.text_channel_id and config.text_channel_id != ctx.channel.id:
            raise UnauthorizedChannelError(channel=config.text_channel_id)
        return True

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """
        Method for finding users data inside the cog and deleting it.
        """
        await self.config.user_from_id(user_id).clear()

    async def cog_command_error(self, context: PyLavContext, error: Exception) -> None:
        error = getattr(error, "original", error)
        unhandled = True
        if isinstance(error, MediaPlayerNotFoundError):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context, description=_("This command requires an existing player to be run.")
                ),
                ephemeral=True,
            )
        elif isinstance(error, exceptions.NoNodeAvailable):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_(
                        "MediaPlayer cog is currently temporarily unavailable due to an outage with "
                        "the backend services, please try again later."
                    ),
                    footer=_("No Lavalink node currently available.")
                    if await self.bot.is_owner(context.author)
                    else None,
                ),
                ephemeral=True,
            )
        elif isinstance(error, exceptions.NoNodeWithRequestFunctionalityAvailable):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("MediaPlayer is currently unable to process tracks belonging to {feature}.").format(
                        feature=error.feature
                    ),
                    footer=_("No Lavalink node currently available with feature {feature}.").format(
                        feature=error.feature
                    )
                    if await self.bot.is_owner(context.author)
                    else None,
                ),
                ephemeral=True,
            )
        elif isinstance(error, UnauthorizedChannelError):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := context.guild.get_channel_or_thread(error.channel))
                        else None
                    ),
                ),
                ephemeral=True,
                delete_after=10,
            )
        if unhandled:
            await self.bot.on_command_error(context, error, unhandled_by_cog=True)  # type: ignore

    @commands.hybrid_group(name="playlist")
    @commands.guild_only()
    async def command_playlist(self, context: PyLavContext):
        """Control custom playlist available in the bot."""

    @command_playlist.command(name="create", aliases=["new"])
    async def command_playlist_create(
        self, context: PyLavContext, url: QueryPlaylistConverter | None, *, name: str | None
    ):
        """Create a new playlist.

        If you don't specify an URL and name, you will be shows a creation menu, which also allows you to save the current player queue as a playlist.

        If you don't specify a name, the playlist will be named the URL playlist if available otherwise the name will be the same as the ID.
        If you specify an URL, the playlist will be created from the URL.
        """

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        add_queue = False
        if not (name or url):
            playlist_prompt = PlaylistCreationFlow(
                cog=self,
                original_author=context.author if not context.interaction else context.interaction.user,
                timeout=120,
            )
            title = _("Let's create a playlist!")
            description = _(
                "(**1**) - Apply changes to playlist.\n"
                "(**2**) - Cancel any changes made.\n"
                "(**3**) - Add a name to the playlist.\n"
                "(**4**) - Link this playlist to an existing playlist/album.\n"
                "(**5**) - Add all track from the queue to the playlist.\n\n"
                "If you want the playlist name to be as the original playlist simply set the URL but no name.\n\n"
            )
            await playlist_prompt.start(ctx=context, title=title, description=description)
            await playlist_prompt.wait()

            url = playlist_prompt.url
            name = playlist_prompt.name
            add_queue = playlist_prompt.queue
            if url:
                add_queue = False
                url = await Query.from_string(url)
        async with context.typing():
            if url:
                tracks_response = await context.lavalink.get_tracks(url)
                tracks = [track["track"] async for track in AsyncIter(tracks_response["tracks"])]
                url = url.query_identifier
                name = name or tracks_response.get("playlistInfo", {}).get("name", f"{context.message.id}")
            else:
                if add_queue and context.player:
                    tracks = context.player.queue.raw_queue
                    if tracks:
                        tracks = [track.track for track in tracks if track.track]
                    else:
                        tracks = []
                else:
                    tracks = []
                url = None
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

    @command_playlist.command(name="list")
    async def command_playlist_list(self, context: PyLavContext):
        """
        List all playlists you have access to on the invoked context.

        This takes into consideration your current VC, Text channel and Server.
        """

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

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
                    description=_("You have no playlists."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,  # type: ignore
            bot=self.bot,
            source=PlaylistListSource(cog=self, pages=playlists),  # type: ignore
            delete_after_timeout=True,
            timeout=120,
            original_author=context.author if not context.interaction else context.interaction.user,
        ).start(context)

    @command_playlist.command(
        name="manage",
        aliases=["delete", "remove", "rm", "del", "clear", "add", "play", "start", "enqueue", "info", "save", "queue"],
    )
    async def command_playlist_manage(self, context: PyLavContext, *, playlist: PlaylistConverter):
        """
        Manage a playlist.

        This command can be used to delete, clear all tracks, add or remove tracks or play a playlist.

        If you use the `start` (`play` or `enqueue`) alias the playlist will be played instead of you being shown the control menu.
        If you use the `delete` (`del`) alias the playlist will be deleted instead of you being shown the control menu.
        If you use the `save` (`queue`) alias the current queue will be added to the specified playlist.
        if you use the `info` alias the playlist tracks will be displayed in a menu.
        """

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        # Could shortcut any other alias - but the issue comes with clarity and confirmation.
        invoked_with_start = context.invoked_with in ("start", "play", "enqueue")
        invoked_with_delete = context.invoked_with in ("delete", "del")
        invoked_with_queue = context.invoked_with in ("queue", "save")
        invoked_with_info = context.invoked_with in ("info",)

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
                    entries=playlist.tracks,
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
                    description=_("{user}, playlist {playlist_name} cannot be managed by yourself.").format(
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
            if manageable:
                title = _("Let's manage: {playlist_name}").format(playlist_name=playlist.name)
            else:
                title = _("Let's take a look at: {playlist_name}").format(playlist_name=playlist.name)
            description = info_description + playlist_info

            description = description.format(
                playlist_name=await playlist.get_name_formatted(with_url=True),
                scope=await playlist.get_scope_name(bot=self.bot, mention=True, guild=context.guild),
                author=await playlist.get_author_name(bot=self.bot, mention=True),
                url=playlist.url or _("N/A"),
                tracks=len(playlist.tracks),
                space="\N{EN SPACE}",
            )

            await playlist_prompt.start(ctx=context, title=title, description=description)
            await playlist_prompt.completed.wait()

        if manageable and invoked_with_delete:
            playlist_prompt.delete = True
            playlist_prompt.cancelled = False

        if manageable and invoked_with_queue and not all([playlist_prompt.update, playlist_prompt.url]):
            playlist_prompt.queue = True
            playlist_prompt.cancelled = False

        if playlist_prompt.cancelled:
            return
        if manageable and playlist_prompt.queue and any([playlist_prompt.update, playlist_prompt.url]):
            playlist_prompt.queue = False
        if manageable and playlist_prompt.delete:
            await playlist.delete()
            await context.send(
                embed=await context.lavalink.construct_embed(
                    title=_("Playlist deleted."),
                    messageable=context,
                    description=_("{user}, playlist {playlist_name} has been deleted.").format(
                        user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                    ),
                ),
                ephemeral=True,
            )
            return
        tracks_added = 0
        tracks_removed = 0
        async with context.typing():
            changed = False
            if manageable:
                if playlist_prompt.clear:
                    changed = True
                    playlist.tracks = []
                if playlist_prompt.name and playlist_prompt.name != playlist.name:
                    changed = True
                    playlist.name = playlist_prompt.name
                if playlist_prompt.url and playlist_prompt.url != playlist.url:
                    changed = True
                    playlist.url = playlist_prompt.url
                if (playlist_prompt.add_tracks or playlist_prompt.remove_prompt) and not playlist_prompt.update:
                    if playlist_prompt.remove_tracks:
                        response = await self.lavalink.get_tracks(
                            *[await Query.from_string(at) for at in playlist_prompt.remove_tracks],
                        )
                        if not response.get("tracks"):
                            pass
                        tracks = response.get("tracks")  # type:ignore
                        for t in tracks:
                            b64 = t["track"]
                            while b64 in playlist.tracks:
                                changed = True
                                playlist.tracks.remove(b64)
                                tracks_removed += 1
                    if playlist_prompt.add_tracks:
                        response = await self.lavalink.get_tracks(
                            *[await Query.from_string(at) for at in playlist_prompt.add_tracks],
                        )
                        if not response.get("tracks"):
                            pass
                        tracks = response.get("tracks")  # type:ignore
                        for t in tracks:
                            b64 = t["track"]
                            changed = True
                            playlist.tracks.append(b64)
                            tracks_added += 1
            if playlist_prompt.update:
                if playlist.url:
                    with contextlib.suppress(Exception):
                        tracks: dict = await self.lavalink.get_tracks(
                            await Query.from_string(playlist.url), bypass_cache=True
                        )
                        if not tracks.get("tracks"):
                            await context.send(
                                embed=await context.lavalink.construct_embed(
                                    messageable=context,
                                    description=_(
                                        "Playlist **{playlist_name}** could not be updated with URL: <{url}>."
                                    ).format(
                                        playlist_name=await playlist.get_name_formatted(with_url=True), url=playlist.url
                                    ),
                                ),
                                ephemeral=True,
                            )
                            return
                        tracks = [track["track"] for track in tracks["tracks"] if "track" in track]  # type: ignore
                        if tracks:
                            changed = True
                            playlist.tracks = tracks
                elif playlist.id in BUNDLED_PLAYLIST_IDS:
                    changed = True
                    await self.lavalink.playlist_db_manager.update_bundled_playlists(playlist.id)
            if manageable:
                if playlist_prompt.dedupe:
                    new_tracks = list(dict.fromkeys(playlist.tracks))
                    diff = len(playlist.tracks) - len(new_tracks)
                    if diff:
                        changed = True
                        playlist.tracks = new_tracks
                        tracks_removed += diff
                if playlist_prompt.queue:
                    changed = True
                    if context.player:
                        tracks: collections.deque[Track] = context.player.queue.raw_queue
                        if tracks:
                            queue_tracks = [track.track for track in tracks if track.track]
                            playlist.tracks.extend(queue_tracks)
                            tracks_added += len(queue_tracks)

            if changed:
                extras = ""
                if tracks_removed:
                    extras += _("\n{track_count} {track_plural} removed from the playlist.").format(
                        track_count=tracks_removed, track_plural=_("track") if tracks_removed == 1 else _("tracks")
                    )
                if tracks_added:
                    extras += _("\n{track_count} {track_plural} added to the playlist.").format(
                        track_count=tracks_added, track_plural=_("track") if tracks_added == 1 else _("tracks")
                    )
                await playlist.save()
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        messageable=context,
                        title=_("Playlist updated."),
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
                        title=_("Playlist unchanged."),
                        description=_("{user}, playlist {playlist_name} has not been updated.").format(
                            user=context.author.mention, playlist_name=await playlist.get_name_formatted(with_url=True)
                        ),
                    ),
                    ephemeral=True,
                )

    @command_playlist.command(name="upload")
    @commands.guild_only()
    async def command_playlist_upload(self, context: commands.Context, url: str = None):
        """
        Upload a playlist to the bot.

        This command will upload a playlist to the bot.
        The playlist can be uploaded by either the URL of the playlist file or by attaching the playlist file to the message.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        valid_playlist_urls = set()
        async with context.typing():
            if not url:
                if not context.message.attachments:
                    await context.send(
                        embed=await context.lavalink.construct_embed(
                            messageable=context,
                            description=_(
                                "You must either provide a URL or attach a playlist file to upload a playlist."
                            ),
                        ),
                        ephemeral=True,
                    )
                    return
            else:
                if isinstance(url, str):
                    url = url.strip("<>")
                    valid_playlist_urls.add(url)
                else:
                    valid_playlist_urls.update([r.strip("<>") for r in url])
            if context.message.attachments:
                for file in context.message.attachments:
                    if file.filename.endswith(".yaml"):
                        valid_playlist_urls.add(file.url)
            if not valid_playlist_urls:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        messageable=context, description=_("No valid playlist file provided.")
                    ),
                    ephemeral=True,
                )
                return
            elif len(valid_playlist_urls) > 1:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        messageable=context,
                        description=_("Multiple playlist files provided - Currently only 1 per message is allowed."),
                    ),
                    ephemeral=True,
                )
                return
            invalid_playlists_urls = set()
            saved_playlists = []
            for url in valid_playlist_urls:
                try:
                    playlist = await PlaylistModel.from_yaml(context=context, url=url, scope=context.author.id)
                    await playlist.save()
                    saved_playlists.append(f"{bold(playlist.name)} ({playlist.id})")
                except InvalidPlaylist:
                    invalid_playlists_urls.add(url)

            if not saved_playlists:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        messageable=context, description=_("Failed to save any of the requested playlists.")
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
            if saved_playlists:
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
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(config.forced_channel_id)) is None:
                channel = rgetattr(context, "author.voice.channel", None)
                if not channel:
                    await context.send(
                        embed=await context.lavalink.construct_embed(
                            messageable=context, description=_("You must be in a voice channel to allow me to connect.")
                        ),
                        ephemeral=True,
                    )
                    return
            if not ((permission := channel.permissions_for(context.me)) and permission.connect and permission.speak):
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}.").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await context.connect_player(channel=channel, self_deaf=True)
        track_count = len(playlist.tracks)
        await player.bulk_add(
            requester=context.author.id,
            tracks_and_queries=[
                Track(node=player.node, data=track, requester=context.author.id, query=await Query.from_base64(track))
                async for i, track in AsyncIter(playlist.tracks).enumerate()
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
