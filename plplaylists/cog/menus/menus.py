from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.vendored.discord.ext import menus

from pylav import emojis
from pylav.sql.models import PlaylistModel
from pylav.types import BotT, ContextT
from pylav.utils import PyLavContext

from plplaylists.cog._types import CogT, SourcesT
from plplaylists.cog.menus.buttons import (
    CloseButton,
    DoneButton,
    EnqueuePlaylistButton,
    NavigateButton,
    PlaylistClearButton,
    PlaylistDedupeButton,
    PlaylistDeleteButton,
    PlaylistDownloadButton,
    PlaylistInfoButton,
    PlaylistQueueButton,
    PlaylistUpdateButton,
    PlaylistUpsertButton,
    RefreshButton,
)

if TYPE_CHECKING:
    from plplaylists.cog.menus.modals import PromptForInput
    from plplaylists.cog.menus.selectors import PlaylistPlaySelector, PlaylistSelectSelector
    from plplaylists.cog.menus.sources import PlaylistPickerSource

LOGGER = getLogger("red.3pt.PyLavPlaylists.ui.menus")

_ = Translator("PyLavPlaylists", Path(__file__))


URL_REGEX = re.compile(r"^(https?)://(\S+)$")


class BaseMenu(discord.ui.View):
    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: menus.ListPageSource,
        *,
        delete_after_timeout: bool = True,
        timeout: int = 120,
        message: discord.Message = None,
        starting_page: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            timeout=timeout,
        )
        self.author = None
        self.ctx = None
        self.cog = cog
        self.bot = bot
        self.message = message
        self._source = source
        self.delete_after_timeout = delete_after_timeout
        self.current_page = starting_page or kwargs.get("page_start", 0)
        self._running = True

    @property
    def source(self) -> menus.ListPageSource:
        return self._source

    async def on_timeout(self):
        self._running = False
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if self.delete_after_timeout and not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    async def get_page(self, page_num: int):
        try:
            if page_num >= self._source.get_max_pages():
                page_num = 0
                self.current_page = 0
            page = await self.source.get_page(page_num)
        except IndexError:
            self.current_page = 0
            page = await self.source.get_page(self.current_page)
        value = await self.source.format_page(self, page)  # type: ignore
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}

    async def send_initial_message(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        kwargs = await self.get_page(self.current_page)
        await self.prepare()
        self.message = await ctx.send(**kwargs, view=self, ephemeral=True)
        return self.message

    async def show_page(self, page_number, interaction: discord.Interaction):
        self.current_page = page_number
        kwargs = await self.get_page(self.current_page)
        await self.prepare()
        if not interaction.response.is_done():
            await interaction.response.edit_message(**kwargs, view=self)
        else:
            await interaction.followup.edit(**kwargs, view=self)

    async def show_checked_page(self, page_number: int, interaction: discord.Interaction) -> None:
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number, interaction)
            elif page_number >= max_pages:
                await self.show_page(0, interaction)
            elif page_number < 0:
                await self.show_page(max_pages - 1, interaction)
            elif max_pages > page_number >= 0:
                await self.show_page(page_number, interaction)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to use owner_ids"""
        if (not await self.bot.allowed_by_whitelist_blacklist(interaction.user, guild=interaction.guild)) or (
            self.author and (interaction.user.id != self.author.id)
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        LOGGER.critical("Interaction check - %s (%s)", interaction.user, interaction.user.id)
        return True

    async def prepare(self):
        return

    async def on_error(self, error: Exception, item: discord.ui.Item[Any], interaction: discord.Interaction) -> None:
        LOGGER.info("Ignoring exception in view %s for item %s:", self, item, exc_info=error)


class PlaylistPickerMenu(BaseMenu):
    _source: PlaylistPickerSource
    result: PlaylistModel

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: PlaylistPickerSource,
        selector_text: str,
        selector_cls: type[PlaylistPlaySelector] | type[PlaylistSelectSelector],  # noqa
        original_author: discord.abc.User,
        *,
        clear_buttons_after: bool = False,
        delete_after_timeout: bool = True,
        timeout: int = 120,
        message: discord.Message = None,
        starting_page: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cog,
            bot,
            source,
            clear_buttons_after=clear_buttons_after,
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )
        self.result: PlaylistModel = None  # type: ignore
        self.selector_cls = selector_cls
        self.selector_text = selector_text
        self.forward_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
            direction=self.source.get_max_pages,
            row=4,
            cog=cog,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=4,
            cog=cog,
        )
        self.refresh_button = RefreshButton(
            style=discord.ButtonStyle.grey,
            row=4,
            cog=cog,
        )
        self.select_view: PlaylistPlaySelector | PlaylistSelectSelector | None = None
        self.author = original_author

    @property
    def source(self) -> PlaylistPickerSource:
        return self._source

    async def prepare(self):
        self.clear_items()
        max_pages = self.source.get_max_pages()
        self.forward_button.disabled = False
        self.backward_button.disabled = False
        self.first_button.disabled = False
        self.last_button.disabled = False
        if max_pages == 2:
            self.first_button.disabled = True
            self.last_button.disabled = True
        elif max_pages == 1:
            self.forward_button.disabled = True
            self.backward_button.disabled = True
            self.first_button.disabled = True
            self.last_button.disabled = True
        self.add_item(self.close_button)
        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)
        if self.source.select_options:  # type: ignore
            options = self.source.select_options  # type: ignore
            self.remove_item(self.select_view)
            self.select_view = self.selector_cls(options, self.cog, self.selector_text, self.source.select_mapping)
            self.add_item(self.select_view)
        if self.select_view and not self.source.select_options:  # type: ignore
            self.remove_item(self.select_view)
            self.select_view = None

    async def start(self, ctx: PyLavContext | discord.Interaction):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.cog.bot.get_context(ctx)
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer(ephemeral=True)
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def show_page(self, page_number: int, interaction: discord.Interaction):
        await self._source.get_page(page_number)
        await self.prepare()
        self.current_page = page_number
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif self.message is not None:
            await self.message.edit(view=self)

    async def wait_for_response(self):
        from plplaylists.cog.menus.selectors import PlaylistSelectSelector

        if isinstance(self.select_view, PlaylistSelectSelector):
            await asyncio.wait_for(self.select_view.responded.wait(), timeout=self.timeout)
            self.result = self.select_view.playlist


class PaginatingMenu(BaseMenu):
    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: SourcesT,
        original_author: discord.abc.User,
        *,
        clear_buttons_after: bool = True,
        delete_after_timeout: bool = False,
        timeout: int = 120,
        message: discord.Message = None,
        starting_page: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cog=cog,
            bot=bot,
            source=source,
            clear_buttons_after=clear_buttons_after,
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )
        self.author = original_author
        self.forward_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=0,
            cog=cog,
        )
        self.backward_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=0,
            cog=cog,
        )
        self.first_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=0,
            cog=cog,
        )
        self.last_button = NavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
            direction=self.source.get_max_pages,
            row=0,
            cog=cog,
        )
        self.refresh_button = RefreshButton(
            style=discord.ButtonStyle.grey,
            row=0,
            cog=cog,
        )

        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=0,
            cog=cog,
        )
        self.add_item(self.close_button)
        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)

    async def start(self, ctx: PyLavContext | discord.Interaction):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.cog.bot.get_context(ctx)
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer(ephemeral=True)
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def prepare(self):
        max_pages = self.source.get_max_pages()
        self.forward_button.disabled = False
        self.backward_button.disabled = False
        self.first_button.disabled = False
        self.last_button.disabled = False
        if max_pages == 2:
            self.first_button.disabled = True
            self.last_button.disabled = True
        elif max_pages == 1:
            self.forward_button.disabled = True
            self.backward_button.disabled = True
            self.first_button.disabled = True
            self.last_button.disabled = True


class PlaylistCreationFlow(discord.ui.View):
    ctx: ContextT
    message: discord.Message
    url_prompt: PromptForInput
    name_prompt: PromptForInput
    scope_prompt: PromptForInput
    author: discord.abc.User

    def __init__(self, cog: CogT, original_author: discord.abc.User, *, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        from plplaylists.cog.menus.modals import PromptForInput

        self.cog = cog
        self.bot = cog.bot
        self.author = original_author
        self.url_prompt = PromptForInput(
            cog=self.cog,
            title=_("Please enter the playlist URL"),
            label=_("Playlist URL"),
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )
        self.name_prompt = PromptForInput(
            cog=self.cog, title=_("Please enter the playlist name"), label=_("Playlist Name"), max_length=64
        )

        self.name_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            row=0,
            cog=cog,
            emoji=emojis.NAME,
            op="name",
        )
        self.url_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            row=0,
            cog=cog,
            emoji=emojis.URL,
            op="url",
        )
        self.done_button = DoneButton(
            style=discord.ButtonStyle.green,
            row=0,
            cog=cog,
        )
        self.queue_button = PlaylistQueueButton(
            style=discord.ButtonStyle.green,
            row=0,
            cog=cog,
            emoji=emojis.QUEUE,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=0,
            cog=cog,
        )

        self.name = None
        self.url = None
        self.scope = None
        self.done = False
        self.queue = None
        self.add_item(self.done_button)
        self.add_item(self.close_button)
        self.add_item(self.name_button)
        self.add_item(self.url_button)
        self.add_item(self.queue_button)

    async def send_initial_message(
        self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None
    ):
        self.ctx = ctx
        self.message = await ctx.send(
            embed=await self.cog.lavalink.construct_embed(description=description, title=title, messageable=ctx),
            view=self,
            ephemeral=True,
        )
        return self.message

    async def start(self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None):
        await self.send_initial_message(ctx, description=description, title=title)

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to use owner_ids"""
        if (not await self.bot.allowed_by_whitelist_blacklist(interaction.user, guild=interaction.guild)) or (
            self.author and (interaction.user.id != self.author.id)
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        return True

    async def prompt_url(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(self.url_prompt)
        await self.url_prompt.responded.wait()
        self.url = self.url_prompt.response

    async def prompt_name(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(self.name_prompt)
        await self.name_prompt.responded.wait()

        self.name = self.name_prompt.response

    async def prompt_scope(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(self.scope_prompt)
        await self.scope_prompt.responded.wait()
        self.scope = self.scope_prompt.response

    async def on_timeout(self):
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    def stop(self):
        super().stop()
        asyncio.ensure_future(self.on_timeout())


class PlaylistManageFlow(discord.ui.View):
    ctx: ContextT
    message: discord.Message
    url_prompt: PromptForInput
    name_prompt: PromptForInput
    scope_prompt: PromptForInput
    author: discord.abc.User

    def __init__(
        self,
        cog: CogT,
        original_author: discord.abc.User,
        playlist: PlaylistModel,
        *,
        timeout: int = 120,
        manageable: bool = True,
    ) -> None:
        super().__init__(timeout=timeout)
        from plplaylists.cog.menus.modals import PromptForInput

        self.completed = asyncio.Event()
        self.cog = cog
        self.bot = cog.bot
        self.author = original_author
        self.playlist = playlist
        self.url_prompt = PromptForInput(
            cog=self.cog,
            title=_("Please enter the playlist URL"),
            label=_("Playlist URL"),
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )
        self.name_prompt = PromptForInput(
            cog=self.cog, title=_("Please enter the new playlist name"), label=_("Playlist Name"), max_length=64
        )

        self.add_prompt = PromptForInput(
            cog=self.cog,
            title=_("What query to add to the playlist"),
            label=_("Query"),
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )

        self.remove_prompt = PromptForInput(
            cog=self.cog,
            title=_("What query to remove from the playlist"),
            label=_("Query"),
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )

        self.name_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            cog=cog,
            emoji=emojis.NAME,
            op="name",
        )
        self.url_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            cog=cog,
            emoji=emojis.URL,
            op="url",
        )
        self.add_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.green,
            cog=cog,
            op="add",
            emoji=emojis.PLUS,
        )
        self.remove_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.red,
            cog=cog,
            op="remove",
            emoji=emojis.MINUS,
        )

        self.done_button = DoneButton(
            style=discord.ButtonStyle.green,
            cog=cog,
        )
        self.delete_button = PlaylistDeleteButton(
            style=discord.ButtonStyle.red,
            cog=cog,
        )
        self.clear_button = PlaylistClearButton(
            style=discord.ButtonStyle.red,
            cog=cog,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            cog=cog,
        )
        self.update_button = PlaylistUpdateButton(
            style=discord.ButtonStyle.green,
            cog=cog,
        )

        self.download_button = PlaylistDownloadButton(
            style=discord.ButtonStyle.blurple,
            cog=cog,
            emoji=emojis.DOWNLOAD,
        )

        self.playlist_enqueue_button = EnqueuePlaylistButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.PLAYLIST,
            playlist=playlist,
        )
        self.playlist_info_button = PlaylistInfoButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.INFO,
            playlist=playlist,
        )
        self.queue_button = PlaylistQueueButton(
            style=discord.ButtonStyle.green,
            cog=cog,
            emoji=emojis.QUEUE,
        )
        self.dedupe_button = PlaylistDedupeButton(
            style=discord.ButtonStyle.red,
            cog=cog,
            emoji=emojis.DUPLICATE,
        )

        self.name = None
        self.url = None
        self.scope = None
        self.add_tracks = set()
        self.remove_tracks = set()

        self.clear = None
        self.delete = None
        self.cancelled = True
        self.done = False
        self.update = False
        self.queue = None
        self.dedupe = None
        if manageable:
            self.add_item(self.done_button)
        self.add_item(self.close_button)
        if manageable:
            self.add_item(self.delete_button)
            self.add_item(self.clear_button)
        self.add_item(self.update_button)
        if manageable:
            self.add_item(self.name_button)
            self.add_item(self.url_button)
            self.add_item(self.add_button)
            self.add_item(self.remove_button)
        self.add_item(self.download_button)

        self.add_item(self.playlist_enqueue_button)
        self.add_item(self.playlist_info_button)
        if manageable:
            self.add_item(self.queue_button)
            self.add_item(self.dedupe_button)

    async def send_initial_message(
        self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None
    ):
        self.ctx = ctx
        if not ctx.channel.permissions_for(ctx.me).attach_files:
            self.download_button.disabled = True
        self.message = await ctx.send(
            embed=await self.cog.lavalink.construct_embed(description=description, title=title, messageable=ctx),
            view=self,
            ephemeral=True,
        )
        return self.message

    async def start(self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None):
        await self.send_initial_message(ctx, description=description, title=title)

    async def interaction_check(self, interaction: discord.Interaction):
        """Just extends the default reaction_check to use owner_ids"""
        if (not await self.bot.allowed_by_whitelist_blacklist(interaction.user, guild=interaction.guild)) or (
            self.author and (interaction.user.id != self.author.id)
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        return True

    async def prompt_url(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.url_prompt)
        await self.url_prompt.responded.wait()
        self.url = self.url_prompt.response

    async def prompt_name(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.name_prompt)
        await self.name_prompt.responded.wait()

        self.name = self.name_prompt.response

    async def prompt_scope(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.scope_prompt)
        await self.scope_prompt.responded.wait()
        self.scope = self.scope_prompt.response

    async def prompt_add_tracks(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.add_prompt)
        await self.add_prompt.responded.wait()
        self.add_tracks.add(self.add_prompt.response)

    async def prompt_remove_tracks(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.remove_prompt)
        await self.remove_prompt.responded.wait()
        self.remove_tracks.add(self.remove_prompt.response)

    async def on_timeout(self):
        self.completed.set()
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    def stop(self):
        super().stop()
        asyncio.ensure_future(self.on_timeout())
