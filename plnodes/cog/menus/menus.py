from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import inline
from redbot.vendored.discord.ext import menus

from pylav import emojis
from pylav.sql.models import NodeModel
from pylav.types import BotT, ContextT
from pylav.utils import PyLavContext

from plnodes.cog._types import CogT
from plnodes.cog.menus.buttons import (
    CloseButton,
    DoneButton,
    NavigateButton,
    NodeButton,
    RefreshButton,
    SearchOnlyNodeToggleButton,
    SSLNodeToggleButton,
)

if TYPE_CHECKING:
    from plnodes.cog.menus.selectors import NodeSelectSelector
    from plnodes.cog.menus.sources import NodeListSource, NodePickerSource

LOGGER = getLogger("red.3pt.PyLavNodes.ui.menus")

_ = Translator("PyLavNodes", Path(__file__))


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


class AddNodeFlow(discord.ui.View):
    ctx: ContextT
    message: discord.Message
    author: discord.abc.User

    def __init__(self, cog: CogT, original_author: discord.abc.User):
        super().__init__(timeout=600)
        from plnodes.cog.menus.modals import PromptForInput
        from plnodes.cog.menus.selectors import SourceSelector

        self.cog = cog
        self.bot = cog.bot
        self.author = original_author
        self.cancelled = True
        self.completed = asyncio.Event()
        self.done_button = DoneButton(
            style=discord.ButtonStyle.green,
            cog=cog,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            cog=cog,
        )
        self.host_prompt = PromptForInput(
            cog=self.cog,
            title=_("Enter the domain or IP address of the host"),
            label=_("Host"),
            style=discord.TextStyle.short,
            min_length=4,
            max_length=200,
        )
        self.port_prompt = PromptForInput(
            cog=self.cog,
            title=_("Enter the host port to connect to"),
            label=_("Port"),
            style=discord.TextStyle.short,
            min_length=2,
            max_length=5,
        )
        self.password_prompt = PromptForInput(
            cog=self.cog,
            title=_("Enter the node's password"),
            label=_("Password"),
            style=discord.TextStyle.short,
            min_length=1,
            max_length=64,
        )
        self.name_prompt = PromptForInput(
            cog=self.cog,
            title=_("Enter an easy to know name for the node."),
            label=_("Name"),
            style=discord.TextStyle.short,
            min_length=8,
            max_length=64,
        )
        self.resume_timeout_prompt = PromptForInput(
            cog=self.cog,
            title=_("Enter a timeout in seconds."),
            label=_("Password"),
            style=discord.TextStyle.short,
            min_length=2,
            max_length=4,
        )
        self.search_only_button = SearchOnlyNodeToggleButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.SEARCH,
        )
        self.ssl_button = SSLNodeToggleButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.SSL,
        )
        self.disabled_sources_selector = SourceSelector(cog=self.cog, placeholder=_("Source to disable."), row=2)
        self.name_button = NodeButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.NAME,
            op="name",
            row=1,
        )
        self.host_button = NodeButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.HOST,
            op="host",
            row=1,
        )
        self.port_button = NodeButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.PORT,
            op="port",
            row=1,
        )
        self.password_button = NodeButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.PASSWORD,
            op="password",
            row=1,
        )
        self.timeout_button = NodeButton(
            cog=self.cog,
            style=discord.ButtonStyle.blurple,
            emoji=emojis.TIMEOUT,
            op="timeout",
            row=1,
        )

        self.name = None
        self.host = None
        self.port = None
        self.password = None
        self.resume_timeout = 600
        self.reconnect_attempts = -1
        self.ssl = False
        self.search_only = False
        self.unique_identifier = None
        self.done = False

        self.add_item(self.done_button)
        self.add_item(self.close_button)
        self.add_item(self.search_only_button)
        self.add_item(self.ssl_button)

        self.add_item(self.name_button)
        self.add_item(self.host_button)
        self.add_item(self.port_button)
        self.add_item(self.password_button)
        self.add_item(self.timeout_button)

        self.add_item(self.disabled_sources_selector)
        self.last_interaction = None

    def stop(self):
        super().stop()
        asyncio.ensure_future(self.on_timeout())

    async def on_timeout(self):
        self.completed.set()
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    async def wait_until_complete(self):
        await asyncio.wait_for(self.completed.wait(), timeout=self.timeout)

    async def start(self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None):
        self.unique_identifier = ctx.message.id
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

    async def prompt_name(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.name_prompt)
        await self.name_prompt.responded.wait()
        self.name = self.name_prompt.response
        await interaction.followup.send(
            embed=await self.cog.lavalink.construct_embed(
                description=_("Name set to {name}").format(name=inline(self.name)),
                messageable=interaction,
            ),
            ephemeral=True,
        )

    async def prompt_password(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.password_prompt)
        await self.password_prompt.responded.wait()
        self.password = self.password_prompt.response
        await interaction.followup.send(
            embed=await self.cog.lavalink.construct_embed(
                description=_("Password set to {password}").format(password=inline(self.password)),
                messageable=interaction,
            ),
            ephemeral=True,
        )

    async def prompt_host(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.host_prompt)
        await self.host_prompt.responded.wait()
        if match := URL_REGEX.match(self.host_prompt.response):
            protocol = match.group(0)
            if protocol == "https":
                self.ssl = True
            else:
                self.ssl = False
            self.host = match.group(1)
        else:
            self.host = self.host_prompt.response
        await interaction.followup.send(
            embed=await self.cog.lavalink.construct_embed(
                description=_("Host set to {host}").format(host=inline(self.host)),
                messageable=interaction,
            ),
            ephemeral=True,
        )

    async def prompt_port(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.port_prompt)
        await self.port_prompt.responded.wait()
        try:
            self.port = int(self.port_prompt.response)
        except ValueError:
            self.port = None
        if self.port is None:
            await interaction.followup.send(
                embed=await self.cog.lavalink.construct_embed(
                    description=_("Invalid port."),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=await self.cog.lavalink.construct_embed(
                    description=_("Port set to {port}").format(port=inline(f"{self.port}")),
                    messageable=interaction,
                ),
                ephemeral=True,
            )

    async def prompt_resume_timeout(self, interaction: discord.Interaction) -> None:
        self.cancelled = False
        await interaction.response.send_modal(self.resume_timeout_prompt)
        await self.resume_timeout_prompt.responded.wait()
        try:
            self.resume_timeout = int(self.resume_timeout_prompt.response)
        except ValueError:
            self.resume_timeout = None
        if self.resume_timeout is None:
            await interaction.followup.send(
                embed=await self.cog.lavalink.construct_embed(
                    description=_("Invalid timeout, it must be a number in seconds."),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=await self.cog.lavalink.construct_embed(
                    description=_("Timeout set to {timeout} seconds.").format(timeout=inline(f"{self.resume_timeout}")),
                    messageable=interaction,
                ),
                ephemeral=True,
            )


class NodePickerMenu(BaseMenu):
    _source: NodePickerSource
    result: NodeModel

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: NodePickerSource,
        selector_text: str,
        selector_cls: type[NodeSelectSelector],  # noqa
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
        self.result: NodeModel = None  # type: ignore
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
        self.select_view: NodeSelectSelector | None = None
        self.author = original_author

    @property
    def source(self) -> NodePickerSource:
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
        from plnodes.cog.menus.selectors import NodeSelectSelector

        if isinstance(self.select_view, NodeSelectSelector):
            await asyncio.wait_for(self.select_view.responded.wait(), timeout=self.timeout)
            self.result = self.select_view.node


class NodeManagerMenu(BaseMenu):
    _source: NodeListSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: NodeListSource,
        original_author: discord.abc.User,
        *,
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
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )
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
        self.author = original_author

    @property
    def source(self) -> NodeListSource:
        return self._source

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
