from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Iterable

import discord
from red_commons.logging import getLogger
from redbot.vendored.discord.ext import menus

from pylav import Track

from audio.cog.menus.selectors import QueueTrackOption

LOGGER = getLogger("red.3pt.mp.ui.sources")

if TYPE_CHECKING:
    from audio import MediaPlayer
    from audio.cog.menus.menus import BaseMenu, QueueMenu

    COG = MediaPlayer


INF = float("inf")
ASCII_ORDER_SORT = "~" * 100


class AudioPreformattedSource(menus.ListPageSource):
    def __init__(self, pages: Iterable[str | discord.Embed]):
        super().__init__(pages, per_page=1)

    async def format_page(self, menu: BaseMenu, page: str | discord.Embed) -> discord.Embed | str:
        if isinstance(page, discord.Embed) and page.colour is None:
            page.colour = await menu.ctx.embed_colour()
        return page


class QueueSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: MediaPlayer):
        self.cog = cog
        self.per_page = 10
        self.guild_id = guild_id

    @property
    def entries(self) -> Iterable[tuple[int, Track]]:
        player = self.cog.lavalink.get_player(self.guild_id)
        if not player:
            return []
        return player.queue._queue

    def is_paginating(self) -> bool:
        return True

    async def get_page(self, page_number: int) -> list[Track]:
        base = page_number * self.per_page
        output = list(itertools.islice(self.entries, base, base + self.per_page))
        return [i for _, i in output]

    def get_max_pages(self) -> int:
        player = self.cog.lavalink.get_player(self.guild_id)
        if not player:
            return 1
        pages, left_over = divmod(player.queue.qsize(), self.per_page)
        if left_over:
            pages += 1
        return pages or 1

    def get_starting_index_and_page_number(self, menu: QueueMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: QueueMenu, tracks: list[Track]) -> discord.Embed:
        player = self.cog.lavalink.get_player(menu.ctx.guild.id)
        if not player:
            return await self.cog.lavalink.construct_embed(description="No active player found in server.")
        if not player.current:
            page = await self.cog.lavalink.construct_embed(description="There's nothing currently being played.")
        else:
            page = await player.get_queue_page(
                page_index=menu.current_page, per_page=self.per_page, total_pages=self.get_max_pages(), embed=True
            )
        return page


class QueuePickerSource(QueueSource):
    def __init__(self, guild_id: int, cog: MediaPlayer):
        super().__init__(guild_id, cog=cog)
        self.per_page = 25
        self.select_options: list[QueueTrackOption] = []
        self.select_mapping: dict[str, Track] = {}
        self.cog = cog

    async def get_page(self, page_number):
        if page_number > self.get_max_pages():
            page_number = 0
        base = page_number * self.per_page
        self.select_options.clear()
        self.select_mapping.clear()
        for i, (_, track) in enumerate(list(itertools.islice(self.entries, base, base + self.per_page)), start=base):
            self.select_options.append(await QueueTrackOption.from_track(track=track, cog=self.cog, index=i))
            self.select_mapping[track.unique_identifier] = track
        return []
