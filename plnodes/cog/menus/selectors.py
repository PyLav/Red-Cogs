from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_list

from pylav.constants import SUPPORTED_SOURCES
from pylav.sql.models import NodeModel

from plnodes.cog._types import CogT

if TYPE_CHECKING:
    from plnodes.cog.menus.menus import AddNodeFlow

LOGGER = getLogger("red.3pt.PyLavNodes.ui.selectors")
_ = Translator("PyLavNodes", Path(__file__))


class SourceOption(discord.SelectOption):
    def __init__(self, name: str, description: str | None, value: str):
        super().__init__(
            label=name,
            description=description,
            value=value,
        )


SOURCE_OPTIONS = []
for source in SUPPORTED_SOURCES:
    SOURCE_OPTIONS.append(SourceOption(name=source, description=None, value=source))


class SourceSelector(discord.ui.Select):
    view: AddNodeFlow

    def __init__(
        self,
        cog: CogT,
        row: int | None = None,
        placeholder: str = "",
    ):
        super().__init__(
            min_values=1,
            max_values=len(SUPPORTED_SOURCES),
            options=SOURCE_OPTIONS,
            placeholder=placeholder,
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
        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(
                messageable=interaction,
                description=_("Disabling the following sources: {sources}").format(sources=humanize_list(self.values)),
            ),
            ephemeral=True,
        )


class NodeOption(discord.SelectOption):
    @classmethod
    async def from_node(cls, node: NodeModel, index: int):
        return cls(
            label=f"{index + 1}. {node.name}",
            description=_("ID: {} || SSL: {} || Search-only: {}").format(node.id, node.ssl, node.search_only),
            value=f"{node.id}",
        )


class NodeSelectSelector(discord.ui.Select):
    def __init__(
        self,
        options: list[NodeOption],
        cog: CogT,
        placeholder: str,
        mapping: dict[str, NodeModel],
    ):
        super().__init__(min_values=1, max_values=1, options=options, placeholder=placeholder)
        self.cog = cog
        self.mapping = mapping
        self.node: NodeModel = None  # type:ignore
        self.responded = asyncio.Event()

    async def callback(self, interaction: discord.Interaction):
        playlist_id = self.values[0]
        self.node: NodeModel = self.mapping.get(playlist_id)
        if self.node is None:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(messageable=interaction, title=_("Node not found.")),
                ephemeral=True,
            )
            self.view.stop()
            await self.view.on_timeout()
            return
        self.responded.set()
        self.view.stop()
        await self.view.on_timeout()
