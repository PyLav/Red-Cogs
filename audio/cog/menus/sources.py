from __future__ import annotations

import datetime
import itertools
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import bold, box, humanize_number
from redbot.vendored.discord.ext import menus
from tabulate import tabulate

from pylav import Player, Query, Track
from pylav.sql.models import PlaylistModel
from pylav.utils import AsyncIter, PyLavContext, get_time_string

from audio.cog._types import CogT
from audio.cog.menus.selectors import EffectsOption, PlaylistOption, QueueTrackOption, SearchTrackOption

LOGGER = getLogger("red.3pt.mp.ui.sources")

if TYPE_CHECKING:
    from audio.cog.menus.menus import BaseMenu, QueueMenu, QueuePickerMenu


INF = float("inf")
ASCII_ORDER_SORT = "~" * 100
_ = Translator("MediaPlayer", Path(__file__))


class PreformattedSource(menus.ListPageSource):
    def __init__(self, pages: Iterable[str | discord.Embed]):
        super().__init__(pages, per_page=1)

    async def format_page(self, menu: BaseMenu, page: str | discord.Embed) -> discord.Embed | str:
        return page


class QueueSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: CogT):  # noqa
        self.cog = cog
        self.per_page = 10
        self.guild_id = guild_id

    @property
    def entries(self) -> Iterable[Track]:
        player = self.cog.lavalink.get_player(self.guild_id)
        if not player:
            return []
        return player.queue.raw_queue

    def is_paginating(self) -> bool:
        return True

    async def get_page(self, page_number: int) -> list[Track]:
        base = page_number * self.per_page
        return list(itertools.islice(self.entries, base, base + self.per_page))

    def get_max_pages(self) -> int:
        player = self.cog.lavalink.get_player(self.guild_id)
        if not player:
            return 1
        pages, left_over = divmod(player.queue.size(), self.per_page)
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
            return await self.cog.lavalink.construct_embed(
                description="No active player found in server.", messageable=menu.ctx
            )
        if not player.current:
            page = await self.cog.lavalink.construct_embed(
                description="There's nothing currently being played.", messageable=menu.ctx
            )
        else:
            page = await player.get_queue_page(
                page_index=menu.current_page,
                per_page=self.per_page,
                total_pages=self.get_max_pages(),
                embed=True,
                messageable=menu.ctx,
            )
        return page


class QueuePickerSource(QueueSource):
    def __init__(self, guild_id: int, cog: CogT):
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
        for i, track in enumerate(list(itertools.islice(self.entries, base, base + self.per_page)), start=base):
            self.select_options.append(await QueueTrackOption.from_track(track=track, index=i))
            self.select_mapping[track.id] = track
        return []

    async def format_page(self, menu: QueuePickerMenu, tracks: list[Track]) -> discord.Embed:
        player = self.cog.lavalink.get_player(menu.ctx.guild.id)
        if not player:
            return await self.cog.lavalink.construct_embed(
                description="No active player found in server.", messageable=menu.ctx
            )
        if not player.current:
            page = await self.cog.lavalink.construct_embed(
                description="There's nothing currently being played.", messageable=menu.ctx
            )
        else:
            page = await player.get_queue_page(
                page_index=menu.current_page,
                per_page=self.per_page,
                total_pages=self.get_max_pages(),
                embed=True,
                messageable=menu.ctx,
            )
        return page


class PlaylistPickerSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: CogT, pages: list[PlaylistModel], ctx: PyLavContext | discord.Interaction):
        pages.sort(
            key=lambda p: (
                ([INF], INF, ASCII_ORDER_SORT, INF)
                if len(p.tracks) == 0
                else (
                    ([(-ord(c)) for c in p.scope.lower()]),
                    -len(p.tracks),
                    p.name.lower(),
                ),
            )
        )
        super().__init__(entries=pages, per_page=5)
        self.per_page = 5
        self.guild_id = guild_id
        self.select_options: list[PlaylistOption] = []
        self.cog = cog
        self.ctx = ctx

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, tracks: list[PlaylistModel]) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        page = await menu.cog.construct_embed(ctx=menu.ctx, title=_("Playlists you can access in this server:"))
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
        for i, playlist in enumerate(self.entries[base: base + self.per_page], start=base):
            playlist.author = self.cog.bot.get_user(playlist.author) or playlist.author
            self.select_options.append(PlaylistOption(playlist=playlist, index=i))
        return self.entries[base: base + self.per_page]


class EffectsPickerSource(menus.ListPageSource):
    def __init__(self, guild_id: int, cog: CogT):
        super().__init__(
            entries=[
                "reset",
                "nightcore",
                "vaporwave",
                "synth",
                "bassboost",
                "metal",
                "piano",
                "default",
            ],
            per_page=25,
        )
        self.guild_id = guild_id
        self.select_options: list[EffectsOption] = []
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, tracks: list[PlaylistModel]) -> str:
        return ""

    async def get_page(self, page_number):
        if page_number > self.get_max_pages():
            page_number = 0
        base = page_number * self.per_page
        self.select_options.clear()
        for i, effect in enumerate(self.entries[base: base + self.per_page], start=base):
            if effect in ["reset", "default"]:
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Reset the effects to default."),
                        index=i,
                    )
                )
            elif effect == "nightcore":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Nightcore effect."),
                        index=i,
                    )
                )
            elif effect == "vaporwave":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Vaporwave effect."),
                        index=i,
                    )
                )
            elif effect == "synth":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Synth effect."),
                        index=i,
                    )
                )
            elif effect == "bassboost":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Bassboost equalizer preset."),
                        index=i,
                    )
                )
            elif effect == "metal":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Metal equalizer preset."),
                        index=i,
                    )
                )
            elif effect == "piano":
                self.select_options.append(
                    EffectsOption(
                        label=effect.title(),
                        value=effect,
                        description=_("Apply the Piano equalizer preset."),
                        index=i,
                    )
                )
        return self.entries[base: base + self.per_page]


class ListSource(menus.ListPageSource):
    def __init__(self, cog: CogT, title: str, pages: list[str], per_page: int = 10):
        pages.sort()
        super().__init__(pages, per_page=per_page)
        self.title = title
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, page: list[str]) -> discord.Embed:
        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        text = ""
        for i, entry in enumerate(page, idx_start + 1):
            text += f"{i}. [{entry}]"
        output = box(text, lang="ini")
        embed = await self.cog.lavalink.construct_embed(messageable=menu.ctx, title=self.title, description=output)
        return embed


class EQPresetsSource(menus.ListPageSource):
    def __init__(self, cog: CogT, pages: list[tuple[str, dict]], per_page: int = 10):
        pages.sort()
        super().__init__(pages, per_page=per_page)
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, page: list[tuple[str, dict]]) -> discord.Embed:
        header_name = _("Preset Name")
        header_author = _("Author")
        data = []
        for preset_name, preset_data in page:
            try:
                author = self.cog.bot.get_user(preset_data["author"])
            except TypeError:
                author = "Build-in"
            data.append(
                {
                    header_name: preset_name,
                    header_author: f"{author}",
                }
            )
        embed = await self.cog.lavalink.construct_embed(ctx=menu.ctx, description=box(tabulate(data, headers="keys")))
        return embed


class PlaylistInfoSource(menus.ListPageSource):
    def __init__(self, cog: CogT, playlist: PlaylistModel, scope_name: str, per_page: int = 10):
        super().__init__(playlist.tracks, per_page=per_page)
        self.playlist = playlist
        self.scope_name = scope_name
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, page: list[Track]) -> discord.Embed:
        idx_start, page_num = self.get_starting_index_and_page_number(menu)

        msg = ""
        spaces = "\N{EN SPACE}" * (len(str(len(self.playlist.tracks))) + 2)
        if not len(self.playlist.tracks):
            msg = _("This playlist is empty.")
        else:
            async for track_idx, track in AsyncIter(page).enumerate(start=idx_start + 1):
                query = await Query.from_string(track.uri)
                if query.is_local:
                    if track.title != "Unknown title":
                        msg += "`{}.` **{} - {}**\n{}{}\n".format(
                            track_idx,
                            track.author,
                            track.title,
                            spaces,
                            query.query_to_queue(),
                        )
                    else:
                        msg += f"`{track_idx}.` {query.query_to_queue()}\n"
                else:
                    msg += f"`{track_idx}.` **[{track.title}]({track.uri})**\n"

        author_obj = self.cog.bot.get_user(self.playlist.author) or self.playlist.author or _("Unknown")
        if isinstance(author_obj, discord.abc.User):
            author_obj = author_obj.mention
        if not self.playlist.url:
            embed_title = _("PlaylistModel info for {playlist_name} (`{id}`) [**{scope}**]").format(
                playlist_name=self.playlist.name, id=self.playlist.id, scope=self.scope_name
            )
            authormsg = "{}: {}\n".format(bold(_("Author")), author_obj)
            msg = authormsg + msg

        else:
            embed_title = _("PlaylistModel info for {playlist_name} (`{id}`) [**{scope}**]").format(
                playlist_name=self.playlist.name, id=self.playlist.id, scope=self.scope_name
            )
            newmsg = f"**URL**: [{self.playlist.name}]({self.playlist.url})\n\n"
            authormsg = "{}: {}\n".format(bold(_("Author")), author_obj)
            msg = authormsg + newmsg + msg

        embed = await self.cog.lavalink.construct_embed(messageable=menu.ctx, title=embed_title, description=msg)
        embed.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} tracks.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                num=len(self.entries),
            )
        )
        return embed


class PlaylistListSource(menus.ListPageSource):
    def __init__(self, cog: CogT, pages: list[PlaylistModel], scope: str | None = None):
        pages.sort(
            key=lambda p: (
                ([INF], INF, ASCII_ORDER_SORT, INF)
                if len(p.tracks) == 0
                else (
                    ([(-ord(c)) for c in p.scope.lower()]),
                    -len(p.tracks),
                    p.name.lower(),
                ),
            )
        )
        super().__init__(entries=pages, per_page=5)
        self.per_page = 5
        self.scope = scope
        self.cog = cog

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, playlists: list[PlaylistModel]) -> discord.Embed | str:

        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        plist = ""
        space = "\N{EN SPACE}"
        async for i, playlist in AsyncIter(playlists).enumerate(start=idx_start + 1):
            playlist_info = ("\n" + space * 4).join(
                (
                    bold(playlist.name),
                    _("ID: {id}").format(id=playlist.id),
                    _("Tracks: {num}").format(num=len(playlist.tracks)),
                    _("Author: {name}").format(
                        name=await playlist.get_author_name(self.cog.bot) or playlist.author or _("Unknown")
                    ),
                    _("Scope: {scope}\n").format(scope=await playlist.get_scope_name(self.cog.bot)),
                )
            )
            plist += f"`{i}.` {playlist_info}"

        embed = await menu.cog.construct_embed(
            ctx=menu.ctx,
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


class PlaylistChangeSource(menus.ListPageSource):
    def __init__(
        self,
        menu_title: str,
        tracks: list[Track],
        extras: str,
        per_page: int = 10,
    ):
        super().__init__(tracks, per_page=per_page)
        self.title = menu_title
        self.extras = extras

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, page: list[Track]) -> discord.Embed:
        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        msg = ""
        for i, track in enumerate(page, start=idx_start + 1):
            name = await track.get_track_display_name(max_length=50, with_url=True)
            msg += f"`{i}.` {name}\n"

        embed = await menu.cog.construct_embed(ctx=menu.ctx, title=self.title, description=msg)
        embed.set_footer(
            text=_("Page {page_num}/{total_pages} | {num} tracks {added_or_removed_string}.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                num=len(self.entries),
                added_or_removed_string=self.extras,
            )
        )
        return embed


class PlayersSource(menus.ListPageSource):
    def __init__(self, cog: CogT):
        super().__init__([], per_page=1)
        self.cog = cog

    @property
    def entries(self) -> list[Player]:
        return list(self.cog.lavalink.player_manager.players.values())

    @entries.setter
    def entries(self, players: list[Player]):
        pass

    def get_max_pages(self):
        players = self.cog.lavalink.player_manager.connected_players
        pages, left_over = divmod(len(list(players)), self.per_page)
        if left_over:
            pages += 1
        return pages or 1

    def get_starting_index_and_page_number(self, menu: BaseMenu) -> tuple[int, int]:
        page_num = menu.current_page
        start = page_num * self.per_page
        return start, page_num

    async def format_page(self, menu: BaseMenu, player: Player) -> discord.Embed:
        idx_start, page_num = self.get_starting_index_and_page_number(menu)
        connect_dur = (
            get_time_string(int((datetime.datetime.now(datetime.timezone.utc) - player.connected_at).total_seconds()))
            or "0s"
        )
        guild_name = player.guild.name
        queue_len = len(player.queue)
        server_owner = f"{player.guild.owner} ({player.guild.owner.id})"
        if not player.current:
            current_track = _("Nothing playing.")
        else:
            current_track = await menu.cog.get_track_description(player.current, menu.cog.local_folder_current_path)
        listener_count = sum(True for m in menu.cog.rgetattr(player, "channel.members", []) if not m.bot)
        listeners = humanize_number(listener_count)
        current_track += "\n"

        field_values = "\n".join(
            f"**{i[0]}**: {i[1]}"
            for i in [
                (_("Server Owner"), server_owner),
                (_("Connected For"), connect_dur),
                (_("Users in VC"), listeners),
                (_("Queue Length"), f"{queue_len} tracks"),
            ]
        )
        current_track += field_values

        embed = await menu.cog.construct_embed(ctx=menu.ctx, title=guild_name, description=current_track)

        embed.set_footer(
            text=_("Page {page_num}/{total_pages}  | Playing in {playing} servers.").format(
                page_num=humanize_number(page_num + 1),
                total_pages=humanize_number(self.get_max_pages()),
                playing=humanize_number(len(self.cog.lavalink.player_manager.playing_players)),
            )
        )
        return embed


class SearchPickerSource(menus.ListPageSource):
    def __init__(self, entries: list[Track], ctx: PyLavContext | discord.Interaction, cog: CogT, per_page: int = 10):
        super().__init__(entries=entries, per_page=per_page)
        self.per_page = 25
        self.select_options: list[SearchTrackOption] = []
        self.cog = cog
        self.ctx = ctx

    async def get_page(self, page_number):
        if page_number > self.get_max_pages():
            page_number = 0
        base = page_number * self.per_page
        self.select_options.clear()
        for i, track in enumerate(self.entries[base: base + self.per_page], start=base):
            self.select_options.append(await SearchTrackOption.from_track(track, self.cog, i))
        return []

    async def format_page(self, menu: BaseMenu, entries: list[Track]) -> str:
        return ""
