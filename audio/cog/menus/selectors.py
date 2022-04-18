from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from red_commons.logging import getLogger

from pylav import Track

if TYPE_CHECKING:
    from audio.cog import MediaPlayer


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
        name = await track.get_track_display_name(max_length=90, author=False, unformatted=True)
        return cls(
            name=f"{index + 1}. {name}",
            description=track.author,
            value=track.unique_identifier,
        )


class QueueSelectTrack(discord.ui.Select):
    def __init__(
        self,
        options: list[QueueTrackOption],
        cog: MediaPlayer,
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
                embed=await self.cog.lavalink.construct_embed(title="Track not found."),
                ephemeral=True,
            )
            self.view.stop()
            await interaction.message.delete()
            return
        if self.interaction_type == "remove":
            self.cog.dispatch_msg(
                ctx=self.view.ctx,
                interaction=interaction,
                command=self.cog.command_remove,  # FIXME
                args=f" {track.uri}",
            )
        else:
            self.cog.dispatch_msg(
                ctx=self.view.ctx,
                interaction=interaction,
                command=self.cog.command_bumpplay,  # FIXME
                args=f" t {track.uri}",
            )
        self.view.stop()
        await interaction.message.delete()
