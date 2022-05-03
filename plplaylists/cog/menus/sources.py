from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_number
from redbot.vendored.discord.ext import menus

from pylav import Query, Track
from pylav.sql.models import PlaylistModel
from pylav.utils import AsyncIter

from plplaylists.cog._types import CogT
from plplaylists.cog.menus.selectors import PlaylistOption

LOGGER = getLogger("red.3pt.PyLavPlaylists.ui.sources")

if TYPE_CHECKING:
    from plplaylists.cog.menus.menus import PaginatingMenu, PlaylistPickerMenu


INF = float("inf")
ASCII_ORDER_SORT = "~" * 100
_ = Translator("PyLavPlaylists", Path(__file__))


class PlaylistPickerSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: CogT, pages: list[PlaylistModel], message_str: str):
        pages.sort(
            key=lambda p: (
                (INF, ASCII_ORDER_SORT)
                if len(p.tracks) == 0
                else (
                    -len(p.tracks),
                    p.name.lower(),
                ),
            )
        )
        super().__init__(entries=pages, per_page=5)
        self.message_str = message_str
        self.per_page = 5
        self.guild_id = guild_id
        self.select_options: list[PlaylistOption] = []
        self.cog = cog
        self.select_mapping: dict[str, PlaylistModel] = {}

    def get_starting_index_and_page_number(self, menu: PlaylistPickerMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: PlaylistPickerMenu, playlists: list[PlaylistModel]) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        page = await self.cog.lavalink.construct_embed(messageable=menu.ctx, title=self.message_str)
        page.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} playlists.").format(
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
        for i, playlist in enumerate(self.entries[base : base + self.per_page], start=base):  # noqa: E203
            self.select_options.append(await PlaylistOption.from_playlist(playlist=playlist, index=i, bot=self.cog.bot))
            self.select_mapping[f"{playlist.id}"] = playlist
        return self.entries[base : base + self.per_page]  # noqa: E203

    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages or 1


class PlaylistListSource(menus.ListPageSource):
    def __init__(self, cog: CogT, pages: list[PlaylistModel]):
        pages.sort(
            key=lambda p: (
                (INF, ASCII_ORDER_SORT)
                if len(p.tracks) == 0
                else (
                    -len(p.tracks),
                    p.name.lower(),
                ),
            )
        )
        super().__init__(entries=pages, per_page=5)
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: PaginatingMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: PaginatingMenu, playlists: list[PlaylistModel]) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        plist = ""
        space = "\N{EN SPACE}"
        async for i, playlist in AsyncIter(playlists).enumerate(start=idx_start + 1):
            scope_name = await playlist.get_scope_name(self.cog.bot)
            author_name = await playlist.get_author_name(self.cog.bot) or playlist.author or _("Unknown")
            is_same = scope_name == author_name
            playlist_info = ("\n" + space * 4).join(
                (
                    await playlist.get_name_formatted(with_url=True),
                    _("ID: {id}").format(id=playlist.id),
                    _("Tracks: {num}").format(num=len(playlist.tracks)),
                    _("Author: {name}").format(name=author_name),
                    _("Scope: {scope}\n").format(scope=scope_name) if not is_same else "\n",
                )
            )
            plist += f"`{i}.` {playlist_info}"

        embed = await self.cog.lavalink.construct_embed(
            messageable=menu.ctx,
            title=_("Playlists you can access in this server:"),
            description=plist,
        )
        embed.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} playlists.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                num=len(self.entries),
            )
        )
        return embed

    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages or 1


class Base64Source(menus.ListPageSource):
    def __init__(
        self,
        guild_id: int,
        cog: CogT,
        playlist: PlaylistModel,
        author: discord.abc.User,
        entries: list[str],
        per_page: int = 10,
    ):  # noqa
        super().__init__(entries=entries, per_page=per_page)
        self.cog = cog
        self.author = author
        self.guild_id = guild_id
        self.playlist = playlist

    def is_paginating(self) -> bool:
        return True

    def get_starting_index_and_page_number(self, menu: PaginatingMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: PaginatingMenu, tracks: list[str]) -> discord.Embed:
        start_index, page_num = self.get_starting_index_and_page_number(menu)
        padding = len(str(start_index + len(tracks)))
        queue_list = ""
        async for track_idx, track in AsyncIter(tracks).enumerate(start=start_index + 1):
            track = Track(
                node=random.choice(self.cog.lavalink.node_manager.nodes),
                requester=self.author.id,
                data=track,
                query=await Query.from_base64(track),
            )
            track_description = await track.get_track_display_name(max_length=50, with_url=True)
            diff = padding - len(str(track_idx))
            queue_list += f"`{track_idx}.{' ' * diff}` {track_description}\n"
        page = await self.cog.lavalink.construct_embed(
            title=_("Tracks in __{name}__").format(name=self.playlist.name),
            description=queue_list,
            messageable=menu.ctx,
        )
        text = "Page {page_num}/{total_pages} | {num_tracks} tracks\n".format(
            page_num=page_num + 1, total_pages=self.get_max_pages(), num_tracks=len(self.entries)
        )
        page.set_footer(text=text)
        return page

    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages or 1
