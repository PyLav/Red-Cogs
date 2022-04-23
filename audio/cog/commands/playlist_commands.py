import itertools
from abc import ABC
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.converters import PlaylistConverter, QueryPlaylistConverter
from pylav.sql.models import PlaylistModel
from pylav.tracks import decode_track
from pylav.utils import AsyncIter, PyLavContext

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import PaginatingMenu, PlaylistCreationFlow
from audio.cog.menus.sources import PlaylistListSource
from audio.cog.utils import rgetattr
from audio.cog.utils.playlists import maybe_prompt_for_playlist

LOGGER = getLogger("red.3pt.mp.commands.playlists")
_ = Translator("MediaPlayer", Path(__file__))


class PlaylistCommands(MPMixin, ABC):
    @commands.hybrid_group(name="playlist")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    async def command_playlist(self, context: PyLavContext):
        """
        Control custom playlist.
        """

    @command_playlist.command(name="create", aliases=["new"])
    async def command_playlist_create(
        self, context: PyLavContext, url: Optional[QueryPlaylistConverter], *, name: Optional[str]
    ):
        """
        Create a new playlist.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not (name or url):
            playlist_prompt = PlaylistCreationFlow(
                cog=self,
                original_author=context.author if not context.interaction else context.interaction.user,
                timeout=120,
            )
            title = _("Let's create a playlist!")
            description = _(
                "Select the name button to set the name for your playlist\n\n"
                "Select the url button to link this playlist to an existing playlist\n"
                "If you want the playlist name to be as the original "
                "playlist simply set the URL but no name.\n\n"
                "Select the cancel button to cancel the creation of the playlist.\n"
                "When you are happy with the name and URL click the done button to create the playlist."
            )

            await playlist_prompt.start(ctx=context, title=title, description=description)
            await playlist_prompt.wait()

            url = playlist_prompt.url
            name = playlist_prompt.name
            if not url and not name:
                return
            if url:
                url = await Query.from_string(url)
        if url:
            tracks_response = await context.lavalink.get_tracks(url)
            tracks = [track["track"] async for track in AsyncIter(tracks_response["tracks"])]
            url = url.query_identifier
            name = name or tracks_response.get("playlistInfo", {}).get("name", f"{context.message.id}")
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
            ),
            ephemeral=True,
        )

    @command_playlist.command(name="delete", aliases=["del", "rm"])
    async def command_playlist_delete(self, context: PyLavContext, *, playlist: PlaylistConverter):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        playlists = [p for p in playlist if await p.can_manage(bot=self.bot, requester=context.author, guild=context.guild)]  # type: ignore

        if not playlists:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("You don't have any playlist with that name or ID with you can manage.")
                ),
                ephemeral=True,
            )
            return
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        await playlist.delete()
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Playlist has been deleted.")),
            ephemeral=True,
        )

    @command_playlist.command(name="play", aliases=["start"])
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
                        description=_("You must be in a voice channel to allow me to connect.")
                    ),
                    ephemeral=True,
                )
                return
            player = await context.lavalink.connect_player(channel=channel, self_deaf=True, requester=context.author)
        track_count = len(playlist.tracks)
        await player.bulk_add(
            requester=context.author.id,
            tracks_and_queries=[
                Track(node=player.node, data=track, requester=context.author.id)
                async for i, track in AsyncIter(playlist.tracks).enumerate()
            ],
        )
        playlist_name = playlist.name
        if playlist.url:
            playlist_name = discord.utils.escape_markdown(playlist_name)
            playlist_name = f"[{playlist_name}]({playlist.url})"
        bundle_prefix = _("Playlist")
        playlist_name = f"\n\n**{bundle_prefix}:  {playlist_name}**"
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("{track_count} tracks enqueued.{playlist_name}").format(
                    track_count=track_count, playlist_name=playlist_name
                ),
            ),
            ephemeral=True,
        )

        if not player.is_playing:
            await player.play(requester=context.author)

    @command_playlist.command(name="list")
    async def command_playlist_list(self, context: PyLavContext):
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

        await PaginatingMenu(
            cog=self,  # type: ignore
            bot=self.bot,
            source=PlaylistListSource(cog=self, pages=playlists),  # type: ignore
            delete_after_timeout=True,
            timeout=120,
            original_author=context.author if not context.interaction else context.interaction.user,
        ).start(context)

    @command_playlist.command(name="remove")
    async def command_playlist_remove(
        self, context: PyLavContext, url: QueryPlaylistConverter, playlist: PlaylistConverter
    ):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        tracks = playlist.tracks
        new_tracks = []
        tracks_removed = []
        async for track in AsyncIter(tracks):
            track_obj, __ = decode_track(track)
            if track_obj["info"]["uri"] == url.query_identifier:
                tracks_removed.append(track_obj)
            else:
                new_tracks.append(track)
        if not tracks_removed:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("No tracks were removed from the playlist."),
                ),
                ephemeral=True,
            )
            return
        playlist.tracks = new_tracks
        await playlist.save()
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("{track_count} tracks removed from the playlist.").format(
                    track_count=len(tracks_removed)
                ),
            ),
            ephemeral=True,
        )
