from __future__ import annotations

from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav import Query

from audio.cog._types import CogT

LOGGER = getLogger("red.3pt.mp.ui.modals")

_ = Translator("MediaPlayer", Path(__file__))


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


class PlaylistSaveModal(discord.ui.Modal):
    def __init__(
        self,
        cog: CogT,
        button: discord.ui.Button,
        title: str,
        timeout: float | None = None,
    ):
        self.cog = cog
        self._button = button
        super().__init__(title=title, timeout=timeout)
        self.text = discord.ui.TextInput(
            style=discord.TextStyle.short,
            label=_("Enter the name for the new playlist"),
            placeholder=_("My awesome new playlist"),
            min_length=3,
            max_length=64,
        )
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction):
        if not getattr(interaction, "_cs_command", None):
            interaction._cs_command = self.cog.command_playlist_save
        await self.cog.command_playlist_save.callback(
            self.cog, await self.cog.bot.get_context(interaction), name=self.text.value.strip()
        )
        # FIXME: Implement playlist save command
