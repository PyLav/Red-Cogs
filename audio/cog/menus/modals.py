from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from red_commons.logging import getLogger
from redbot.core import commands

if TYPE_CHECKING:
    from redbot.core.bot import Red

    from audio.cog import MediaPlayer

    COG = MediaPlayer
    CLIENT = Red
else:
    from discord.ext.commands import Cog

    COG = Cog
    CLIENT = discord.Client

LOGGER = getLogger("red.3pt.mp.ui.modals")


class EnqueueModal(discord.ui.Modal):
    def __init__(
        self,
        cog: COG,
        ctx: commands.Context,
        button: discord.ui.Button,
        title: str,
        timeout: float | None = None,
    ):
        self.cog = cog
        self.ctx = ctx
        self._button = button
        super().__init__(title=title, timeout=timeout)
        self.text = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            label="Search for a song to add to the queue",
            placeholder="Hello by Adele, tts:Hello, https://open.spotify.com/playlist/37i9dQZF1DX6XceWZP1znY",
        )
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.slash_play.callback(
            self=self.cog,
            interaction=interaction,
            query=self.text.value,
        )
