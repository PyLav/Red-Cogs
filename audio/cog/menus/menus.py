from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import discord
from red_commons.logging import getLogger
from redbot.core.commands import commands
from redbot.core.i18n import Translator
from redbot.vendored.discord.ext import menus

from audio.cog.menus.buttons import (
    AudioNavigateButton,
    CloseButton,
    DecreaseVolumeButton,
    DisconnectButton,
    EnqueueButton,
    EqualizerButton,
    IncreaseVolumeButton,
    PauseTrackButton,
    PlayNowFromQueueButton,
    PreviousTrackButton,
    RefreshButton,
    RemoveFromQueueButton,
    ResumeTrackButton,
    ShuffleButton,
    SkipTrackButton,
    StopTrackButton,
    ToggleRepeatButton,
    ToggleRepeatQueueButton,
)

if TYPE_CHECKING:
    from redbot.core.bot import Red

    from audio.cog.abc import COG_TYPE
    from audio.cog.menus.selectors import QueueSelectTrack
    from audio.cog.menus.sources import QueuePickerSource, QueueSource


LOGGER = getLogger("red.3pt.mp.ui.menus")

_ = Translator("MediaPlayer", Path(__file__))


class BaseMenu(discord.ui.View):
    def __init__(
        self,
        cog: COG_TYPE,
        bot: Red,
        source: menus.ListPageSource,
        *,
        delete_after_timeout: bool = True,
        timeout: int = 120,
        message: discord.Message = None,
        starting_page: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            timeout=5,
        )
        self.author = None
        self.ctx = None
        self.cog = cog
        self.bot = bot
        self.message = message
        self._source = source
        self.delete_after_timeout = delete_after_timeout
        self.current_page = starting_page or kwargs.get("page_start", 0)

    @property
    def source(self) -> menus.ListPageSource:
        return self._source

    async def on_timeout(self):
        if self.message is None:
            return
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

    async def send_initial_message(self, ctx: commands.Context | discord.Interaction):
        if isinstance(ctx, discord.Interaction):
            self.author = ctx.user
        else:
            self.author = ctx.author
        self.ctx = ctx
        kwargs = await self.get_page(self.current_page)
        await self.prepare()
        self.message = await ctx.send(**kwargs, view=self)
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
        LOGGER.critical("Interaction check - %s (%s)", interaction.user, interaction.user.id)
        if (
            self.author
            and (interaction.user.id != self.author.id)
            and not await self.bot.allowed_by_whitelist_blacklist(self.author, guild=self.ctx.guild)
        ):
            await interaction.response.send_message(
                content="You are not authorized to interact with this.", ephemeral=True
            )
            return False
        return True

    async def prepare(self):
        return

    async def on_error(self, error: Exception, item: discord.ui.Item[Any], interaction: discord.Interaction) -> None:
        LOGGER.info("Ignoring exception in view %s for item %s:", self, item, exc_info=error)


class QueueMenu(BaseMenu):
    _source: QueueSource

    def __init__(
        self,
        cog: COG_TYPE,
        bot: Red,
        source: QueueSource,
        *,
        delete_after_timeout: bool = True,
        timeout: int = 600,
        message: discord.Message = None,
        starting_page: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cog=cog,
            bot=bot,
            source=source,
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )

        self.forward_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=0,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=0,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=0,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
            direction=self.source.get_max_pages,
            row=0,
            cog=cog,
        )
        self.refresh_button = RefreshButton(
            discord.ButtonStyle.grey,
            row=0,
            cog=cog,
        )

        self.queue_disconnect = DisconnectButton(
            discord.ButtonStyle.red,
            row=1,
            cog=cog,
        )
        self.repeat_queue_button_on = ToggleRepeatQueueButton(
            discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
        )
        self.repeat_button_on = ToggleRepeatButton(
            discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
        )
        self.repeat_button_off = ToggleRepeatButton(
            discord.ButtonStyle.grey,
            row=1,
            cog=cog,
        )

        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=1,
            cog=cog,
        )

        self.previous_track_button = PreviousTrackButton(
            discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.stop_button = StopTrackButton(
            discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.paused_button = PauseTrackButton(
            discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
        )
        self.resume_button = ResumeTrackButton(
            discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
        )
        self.skip_button = SkipTrackButton(
            discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.shuffle_button = ShuffleButton(
            discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )

        self.decrease_volume_button = DecreaseVolumeButton(
            discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )
        self.increase_volume_button = IncreaseVolumeButton(
            discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )
        self.equalize_button = EqualizerButton(
            discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )

        self.enqueue_button = EnqueueButton(
            self.cog,
            discord.ButtonStyle.green,
            row=3,
        )
        self.remove_from_queue_button = RemoveFromQueueButton(
            self.cog,
            discord.ButtonStyle.red,
            row=3,
        )
        self.play_now_button = PlayNowFromQueueButton(
            self.cog,
            discord.ButtonStyle.blurple,
            row=4,
        )

    async def prepare(self):
        self.clear_items()
        max_pages = self.source.get_max_pages()
        self.add_item(self.close_button)
        self.add_item(self.queue_disconnect)

        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)
        self.add_item(self.refresh_button)

        self.repeat_button_on.disabled = False
        self.repeat_button_off.disabled = False
        self.repeat_queue_button_on.disabled = False

        self.forward_button.disabled = False
        self.backward_button.disabled = False
        self.first_button.disabled = False
        self.last_button.disabled = False
        self.refresh_button.disabled = False

        self.previous_track_button.disabled = False
        self.paused_button.disabled = False
        self.resume_button.disabled = False
        self.stop_button.disabled = False
        self.skip_button.disabled = False
        self.shuffle_button.disabled = False

        self.decrease_volume_button.disabled = False
        self.increase_volume_button.disabled = False
        self.equalize_button.disabled = False
        self.enqueue_button.disabled = False
        self.remove_from_queue_button.disabled = False
        self.play_now_button.disabled = False

        self.add_item(self.previous_track_button)
        self.add_item(self.stop_button)

        if max_pages == 2:
            self.first_button.disabled = True
            self.last_button.disabled = True
        elif max_pages == 1:
            self.forward_button.disabled = True
            self.backward_button.disabled = True
            self.first_button.disabled = True
            self.last_button.disabled = True
        player = self.cog.lavalink.get_player(self.source.guild_id)
        if not player:
            self.forward_button.disabled = True
            self.backward_button.disabled = True
            self.first_button.disabled = True
            self.last_button.disabled = True
            self.stop_button.disabled = True
            self.skip_button.disabled = True
            self.previous_track_button.disabled = True
            self.repeat_button_off.disabled = True
            self.shuffle_button.disabled = True
            self.decrease_volume_button.disabled = True
            self.increase_volume_button.disabled = True
            self.resume_button.disabled = True
            self.repeat_button_on.disabled = True
            self.equalize_button.disabled = True
            self.enqueue_button.disabled = True
            self.remove_from_queue_button.disabled = True
            self.play_now_button.disabled = True
            self.repeat_queue_button_on.disabled = True

            self.add_item(self.resume_button)
            self.add_item(self.repeat_button_off)
        else:
            if player.paused:
                self.add_item(self.resume_button)
            else:
                self.add_item(self.paused_button)
            if player.queue.empty():
                self.shuffle_button.disabled = True
                self.remove_from_queue_button.disabled = True
                self.play_now_button.disabled = True
            if not player.current:
                self.equalize_button.disabled = True
                self.stop_button.disabled = True
                self.shuffle_button.disabled = True
                self.previous_track_button.disabled = True
                self.decrease_volume_button.disabled = True
                self.increase_volume_button.disabled = True
            if player.history.empty():
                self.previous_track_button.disabled = True
            if player.repeat_current:
                self.add_item(self.repeat_button_on)
            elif player.repeat_queue:
                self.add_item(self.repeat_queue_button_on)
            else:
                self.add_item(self.repeat_button_off)

        self.add_item(self.skip_button)
        self.add_item(self.shuffle_button)
        self.add_item(self.decrease_volume_button)
        self.add_item(self.increase_volume_button)
        self.add_item(self.equalize_button)
        self.add_item(self.enqueue_button)
        self.add_item(self.remove_from_queue_button)
        self.add_item(self.play_now_button)
        self.equalize_button.disabled = True
        self.equalize_button.disabled = True

    @property
    def source(self) -> QueueSource:
        return self._source

    async def start(self, ctx: commands.Context | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)


class QueuePickerMenu(BaseMenu):
    _source: QueuePickerSource

    def __init__(
        self,
        cog: COG_TYPE,
        bot: Red,
        source: QueuePickerSource,
        *,
        delete_after_timeout: bool = True,
        timeout: int = 120,
        message: discord.Message = None,
        starting_page: int = 0,
        menu_type: Literal["remove", "play"],
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cog=cog,
            bot=bot,
            source=source,
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )
        self.menu_type = menu_type
        self.forward_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
            discord.ButtonStyle.grey,
            "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
            direction=self.source.get_max_pages,
            row=4,
            cog=cog,
        )
        self.refresh_button = RefreshButton(
            discord.ButtonStyle.grey,
            row=4,
            cog=cog,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=4,
            cog=cog,
        )
        self.select_view: QueueSelectTrack | None = None
        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)

    @property
    def source(self) -> QueuePickerSource:
        return self._source

    async def start(self, ctx: commands.Context | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def send_initial_message(self, ctx: commands.Context | discord.Interaction):
        if isinstance(ctx, discord.Interaction):
            self.author = ctx.user
        else:
            self.author = ctx.author
        await self._source.get_page(0)
        self.ctx = ctx
        embed = await self.source.format_page(self, [])
        await self.prepare()
        self.message = await ctx.send(embed=embed, view=self, ephemeral=True)
        return self.message

    async def show_page(self, page_number: int, interaction: discord.Interaction):
        await self._source.get_page(page_number)
        await self.prepare()
        self.current_page = page_number
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif self.message is not None:
            await self.message.edit(view=self)

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
        if self.source.select_options:
            from audio.cog.menus.selectors import QueueSelectTrack

            options = self.source.select_options
            if self.menu_type == "remove":
                title = _("Select Track To Remove")
            else:
                title = _("Select Track To Play Now")
            self.remove_item(self.select_view)
            self.select_view = QueueSelectTrack(
                options=options,
                cog=self.cog,
                placeholder=title,
                interaction_type=self.menu_type,
                mapping=self.source.select_mapping,
            )
            self.add_item(self.select_view)
        if self.select_view and not self.source.select_options:
            self.remove_item(self.select_view)
            self.select_view = None
