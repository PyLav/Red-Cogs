from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator
from redbot.vendored.discord.ext import menus

from pylav.sql.models import PlaylistModel
from pylav.types import BotT, ContextT
from pylav.utils import PyLavContext

from audio.cog._types import CogT, SourcesT
from audio.cog.menus.buttons import (
    AudioNavigateButton,
    AudioStatsDisconnectAllButton,
    AudioStatsDisconnectButton,
    AudioStatsStopTrackButton,
    CloseButton,
    DecreaseVolumeButton,
    DisconnectButton,
    DoneButton,
    EnqueueButton,
    EnqueuePlaylistButton,
    EqualizerButton,
    IncreaseVolumeButton,
    LabelButton,
    NoButton,
    PauseTrackButton,
    PlaylistClearButton,
    PlaylistDeleteButton,
    PlaylistDownloadButton,
    PlaylistInfoButton,
    PlaylistQueueButton,
    PlaylistUpdateButton,
    PlaylistUpsertButton,
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
    YesButton,
)

if TYPE_CHECKING:
    from audio.cog.menus.modals import PromptForInput
    from audio.cog.menus.selectors import (
        EffectsSelector,
        PlaylistPlaySelector,
        PlaylistSelectSelector,
        QueueSelectTrack,
        SearchSelectTrack,
    )
    from audio.cog.menus.sources import (
        EffectsPickerSource,
        PlayersSource,
        PlaylistPickerSource,
        QueuePickerSource,
        QueueSource,
        SearchPickerSource,
    )

LOGGER = getLogger("red.3pt.mp.ui.menus")

_ = Translator("MediaPlayer", Path(__file__))


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


class QueueMenu(BaseMenu):
    _source: QueueSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: QueueSource,
        original_author: discord.abc.User,
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
        self.author = original_author

        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=0,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=0,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=0,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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

        self.queue_disconnect = DisconnectButton(
            style=discord.ButtonStyle.red,
            row=1,
            cog=cog,
        )
        self.repeat_queue_button_on = ToggleRepeatQueueButton(
            style=discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
        )
        self.repeat_button_on = ToggleRepeatButton(
            style=discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
        )
        self.repeat_button_off = ToggleRepeatButton(
            style=discord.ButtonStyle.grey,
            row=1,
            cog=cog,
        )

        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=1,
            cog=cog,
        )

        self.previous_track_button = PreviousTrackButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.stop_button = StopTrackButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.paused_button = PauseTrackButton(
            style=discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
        )
        self.resume_button = ResumeTrackButton(
            style=discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
        )
        self.skip_button = SkipTrackButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )
        self.shuffle_button = ShuffleButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
        )

        self.decrease_volume_button = DecreaseVolumeButton(
            style=discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )
        self.increase_volume_button = IncreaseVolumeButton(
            style=discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )
        self.equalize_button = EqualizerButton(
            style=discord.ButtonStyle.grey,
            row=3,
            cog=cog,
        )

        self.enqueue_button = EnqueueButton(
            cog=cog,
            style=discord.ButtonStyle.green,
            row=3,
        )
        self.remove_from_queue_button = RemoveFromQueueButton(
            cog=cog,
            style=discord.ButtonStyle.red,
            row=3,
        )
        self.play_now_button = PlayNowFromQueueButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
            row=4,
        )
        self.playlist_enqueue_button = EnqueuePlaylistButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
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
            self.playlist_enqueue_button.disabled = True

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
        self.add_item(self.playlist_enqueue_button)
        self.equalize_button.disabled = True
        self.equalize_button.disabled = True

    @property
    def source(self) -> QueueSource:
        return self._source

    async def start(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)


class QueuePickerMenu(BaseMenu):
    _source: QueuePickerSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: QueuePickerSource,
        original_author: discord.abc.User,
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
        self.author = original_author
        self.menu_type = menu_type
        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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
        self.select_view: QueueSelectTrack | None = None
        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)

    @property
    def source(self) -> QueuePickerSource:
        return self._source

    async def start(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def send_initial_message(self, ctx: PyLavContext | discord.Interaction):
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
        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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
        from audio.cog.menus.selectors import PlaylistSelectSelector

        if isinstance(self.select_view, PlaylistSelectSelector):
            await asyncio.wait_for(self.select_view.responded.wait(), timeout=self.timeout)
            self.result = self.select_view.playlist


class EffectPickerMenu(BaseMenu):
    source: EffectsPickerSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: EffectsPickerSource,
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
        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
            direction=self.source.get_max_pages,
            row=4,
            cog=cog,
        )
        self.refresh_button = RefreshButton(
            style=discord.ButtonStyle.grey,
            row=4,
            cog=cog,
        )
        self.close_button = CloseButton(
            style=discord.ButtonStyle.red,
            row=4,
            cog=cog,
        )
        self.select_view: PlaylistPlaySelector | PlaylistSelectSelector | None = None
        self.author = original_author

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
        options = self.source.select_options  # type: ignore
        self.remove_item(self.select_view)
        self.select_view = EffectsSelector(
            options, self.cog, _("Pick An Effect Preset To Apply"), mapping=self.source.select_mapping
        )
        self.add_item(self.select_view)

    async def start(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def show_page(self, page_number: int, interaction: discord.Interaction):
        await self.prepare()
        self.current_page = page_number
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif self.message is not None:
            await self.message.edit(view=self)


class StatsMenu(BaseMenu):
    _source: PlayersSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: PlayersSource,
        original_author: discord.abc.User,
        *,
        clear_buttons_after: bool = False,
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
            clear_buttons_after=clear_buttons_after,
            delete_after_timeout=delete_after_timeout,
            timeout=timeout,
            message=message,
            starting_page=starting_page,
            **kwargs,
        )

        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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
        self.stop_button = AudioStatsStopTrackButton(
            style=discord.ButtonStyle.red,
            row=1,
            cog=cog,
        )
        self.queue_disconnect_label = LabelButton(disconnect_type_translation=_("selected"), row=2, multiple=False)
        self.queue_disconnect = AudioStatsDisconnectButton(
            style=discord.ButtonStyle.red,
            row=2,
            cog=cog,
        )
        self.queue_disconnect_inactive_label = LabelButton(
            disconnect_type_translation=_("inactive"),
            row=3,
        )
        self.queue_disconnect_inactive = AudioStatsDisconnectAllButton(
            disconnect_type="inactive",
            style=discord.ButtonStyle.red,
            row=3,
            cog=cog,
        )
        self.queue_disconnect_all_label = LabelButton(
            disconnect_type_translation=_("all"),
            row=4,
        )
        self.queue_disconnect_all = AudioStatsDisconnectAllButton(
            disconnect_type="all",
            style=discord.ButtonStyle.red,
            row=4,
            cog=cog,
        )
        self.author = original_author

    async def prepare(self):
        self.clear_items()
        max_pages = self.source.get_max_pages()
        self.add_item(self.close_button)
        self.add_item(self.stop_button)
        self.add_item(self.queue_disconnect_label)
        self.add_item(self.queue_disconnect)
        self.add_item(self.first_button)
        self.add_item(self.backward_button)
        self.add_item(self.forward_button)
        self.add_item(self.last_button)
        self.add_item(self.refresh_button)
        self.add_item(self.queue_disconnect_inactive_label)
        self.add_item(self.queue_disconnect_inactive)
        self.add_item(self.queue_disconnect_all_label)
        self.add_item(self.queue_disconnect_all)

        self.forward_button.disabled = False
        self.backward_button.disabled = False
        self.first_button.disabled = False
        self.last_button.disabled = False
        self.refresh_button.disabled = False
        self.queue_disconnect.disabled = False
        self.queue_disconnect_all.disabled = False
        self.queue_disconnect_inactive.disabled = False
        self.stop_button.disabled = False
        self.queue_disconnect_label.disabled = True
        self.queue_disconnect_all_label.disabled = True
        self.queue_disconnect_inactive_label.disabled = True

        if max_pages > 2:
            self.forward_button.disabled = False
            self.backward_button.disabled = False
            self.first_button.disabled = False
            self.last_button.disabled = False
        elif max_pages == 2:
            self.forward_button.disabled = False
            self.backward_button.disabled = False
            self.first_button.disabled = True
            self.last_button.disabled = True
        elif max_pages == 1:
            self.forward_button.disabled = True
            self.backward_button.disabled = True
            self.first_button.disabled = True
            self.last_button.disabled = True
        player = self.source.current_player
        if not player:
            self.stop_button.disabled = True
            self.queue_disconnect.disabled = True
            self.queue_disconnect_label.disabled = True
            self.queue_disconnect_inactive_label.disabled = True
            self.queue_disconnect_all_label.disabled = True
        elif not player.current:
            self.stop_button.disabled = True

        if not len(self.source.entries) > 1:
            self.queue_disconnect_inactive.disabled = True
            self.queue_disconnect_all.disabled = True

        if not len([p for p in self.cog.lavalink.player_manager.connected_players if not p.is_playing]) > 0:
            self.queue_disconnect_inactive.disabled = True

    @property
    def source(self) -> PlayersSource:
        return self._source

    async def start(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def get_page(self, page_num: int):
        if len(self.source.entries) == 0:
            self._source.current_player = None
            return {
                "content": None,
                "embed": await self.cog.lavalink.construct_embed(
                    messageable=self.ctx, title=_("Not connected anywhere.")
                ),
            }
        try:
            if page_num >= self._source.get_max_pages():
                page_num = 0
                self.current_page = 0
            page = await self.source.get_page(page_num)
        except IndexError:
            self.current_page = 0
            page = await self.source.get_page(self.current_page)
        value = await self.source.format_page(self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}


class SearchPickerMenu(BaseMenu):
    source: SearchPickerSource

    def __init__(
        self,
        cog: CogT,
        bot: BotT,
        source: SearchPickerSource,
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
        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=4,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=4,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=4,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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
        self.select_view: SearchSelectTrack | None = None

    async def start(self, ctx: PyLavContext | discord.Interaction):
        self.ctx = ctx
        await self.send_initial_message(ctx)

    async def show_page(self, page_number: int, interaction: discord.Interaction):
        self.current_page = page_number
        kwargs = await self.get_page(self.current_page)
        await self.prepare()
        if not interaction.response.is_done():
            await interaction.response.edit_message(**kwargs, view=self)
        else:
            await interaction.followup.edit(**kwargs, view=self)

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
        if self.source.select_options:  # type: ignore
            options = self.source.select_options  # type: ignore
            title = _("Select Track To Enqueue")
            self.remove_item(self.select_view)
            self.select_view = SearchSelectTrack(options, self.cog, title, self.source.select_mapping)
            self.add_item(self.select_view)
        if self.select_view and not self.source.select_options:  # type: ignore
            self.remove_item(self.select_view)
            self.select_view = None

        self.add_item(self.close_button)


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
        self.forward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=1,
            row=0,
            cog=cog,
        )
        self.backward_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}",
            direction=-1,
            row=0,
            cog=cog,
        )
        self.first_button = AudioNavigateButton(
            style=discord.ButtonStyle.grey,
            emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
            direction=0,
            row=0,
            cog=cog,
        )
        self.last_button = AudioNavigateButton(
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


class PromptYesOrNo(discord.ui.View):
    ctx: ContextT
    message: discord.Message
    author: discord.abc.User
    response: bool

    def __init__(self, cog: CogT, initial_message: str, *, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.initial_message_str = initial_message
        self.yes_button = YesButton(
            style=discord.ButtonStyle.green,
            row=0,
            cog=cog,
        )
        self.no_button = NoButton(
            style=discord.ButtonStyle.red,
            row=0,
            cog=cog,
        )
        self.add_item(self.yes_button)
        self.add_item(self.no_button)
        self._running = True
        self.message = None  # type: ignore
        self.ctx = None  # type: ignore
        self.author = None  # type: ignore
        self.response = None  # type: ignore

    async def on_timeout(self):
        self._running = False
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    async def start(self, ctx: PyLavContext | discord.Interaction):
        await self.send_initial_message(ctx)

    async def send_initial_message(self, ctx: PyLavContext | discord.Interaction):
        if isinstance(ctx, discord.Interaction):
            self.author = ctx.user
        else:
            self.author = ctx.author
        self.ctx = ctx
        self.message = await ctx.send(
            embed=await self.cog.lavalink.construct_embed(description=self.initial_message_str, messageable=ctx),
            view=self,
        )
        return self.message

    async def wait_for_yes_no(self, wait_for: float = None) -> bool:
        tasks = [asyncio.create_task(c) for c in [self.yes_button.responded.wait(), self.no_button.responded.wait()]]
        done, pending = await asyncio.wait(tasks, timeout=wait_for or self.timeout, return_when=asyncio.FIRST_COMPLETED)
        self.stop()
        for task in pending:
            task.cancel()
        if done:
            done.pop().result()
        if not self.message.flags.ephemeral:
            await self.message.delete()
        else:
            await self.message.edit(view=None)
        if self.yes_button.responded.is_set():
            self.response = True
        else:
            self.response = False
        return self.response

    def stop(self):
        super().stop()
        asyncio.ensure_future(self.on_timeout())


class PlaylistCreationFlow(discord.ui.View):
    ctx: ContextT
    message: discord.Message
    url_prompt: PromptForInput
    name_prompt: PromptForInput
    scope_prompt: PromptForInput
    author: discord.abc.User

    def __init__(self, cog: CogT, original_author: discord.abc.User, *, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        from audio.cog.menus.modals import PromptForInput

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
            emoji=discord.PartialEmoji(name="name", animated=False, id=967768470781579284),
            op="name",
        )
        self.url_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            row=0,
            cog=cog,
            emoji=discord.PartialEmoji(name="url", animated=False, id=967753966093991968),
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
            emoji=discord.PartialEmoji(name="queue", animated=False, id=967902316185415681),
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
        self, cog: CogT, original_author: discord.abc.User, playlist: PlaylistModel, *, timeout: int = 120
    ) -> None:
        super().__init__(timeout=timeout)
        from audio.cog.menus.modals import PromptForInput

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
            emoji=discord.PartialEmoji(name="name", animated=False, id=967768470781579284),
            op="name",
        )
        self.url_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            cog=cog,
            emoji=discord.PartialEmoji(name="url", animated=False, id=967753966093991968),
            op="url",
        )
        self.add_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            cog=cog,
            op="add",
            emoji=discord.PartialEmoji(name="plus", animated=False, id=965672202416570368),
        )
        self.remove_button = PlaylistUpsertButton(
            style=discord.ButtonStyle.grey,
            cog=cog,
            op="remove",
            emoji=discord.PartialEmoji(name="minus", animated=False, id=965672202013925447),
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
            emoji=discord.PartialEmoji(name="download", animated=False, id=967760183977730079),
        )

        self.playlist_enqueue_button = EnqueuePlaylistButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
            emoji=discord.PartialEmoji(name="play", animated=False, id=965672202441723994),
            playlist=playlist,
        )
        self.playlist_info_button = PlaylistInfoButton(
            cog=cog,
            style=discord.ButtonStyle.blurple,
            emoji=discord.PartialEmoji(name="info", animated=False, id=967827814160158820),
            playlist=playlist,
        )
        self.queue_button = PlaylistQueueButton(
            style=discord.ButtonStyle.green,
            cog=cog,
            emoji=discord.PartialEmoji(name="queue", animated=False, id=967902316185415681),
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

        self.add_item(self.done_button)
        self.add_item(self.close_button)
        self.add_item(self.delete_button)
        self.add_item(self.clear_button)
        self.add_item(self.update_button)

        self.add_item(self.name_button)
        self.add_item(self.url_button)
        self.add_item(self.add_button)
        self.add_item(self.remove_button)
        self.add_item(self.download_button)

        self.add_item(self.playlist_enqueue_button)
        self.add_item(self.playlist_info_button)
        self.add_item(self.queue_button)

    async def send_initial_message(
        self, ctx: PyLavContext | discord.Interaction, description: str = None, title: str = None
    ):
        self.ctx = ctx
        if not ctx.channel.permissions_for(ctx.me).attach_files:
            self.download_button.disabled = True
        self.message = await ctx.send(
            embed=await self.cog.lavalink.construct_embed(description=description, title=title, messageable=ctx),
            view=self,
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
