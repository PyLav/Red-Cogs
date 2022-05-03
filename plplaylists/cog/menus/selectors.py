from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav.sql.models import PlaylistModel
from pylav.types import BotT

from plplaylists.cog._types import CogT

LOGGER = getLogger("red.3pt.PyLavPlaylists.ui.selectors")
_ = Translator("PyLavPlaylists", Path(__file__))


class PlaylistOption(discord.SelectOption):
    @classmethod
    async def from_playlist(cls, playlist: PlaylistModel, bot: BotT, index: int):
        return cls(
            label=f"{index + 1}. {playlist.name}",
            description=_("Tracks: {} || {} || {}").format(
                len(playlist.tracks),
                await playlist.get_author_name(bot, mention=False),
                await playlist.get_scope_name(bot, mention=False),
            ),
            value=f"{playlist.id}",
        )


class PlaylistPlaySelector(discord.ui.Select):
    def __init__(
        self,
        options: list[PlaylistOption],
        cog: CogT,
        placeholder: str,
        mapping: dict[str, PlaylistModel],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.mapping = mapping

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
            return
        playlist_id = self.values[0]
        playlist: PlaylistModel = self.mapping.get(playlist_id)
        if playlist is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(messageable=interaction, title=_("Playlist not found.")),
                ephemeral=True,
            )
            self.view.stop()
            await self.view.on_timeout()
            return
        await self.cog.command_playlist_play.callback(self.cog, interaction, playlist=[playlist])  # type: ignore
        self.view.stop()
        await self.view.on_timeout()


class PlaylistSelectSelector(discord.ui.Select):
    def __init__(
        self,
        options: list[PlaylistOption],
        cog: CogT,
        placeholder: str,
        mapping: dict[str, PlaylistModel],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.mapping = mapping
        self.playlist: PlaylistModel = None  # type:ignore
        self.responded = asyncio.Event()

    async def callback(self, interaction: discord.Interaction):
        playlist_id = self.values[0]
        self.playlist: PlaylistModel = self.mapping.get(playlist_id)
        if self.playlist is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(messageable=interaction, title=_("Playlist not found.")),
                ephemeral=True,
            )
            self.view.stop()
            await self.view.on_timeout()
            return
        self.responded.set()
        self.view.stop()
        await self.view.on_timeout()
