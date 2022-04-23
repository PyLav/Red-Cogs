import asyncio
import itertools
from abc import ABC
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import EntryNotFoundError, Query, Track
from pylav.converters import QueryPlaylistConverter
from pylav.utils import AsyncIter, PyLavContext

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import PaginatingMenu, PlaylistCreationFlow, PlaylistPickerMenu
from audio.cog.menus.selectors import PlaylistSelectSelector
from audio.cog.menus.sources import PlaylistListSource, PlaylistPickerSource
from audio.cog.utils import rgetattr

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
            playlist_prompt = PlaylistCreationFlow(cog=self, timeout=120)
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

    @command_playlist.command(name="delete")
    async def command_playlist_delete(self, context: PyLavContext, *, playlist_id_or_name: str):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        playlists = await context.lavalink.playlist_db_manager.get_manageable_playlists(
            requester=context.author,
            bot=self.bot,
            name_or_id=playlist_id_or_name,
        )

        if not playlists:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("You don't have any playlist with that name or ID with you can manage.")
                ),
                ephemeral=True,
            )
            return

        if len(playlists) > 1:
            playlist_picker = PlaylistPickerMenu(
                cog=self,
                bot=self.bot,
                source=PlaylistPickerSource(
                    guild_id=context.guild.id,
                    cog=self,
                    pages=playlists,
                    message_str=_("Multiple playlist matched, pick the one which you meant."),
                ),
                selector_cls=PlaylistSelectSelector,
                delete_after_timeout=True,
                clear_buttons_after=True,
                starting_page=0,
                selector_text=_("Pick a playlist"),
            )

            await playlist_picker.start(context)
            await playlist_picker.wait_for_response()
            playlist = playlist_picker.result
            await playlist.delete()
        else:
            playlist = playlists[0]
            await playlist.delete()
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

        try:
            playlists = await context.lavalink.playlist_db_manager.get_playlist_by_name_or_id(playlist_id_or_name)
        except EntryNotFoundError:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Playlist with that name or ID not found.")),
                ephemeral=True,
            )
            return
        if len(playlists) > 1:
            playlist_picker = PlaylistPickerMenu(
                cog=self,
                bot=self.bot,
                source=PlaylistPickerSource(
                    guild_id=context.guild.id,
                    cog=self,
                    pages=playlists,
                    message_str=_("Multiple playlist matched, pick the one which you want."),
                ),
                selector_cls=PlaylistSelectSelector,
                delete_after_timeout=True,
                clear_buttons_after=True,
                starting_page=0,
                selector_text=_("Pick a playlist"),
            )

            await playlist_picker.start(context)
            try:
                await playlist_picker.wait_for_response()
            except asyncio.TimeoutError:
                playlist_picker.stop()
                await playlist_picker.on_timeout()
                return
            playlist = playlist_picker.result
        else:
            playlist = playlists[0]
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
