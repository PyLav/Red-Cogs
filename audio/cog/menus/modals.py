from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

import discord
from red_commons.logging import getLogger

from pylav import Query

if TYPE_CHECKING:
    from redbot.core.bot import Red

    CLIENT = Red
    from audio.cog.abc import COG_TYPE

else:
    CLIENT = discord.Client
    from discord.ext.commands import Cog

    COG_TYPE = TypeVar("COG_TYPE", bound=Cog)


LOGGER = getLogger("red.3pt.mp.ui.modals")


class EnqueueModal(discord.ui.Modal):
    def __init__(
        self,
        cog: COG_TYPE,
        title: str,
        timeout: float | None = None,
    ):
        self.cog = cog
        super().__init__(title=title, timeout=timeout)
        self.text = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            label="Search for a song to add to the queue",
            placeholder="Hello by Adele, tts:Hello, https://open.spotify.com/playlist/37i9dQZF1DX6XceWZP1znY",
        )
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.command_slash.callback(
            self=self.cog,
            interaction=interaction,
            query=await Query.from_string(self.text.value),
        )
