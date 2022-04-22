from __future__ import annotations

import discord
from red_commons.logging import getLogger

from pylav import Query

from audio.cog._types import CogT

LOGGER = getLogger("red.3pt.mp.ui.modals")


class EnqueueModal(discord.ui.Modal):
    def __init__(
        self,
        cog: CogT,
        title: str,
        timeout: float | None = None,
    ):
        super().__init__(title=title, timeout=timeout)
        self.cog = cog
        self.text = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            label="Search for a song to add to the queue",
            placeholder="Hello by Adele, tts:Hello, https://open.spotify.com/playlist/37i9dQZF1DX6XceWZP1znY",
        )
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        if not getattr(interaction, "_cs_command", None):
            interaction._cs_command = self.cog.command_play

        await self.cog.command_play.callback(
            self.cog,
            await self.cog.bot.get_context(interaction),
            query=await Query.from_string(self.text.value.strip()),
        )
