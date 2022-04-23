from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.sql.models import PlaylistModel
from pylav.types import BotT

from audio.cog._types import CogT

LOGGER = getLogger("red.3pt.mp.ui.selectors")
_ = Translator("MediaPlayer", Path(__file__))


class QueueTrackOption(discord.SelectOption):
    def __init__(self, name: str, description: str, value: str):
        super().__init__(
            label=name,
            description=description,
            value=value,
        )

    @classmethod
    async def from_track(cls, track: Track, index: int):
        name = await track.get_track_display_name(
            max_length=100 - (2 + len(str(index + 1))), author=False, unformatted=True
        )
        label = f"{index + 1}. {name}"
        return cls(
            name=label,
            description=track.author,
            value=track.id,
        )


class QueueSelectTrack(discord.ui.Select):
    def __init__(
        self,
        options: list[QueueTrackOption],
        cog: CogT,
        placeholder: str,
        interaction_type: Literal["remove", "play"],
        mapping: dict[str, Track],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.interaction_type = interaction_type
        self.mapping = mapping

    async def callback(self, interaction: discord.Interaction):
        track_id = self.values[0]
        track: Track = self.mapping.get(track_id)
        if track is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    description="Track not found.", messageable=interaction.channel  # type: ignore
                ),
                ephemeral=True,
            )
            self.view.stop()
            return
        player = self.cog.lavalink.get_player(interaction.guild)
        if not player:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    description="Player has been disconnected.", messageable=interaction.channel  # type: ignore
                ),
                ephemeral=True,
            )
            self.view.stop()
            return

        await interaction.response.defer(ephemeral=True)

        index = player.queue.index(track)
        index += 1
        if self.interaction_type == "remove":
            if not getattr(interaction, "_cs_command", None):
                interaction._cs_command = self.cog.command_remove
            context = await self.cog.bot.get_context(interaction)
            await self.cog.command_remove.callback(
                self.cog, context, track_url_or_index=f"{index}", remove_duplicates=True
            )
        else:
            if not getattr(interaction, "_cs_command", None):
                interaction._cs_command = self.cog.command_playnow
            context = await self.cog.bot.get_context(interaction)
            await self.cog.command_playnow.callback(self.cog, context, queue_number=index)
        self.view.stop()


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
            await interaction.message.delete()
            return

        if not getattr(interaction, "_cs_command", None):
            interaction._cs_command = self.cog.command_playlist_play
        await self.cog.command_playlist_play.callback(self.cog, interaction, playlist=[playlist])
        self.view.stop()
        await interaction.message.delete()


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
            await interaction.message.delete()
            return
        self.responded.set()
        await interaction.response.pong()
        self.view.stop()
        await interaction.message.delete()


class EffectsOption(discord.SelectOption):
    def __init__(self, label: str, description: str, value: str, index: int):
        super().__init__(
            label=f"{index + 1}. {label}",
            description=description,
            value=value,
        )


class EffectsSelector(discord.ui.Select):
    def __init__(
        self,
        options: list[EffectsOption],
        cog: CogT,
        placeholder: str,
        mapping: dict[str, str],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.mapping = mapping

    async def callback(self, interaction: discord.Interaction):
        effect_value = self.values[0]
        label: str = self.mapping.get(effect_value)
        if label is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(messageable=interaction, title=_("No Preset Selected.")),
                ephemeral=True,
            )
            self.view.stop()
            await interaction.message.delete()
            return
        self.cog.dispatch_msg(  # TODO Replace with preset command
            ctx=self.view.ctx,
            interaction=interaction,
            command=self.cog.command_effects,
            args=f" {label}",
        )
        self.view.stop()
        await interaction.message.delete()


class SearchTrackOption(discord.SelectOption):
    def __init__(self, name: str, description: str, value: str):
        super().__init__(
            label=name,
            description=description,
            value=value,
        )

    @classmethod
    async def from_track(cls, track: Track, index: int):
        name = await track.get_track_display_name(
            max_length=100 - (2 + len(str(index + 1))), author=False, unformatted=True
        )
        return cls(name=f"{index + 1}. {name}", description=track.author, value=track.id)


class SearchSelectTrack(discord.ui.Select):
    def __init__(
        self,
        options: list[SearchTrackOption],
        cog: CogT,
        placeholder: str,
        mapping: dict[str, Track],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.mapping = mapping

    async def callback(self, interaction: discord.Interaction):
        track_id = self.values[0]
        track: Track = self.mapping.get(track_id)

        if track is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(messageable=interaction, title=_("Track not found.")),
                ephemeral=True,
            )
            self.view.stop()
            await interaction.message.delete()
            return

        if not getattr(interaction, "_cs_command", None):
            interaction._cs_command = self.cog.command_play
        await self.cog.command_play.callback(
            self.cog,
            await self.cog.bot.get_context(interaction),
            query=await Query.from_string(track.uri),
        )
        self.view.stop()
        await interaction.message.delete()
