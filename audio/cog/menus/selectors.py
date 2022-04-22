from __future__ import annotations

from typing import Literal

import discord
from red_commons.logging import getLogger

from pylav import Track

from audio.cog._types import CogT

LOGGER = getLogger("red.3pt.mp.ui.selectors")


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
