from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import discord
import humanize
from red_commons.logging import getLogger
from redbot.core import i18n
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_number
from redbot.vendored.discord.ext import menus
from tabulate import tabulate

from pylav.node import Node
from pylav.sql.models import NodeModel

from plnodes.cog._types import CogT
from plnodes.cog.menus.selectors import NodeOption

LOGGER = getLogger("red.3pt.PyLavNodes.ui.sources")

if TYPE_CHECKING:
    from plnodes.cog.menus.menus import BaseMenu, NodeManagerMenu


INF = float("inf")
ASCII_ORDER_SORT = "~" * 100
_ = Translator("PyLavNodes", Path(__file__))


class NodePickerSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: CogT, pages: list[NodeModel], message_str: str):
        super().__init__(entries=pages, per_page=5)
        self.message_str = message_str
        self.per_page = 5
        self.guild_id = guild_id
        self.select_options: list[NodeOption] = []
        self.cog = cog
        self.select_mapping: dict[str, NodeModel] = {}

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, nodes: list[NodeModel]) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        page = await self.cog.lavalink.construct_embed(messageable=menu.ctx, title=self.message_str)
        page.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} nodes.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                num=len(self.entries),
            )
        )
        return page

    async def get_page(self, page_number):
        if page_number > self.get_max_pages():
            page_number = 0
        base = page_number * self.per_page
        self.select_options.clear()
        self.select_mapping.clear()
        for i, node in enumerate(self.entries[base : base + self.per_page], start=base):  # noqa: E203
            self.select_options.append(await NodeOption.from_node(node=node, index=i))
            self.select_mapping[f"{node.id}"] = node
        return self.entries[base : base + self.per_page]  # noqa: E203

    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages or 1


class NodeListSource(menus.ListPageSource):
    def __init__(self, cog: CogT, pages: list[Node]):
        super().__init__(entries=pages, per_page=1)
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: NodeManagerMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: NodeManagerMenu, node: Node) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        region = node.region
        host = node.host
        port = node.port
        password = node.password
        secure = _("Yes") if node.ssl else _("No")
        connected = _("Yes") if node.available else _("No")
        search_only = _("Yes") if node.search_only else _("No")
        locale = f"{i18n.get_babel_locale()}"
        with contextlib.suppress(Exception):
            humanize.i18n.activate(locale)

        server_connected_players = node.server_connected_players
        server_active_players = node.server_playing_players
        pylav_connected_players = len(node.connected_players)
        pylav_active_players = len(node.playing_players)
        if node.stats:
            frames_sent = node.stats.frames_sent
            frames_nulled = node.stats.frames_nulled
            frames_deficit = node.stats.frames_deficit

            uptime = humanize.naturaldelta(node.stats.uptime)
            system_load = humanize_number(round(node.stats.system_load, 2))
            lavalink_load = humanize_number(round(node.stats.lavalink_load, 2))

            free = humanize.naturalsize(node.stats.memory_free, binary=True)
            used = humanize.naturalsize(node.stats.memory_used, binary=True)
            allocated = humanize.naturalsize(node.stats.memory_allocated, binary=True)
            reservable = humanize.naturalsize(node.stats.memory_reservable, binary=True)
            penalty = humanize_number(round(node.stats.penalty.total - 1, 2))
        else:
            frames_sent = 0
            frames_nulled = 0
            frames_deficit = 0
            uptime = "?"
            system_load = "?"
            lavalink_load = "?"
            free = "?"
            used = "?"
            allocated = "?"
            reservable = "?"
            penalty = "?"

        humanize.i18n.deactivate()
        t_property = _("Property")
        t_values = _("Value")
        data = {
            _("Region"): region or _("N/A"),
            _("Host"): host,
            _("Port"): f"{port}",
            _("Password"): "*" * min(len(password), 10),
            _("SSL"): secure,
            _("Available"): connected,
            _("Search Only"): search_only,
            _(
                "Players\nConnected\nActive"
            ): f"-\n{pylav_connected_players}/{server_connected_players or '?'}\n{pylav_active_players}/{server_active_players or '?'}",
            _("Frames Lost"): f"{(abs(frames_deficit) + abs(frames_nulled))/(frames_sent or 1) * 100:.2f}%",
            _("Uptime"): uptime,
            _("Load\nLavalink\nSystem"): f"-\n{lavalink_load}%\n{system_load}%",
            _("Penalty"): penalty,
            _("Memory\nUsed\nFree\nAllocated\nReservable"): f"-\n{used}\n{free}\n{allocated}\n{reservable}",
        }
        description = box(
            tabulate([{t_property: k, t_values: v} for k, v in data.items()], headers="keys", tablefmt="fancy_grid")
        )
        embed = await self.cog.lavalink.construct_embed(
            messageable=menu.ctx,
            title=node.name,
            description=description,
        )
        embed.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} {plural}.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                num=len(self.entries),
                plural=_("nodes") if len(self.entries) != 1 else _("node"),
            )
        )
        return embed
