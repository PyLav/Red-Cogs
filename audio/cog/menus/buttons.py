from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import discord
from red_commons.logging import getLogger

if TYPE_CHECKING:
    from audio.cog import MediaPlayer


LOGGER = getLogger("red.3pt.mp.ui.buttons")


class AudioNavigateButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle,
        emoji: str | discord.PartialEmoji,
        direction: int | Callable[[], int],
        row: int = None,
        label: str = None,
    ):
        super().__init__(style=style, emoji=emoji, row=row, label=label)

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


class PreviousTrackButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="previous", id=965672202424950795, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx, interaction=interaction, command=self.view.cog.command_prev, args=""
        )


class StopTrackButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="stop", id=965672202563362926, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx, interaction=interaction, command=self.view.cog.command_stop, args=""
        )


class PauseTrackButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="pause", id=965672202466910268, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx,
            interaction=interaction,
            command=self.view.cog.command_pause,
            args="",
        )
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class ResumeTrackButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="play", id=965672202441723994, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx,
            interaction=interaction,
            command=self.view.cog.command_pause,
            args="",
        )
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class SkipTrackButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="next", id=965672202416570428, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx, interaction=interaction, command=self.view.cog.command_skip, args=""
        )
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class RefreshButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class IncreaseVolumeButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="volumeup", id=965672202517225492, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_increase_volume(self.view.ctx, interaction)
        if success:
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await interaction.response.edit_message(view=self.view, **kwargs)


class DecreaseVolumeButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="volumedown", id=965672202399801374, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_decrease_volume(self.view.ctx, interaction)
        if success:
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await interaction.response.edit_message(view=self.view, **kwargs)


class ToggleRepeatButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="loop", id=965672202143928362, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_toggle_repeat(self.view.ctx, interaction)
        if success:
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await interaction.response.edit_message(view=self.view, **kwargs)


class ToggleRepeatQueueButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="repeat", id=965672202412388352, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_toggle_repeat(self.view.ctx, interaction)
        if success:
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await interaction.response.edit_message(view=self.view, **kwargs)


class ShuffleButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="random", id=965672202458509463, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_shuffle(self.view.ctx, interaction)
        if success:
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await interaction.response.edit_message(view=self.view, **kwargs)


class QueueInfoButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="menu", id=965672202466910238, animated=False),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.prepare()
        await self.view.ctx.send_help(self.view.cog.command_queue)
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class CloseButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="minimize", animated=False, id=965672202424963142),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        await interaction.message.delete()


class EqualizerButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="equalizer", animated=False, id=965672202454323250),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.cog.dispatch_msg(  # FIXME:
            ctx=self.view.ctx,
            interaction=interaction,
            command=self.view.cog.command_equalizer,
            args="",
        )
        kwargs = await self.view.get_page(self.view.current_page)
        await self.view.prepare()
        await interaction.response.edit_message(view=self.view, **kwargs)


class DisconnectButton(discord.ui.Button):
    def __init__(self, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="power", animated=False, id=965672202395586691),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        success = await self.view.cog.menu_disconnect(self.view.ctx, interaction)
        if success:
            self.view.stop()
            await interaction.message.delete()


class EnqueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: MediaPlayer,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="plus", animated=False, id=965672202416570368),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.modals import EnqueueModal

        modal = EnqueueModal(self.cog, self.view.ctx, self, "What do you want to enqueue?")
        await interaction.response.send_modal(modal)


class RemoveFromQueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: MediaPlayer,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="minus", animated=False, id=965672202013925447),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import QueuePickerMenu
        from audio.cog.menus.sources import QueuePickerSource

        await QueuePickerMenu(
            cog=self.view.ctx.cog,
            bot=self.view.bot,
            source=QueuePickerSource(guild_id=self.view.ctx.guild.id, cog=self.view.ctx.cog),
            delete_after_timeout=True,
            starting_page=0,
            menu_type="remove",
        ).start(self.view.ctx)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class PlayNowFromQueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: MediaPlayer,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="musicalnote", animated=False, id=965674278144077824),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import QueuePickerMenu
        from audio.cog.menus.sources import QueuePickerSource

        await QueuePickerMenu(
            cog=self.view.ctx.cog,
            bot=self.view.bot,
            source=QueuePickerSource(guild_id=self.view.ctx.guild.id, cog=self.view.ctx.cog),
            delete_after_timeout=True,
            starting_page=0,
            menu_type="play",
        ).start(self.view.ctx)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)
