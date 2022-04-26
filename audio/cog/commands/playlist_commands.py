import collections
import contextlib
import itertools
from abc import ABC
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import bold, humanize_list

from pylav import InvalidPlaylist, Query, Track
from pylav.converters import PlaylistConverter, QueryPlaylistConverter
from pylav.sql.models import PlaylistModel
from pylav.utils import AsyncIter, PyLavContext

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import PaginatingMenu, PlaylistCreationFlow, PlaylistManageFlow
from audio.cog.menus.sources import Base64Source, PlaylistListSource
from audio.cog.utils import decorators, rgetattr
from audio.cog.utils.playlists import maybe_prompt_for_playlist

LOGGER = getLogger("red.3pt.mp.commands.playlists")
_ = Translator("MediaPlayer", Path(__file__))


class PlaylistCommands(MPMixin, ABC):
    @commands.hybrid_group(name="playlist")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    async def command_playlist(self, context: PyLavContext):
        """Control custom playlist available in the bot."""

    @command_playlist.command(name="create", aliases=["new"])
    async def command_playlist_create(
        self, context: PyLavContext, url: Optional[QueryPlaylistConverter], *, name: Optional[str]
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
                "(**1 **) - Select the done button to apply the changes you've made to this playlist.\n"
                "(**2 **) - Select the cancel button to cancel this operation.\n"
                "(**3 **) - Select the name button to set the name for your playlist.\n"
                "(**4 **) - Select the url button to link this playlist to an existing playlist/album.\n"
                "(**5 **) - Select the queue button to add all track from the queue to the playlist.\n\n"
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
        invoked_with_info = context.invoked_with in ("info")

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

        if not await playlist.can_manage(bot=self.bot, requester=context.author, guild=context.guild):
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("You do not have permission to manage this playlist."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        playlist_prompt = PlaylistManageFlow(
            cog=self,
            original_author=context.author,
            timeout=600,
            playlist=playlist,
        )
        if not (invoked_with_delete or invoked_with_queue):
            title = _("Let's manage: {playlist_name}").format(playlist_name=playlist.name)

            description = _(
                "(**1 **) - Select the done button to apply the changes you've made to this playlist.\n"
                "(**2 **) - Select the cancel button to cancel this operation.\n"
                "(**3 **) - Select the delete button to delete this playlist.\n"
                "(**4 **) - Select the clear button to clear all tracks from this playlist.\n"
                "(**5 **) - Select the update button to update this playlist to whatever URL "
                "has been set on it bringing it up to date.\n"
                "Please note that this action will ignore any tracks added/removed via this menu.\n"
                "(**6 **) - Select the name button to change the name for your playlist.\n"
                "(**7 **) - Select the url button to link this playlist to an existing playlist.\n"
                "(**8 **) - Select the add button to add tracks from this playlist.\n"
                "(**9 **) - Select the remove button to remove tracks from this playlist.\n"
                "(**10**) - Select the download button to download this playlist so that it can be "
                "shared with others.\n"
                "(**11**) - Select the play button to enqueue the currently selected playlist.\n"
                "(**12**) - Select the info button to display all tracks in the playlist.\n"
                "(**13**) - Select the queue button to add all track from the queue to the playlist.\n"
                "(**14**) - Select the dedupe button to remove all duplicate entries from the queue.\n\n"
                "The add/remove track buttons can be used multiple times to "
                "add/remove multiple tracks and playlists at once.\n\n"
                "A Query is anything playable by the play command - any query can be used by the add/remove buttons\n\n"
                "The clear button will always be run first before any other operations.\n"
                "The URL button will always run last - "
                "Linking a playlist via the URL will overwrite any tracks added or removed to this playlist.\n\n"
                "If you interact with a button multiple times other than the add/remove buttons "
                "only the last interaction will take effect.\n\n\n"
                "**Currently managing**:\n"
                "Name:     {playlist_name}\n"
                "Scope:    {scope}\n"
                "Author:   {author}\n"
                "Tracks:   {tracks} tracks\n"
                "URL:      {url}\n"
            ).format(
                playlist_name=await playlist.get_name_formatted(with_url=True),
                scope=await playlist.get_scope_name(bot=self.bot, mention=True, guild=context.guild),
                author=await playlist.get_author_name(bot=self.bot, mention=True),
                url=playlist.url or "",
                tracks=len(playlist.tracks),
            )

            await playlist_prompt.start(ctx=context, title=title, description=description)
            await playlist_prompt.completed.wait()

        if invoked_with_delete:
            playlist_prompt.delete = True
            playlist_prompt.cancelled = False

        if invoked_with_queue and not all([playlist_prompt.update, playlist_prompt.url]):
            playlist_prompt.queue = True
            playlist_prompt.cancelled = False

        if playlist_prompt.cancelled:
            return
        if playlist_prompt.queue and any([playlist_prompt.update, playlist_prompt.url]):
            playlist_prompt.queue = False
        if playlist_prompt.delete:
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
                    successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
                        *[await Query.from_string(rt) for rt in playlist_prompt.remove_tracks],
                        requester=context.author,
                        player=None,
                    )
                    for t in successful:
                        b64 = t.track
                        while b64 in playlist.tracks:
                            changed = True
                            playlist.tracks.remove(b64)
                            tracks_removed += 1
                if playlist_prompt.add_tracks:
                    successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
                        *[await Query.from_string(at) for at in playlist_prompt.add_tracks],
                        requester=context.author,
                        player=None,
                        enqueue=False,
                    )
                    for t in successful:
                        b64 = t.track
                        changed = True
                        playlist.tracks.append(b64)
                        tracks_added += 1
            if playlist_prompt.update and playlist.url:
                with contextlib.suppress(Exception):
                    tracks: dict = await self.lavalink.get_tracks(
                        query=await Query.from_string(playlist.url), bypass_cache=True
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

    @command_playlist.command(name="__command_playlist_play", hidden=True)
    @decorators.always_hidden()
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
            channel = rgetattr(context, "author.voice.channel", None)
            if not channel:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        messageable=context, description=_("You must be in a voice channel to allow me to connect.")
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
