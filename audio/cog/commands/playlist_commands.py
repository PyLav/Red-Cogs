from abc import ABC
from logging import getLogger
from pathlib import Path
from typing import Optional

import discord
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Track
from pylav.converters import QueryPlaylistConverter
from pylav.utils import AsyncIter

from audio.cog import MPMixin
from audio.cog.utils import rgetattr

LOGGER = getLogger("red.3pt.mp.commands.playlists")
_ = Translator("MediaPlayer", Path(__file__))


class PlaylistCommands(MPMixin, ABC):
    @commands.group(name="playlist")
    @commands.guild_only()
    async def command_playlist(self, context: commands.Context):
        """
        Control custom playlist.
        """

    @command_playlist.command(name="create")
    async def command_playlist_create(
        self, context: commands.Context, url: Optional[QueryPlaylistConverter], *, name: Optional[str]
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
                embed=await self.lavalink.construct_embed(
                    messageable=context, description=_("You must specify a name or a URL.")
                ),
                ephemeral=True,
            )
            return

        if url:
            tracks_response = await self.lavalink.get_tracks(url)
            tracks = [track["track"] async for track in AsyncIter(tracks_response["tracks"])]
            url = url.query_identifier
            name = name or tracks_response.get("playlistInfo", {}).get("name", f"{context.message.id}")
        else:
            tracks = []
            url = None
            if name is None:
                name = f"{context.message.id}"
        await self.lavalink.playlist_db_manager.create_or_update_playlist(
            id=context.message.id, scope=context.author.id, author=context.author.id, name=name, url=url, tracks=tracks
        )

        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("Playlist created"),
                description=_("Name: `{name}`\nID: `{id}`\nTracks: `{track_count}`").format(
                    name=name, id=context.message.id, track_count=len(tracks)
                ),
            ),
            ephemeral=True,
        )

    @command_playlist.command(name="delete")
    async def command_playlist_delete(self, context: commands.Context, playlist_id: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.lavalink.playlist_db_manager.delete_playlist(playlist_id)
        await context.send(
            embed=await self.lavalink.construct_embed(messageable=context, description=_("Playlist has been deleted.")),
            ephemeral=True,
        )

    @command_playlist.command(name="play")
    async def command_playlist_play(self, context: commands.Context, *, playlist_id_or_name: str):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if (player := self.lavalink.get_player(context.guild)) is None:
            channel = rgetattr(context, "author.voice.channel", None)
            if not channel:
                await context.send(
                    embed=await self.lavalink.construct_embed(
                        messageable=context, description=_("You must be in a voice channel to allow me to connect.")
                    ),
                    ephemeral=True,
                )
                return
            player = await self.lavalink.connect_player(channel=channel, self_deaf=True, requester=context.author)

        playlists = await self.lavalink.playlist_db_manager.get_playlist_by_name_or_id(playlist_id_or_name)
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
            playlist_name = f"**[{playlist_name}]({playlist.url})**"
        bundle_prefix = _("Playlist")
        playlist_name = f"\n\n**{bundle_prefix}:  {playlist_name}**"
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("{track_count} tracks enqueued.{playlist_name}").format(
                    track_count=track_count, playlist_name=playlist_name
                ),
            ),
            ephemeral=True,
        )

        if not player.is_playing:
            await player.play(requester=context.author)

    @command_playlist.command(name="list")
    async def command_list(self, context: commands.Context):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await context.send(
            embed=await self.lavalink.construct_embed(messageable=context, description=_("List of playlists:")),
            ephemeral=True,
        )
        async for i in self.lavalink.playlist_db_manager.get_all_playlists():
            i.tracks = len(i.tracks)
