from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import discord
from discord import Emoji, PartialEmoji
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav import emojis

from plnodes.cog._types import CogT

if TYPE_CHECKING:
    from plnodes.cog.menus.menus import AddNodeFlow

LOGGER = getLogger("red.3pt.PyLavNodes.ui.buttons")

_ = Translator("PyLavNodes", Path(__file__))


class NavigateButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | discord.PartialEmoji,
        direction: int | Callable[[], int],
        row: int = None,
        label: str = None,
    ):

        super().__init__(style=style, emoji=emoji, row=row, label=label)
        self.cog = cog
        self._direction = direction

    @property
    def direction(self) -> int:
        return self._direction if isinstance(self._direction, int) else self._direction()

    async def callback(self, interaction: discord.Interaction):
        max_pages = self.view.source.get_max_pages()
        if self.direction == 0:
            self.view.current_page = 0
        elif self.direction == max_pages:
            self.view.current_page = max_pages - 1
        else:
            self.view.current_page += self.direction

        if self.view.current_page >= max_pages:
            self.view.current_page = 0
        elif self.view.current_page < 0:
            self.view.current_page = max_pages - 1

        kwargs = await self.view.get_page(self.view.current_page)
        await self.view.prepare()
        await interaction.response.edit_message(view=self.view, **kwargs)


class RefreshButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class CloseButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.MINIMIZE,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = True
        self.view.stop()
        await self.view.on_timeout()


class DoneButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.CHECK,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.done = True
        self.view.cancelled = False
        self.view.stop()
        await self.view.on_timeout()


class SSLNodeToggleButton(discord.ui.Button):
    view: AddNodeFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.ssl = not self.view.ssl
        if self.view.ssl:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Connecting to the node with SSL enabled...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Connecting to the node with SSL disabled...")
                ),
                ephemeral=True,
            )


class SearchOnlyNodeToggleButton(discord.ui.Button):
    view: AddNodeFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.search_only = not self.view.search_only
        if self.view.search_only:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("This node will only be used for searches...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("This node will be used for search and playback...")
                ),
                ephemeral=True,
            )


class AddNodeDoneButton(discord.ui.Button):
    view: AddNodeFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.CHECK,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )

        if not all([self.view.name, self.view.host, self.view.port, self.view.password]):
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Please fill out all the fields before continuing.")
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        self.view.last_interaction = interaction
        self.view.done = True
        self.view.disabled_sources = self.view.disabled_sources_selector.values
        self.view.cancelled = False
        self.view.stop()
        await self.view.on_timeout()


class NodeButton(discord.ui.Button):
    view: AddNodeFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        op: Literal["name", "host", "port", "password", "timeout"],
        label: str = None,
        emoji: str | Emoji | PartialEmoji = None,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            label=label,
            row=row,
        )
        self.cog = cog
        self.op = op

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        if self.op == "name":
            await self.view.prompt_name(interaction)
        elif self.op == "host":
            await self.view.prompt_host(interaction)
        elif self.op == "port":
            await self.view.prompt_port(interaction)
        elif self.op == "password":
            await self.view.prompt_password(interaction)
        elif self.op == "timeout":
            await self.view.prompt_resume_timeout(interaction)
