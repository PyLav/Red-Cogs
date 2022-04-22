import itertools
from abc import ABC
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Track
from pylav.converters import QueryPlaylistConverter
from pylav.utils import AsyncIter, PyLavContext

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import PaginatingMenu
from audio.cog.menus.sources import PlaylistListSource
from audio.cog.utils import rgetattr

LOGGER = getLogger("red.3pt.mp.commands.playlists")
_ = Translator("MediaPlayer", Path(__file__))


class PlaylistCommands(MPMixin, ABC):
    @commands.hybrid_group(name="playlist", fallback="pl")
    @commands.guild_only()
    @app_commands.guilds(MY_GUILD)
    async def command_playlist(self, context: PyLavContext):
        """
        Control custom playlist.
        """

    @command_playlist.command(name="create")
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
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("You must specify a name or a URL.")),
                ephemeral=True,
            )
            return

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

    @command_playlist.command(name="delete")
    async def command_playlist_delete(self, context: PyLavContext, playlist_id: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await context.lavalink.playlist_db_manager.delete_playlist(playlist_id)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Playlist has been deleted.")),
            ephemeral=True,
        )

    @command_playlist.command(name="play")
    async def command_playlist_play(self, context: PyLavContext, *, playlist_id_or_name: str):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

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

        playlists = await context.lavalink.playlist_db_manager.get_playlist_by_name_or_id(playlist_id_or_name)
        playlist = next(iter(playlists), None)
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
        ).start(context)
