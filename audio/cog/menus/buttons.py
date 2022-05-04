from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Literal

import discord
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav import emojis
from pylav.utils import AsyncIter

from audio.cog._types import CogT

LOGGER = getLogger("red.3pt.PyLavPlayer.ui.buttons")

_ = Translator("PyLavPlayer", Path(__file__))


class NavigateButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | discord.PartialEmoji,
        direction: int | Callable[[], int],
        row: int = None,
        label: str = None,
    ):

        super().__init__(style=style, emoji=emoji, row=row, label=label)
        self.cog = cog
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
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.PREVIOUS,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_previous.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class StopTrackButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.STOP,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_stop.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class PauseTrackButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.PAUSE,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_pause.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class ResumeTrackButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.PLAY,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_resume.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class SkipTrackButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.NEXT,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_skip.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class RefreshButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class IncreaseVolumeButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.VOLUMEUP,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_volume_change_by.callback(self.cog, interaction, change_by=5)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class DecreaseVolumeButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.VOLUMEDOWN,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_volume_change_by.callback(self.cog, interaction, change_by=-5)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class ToggleRepeatButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.LOOP,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        player = self.cog.lavalink.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    description="Not connected to a voice channel.", messageable=interaction
                ),
                ephemeral=True,
            )
        if player.config.repeat_current:
            repeat_queue = True
        else:
            repeat_queue = False
        await self.cog.command_repeat.callback(self.cog, interaction, queue=repeat_queue)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class ToggleRepeatQueueButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.REPEAT,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        player = self.cog.lavalink.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    description="Not connected to a voice channel.", messageable=interaction
                ),
                ephemeral=True,
            )
        if player.config.repeat_current:
            repeat_queue = True
        else:
            repeat_queue = False
        await self.cog.command_repeat.callback(self.cog, interaction, queue=repeat_queue)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class ShuffleButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.RANDOM,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_shuffle.callback(self.cog, interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class CloseButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.MINIMIZE,
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
        self.view.cancelled = True
        self.view.stop()
        await self.view.on_timeout()


class EqualizerButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.EQUALIZER,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        # TODO: Implement
        kwargs = await self.view.get_page(self.view.current_page)
        await self.view.prepare()
        await interaction.response.edit_message(view=self.view, **kwargs)


class DisconnectButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.POWER,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.cog.command_disconnect.callback(self.cog, interaction)
        self.view.stop()
        await self.view.on_timeout()


class EnqueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emojis.PLUS,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.modals import EnqueueModal

        modal = EnqueueModal(self.cog, _("What do you want to enqueue?"))
        await interaction.response.send_modal(modal)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class RemoveFromQueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emojis.MINUS,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import QueuePickerMenu
        from audio.cog.menus.sources import QueuePickerSource

        picker = QueuePickerMenu(
            bot=self.cog.bot,
            cog=self.cog,
            source=QueuePickerSource(guild_id=interaction.guild.id, cog=self.cog),
            delete_after_timeout=True,
            starting_page=0,
            menu_type="remove",
            original_author=interaction.user,
        )
        await picker.start(interaction)
        await picker.wait()
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class PlayNowFromQueueButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emojis.MUSICALNOTE,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import QueuePickerMenu
        from audio.cog.menus.sources import QueuePickerSource

        picker = QueuePickerMenu(
            bot=self.cog.bot,
            cog=self.cog,
            source=QueuePickerSource(guild_id=interaction.guild.id, cog=self.cog),
            delete_after_timeout=True,
            starting_page=0,
            menu_type="play",
            original_author=interaction.user,
        )
        await picker.start(interaction)
        await picker.wait()
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class EffectPickerButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emojis.SETTINGS,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import EffectPickerMenu
        from audio.cog.menus.sources import EffectsPickerSource

        await EffectPickerMenu(
            cog=self.cog,
            bot=self.cog.bot,
            source=EffectsPickerSource(guild_id=interaction.guild.id, cog=self.cog),
            delete_after_timeout=True,
            clear_buttons_after=False,
            starting_page=0,
            menu_type="play",
            original_author=interaction.user,
        ).start(interaction)
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class AudioStatsDisconnectButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emojis.POWER,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, title=_("You are not authorized to perform this action.")
                ),
                ephemeral=True,
            )
            return
        player = self.view.source.current_player
        if not player:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, title=_("No Player Available For Action - Try Refreshing.")
                ),
                ephemeral=True,
            )
            return
        self.view.bot.dispatch("red_audio_audio_disconnect", player.guild)
        self.cog.update_player_lock(player, False)
        player.queue = []
        player.store("playing_song", None)
        player.store("autoplay_notified", False)
        channel_id = player.fetch("notify_channel")
        notify_channel = player.guild.get_channel_or_thread(channel_id)
        if player.equalizer.changed:
            async with self.cog.config.custom("EQUALIZER", player.guild.id).all() as eq_data:
                eq_data["eq_bands"] = player.equalizer.get()
                eq_data["name"] = player.equalizer.name
        await player.stop()
        await player.disconnect()
        if notify_channel:
            # TODO Use Text input to get a message from owner to send
            await self.cog.send_embed_msg(
                notify_channel, title=_("Bot Owner Action"), description=_("Player disconnected.")
            )
        self.cog._ll_guild_updates.discard(player.guild.id)  # noqa
        await self.cog.api_interface.persistent_queue_api.drop(player.guild.id)
        await self.cog.clean_up_guild_config(
            "last_known_vc_and_notify_channels",
            "last_known_track",
            "currently_auto_playing_in",
            guild_ids=[player.guild.id],
        )

        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class AudioStatsStopTrackButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emojis.STOP,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to perform this action.")
                ),
                ephemeral=True,
            )
            return
        player = self.view.source.current_player
        if not player:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No Player Available For Action - Try Refreshing.")
                ),
                ephemeral=True,
            )
            return
        if player.equalizer.changed:
            async with self.cog.config.custom("EQUALIZER", player.guild.id).all() as eq_data:
                eq_data["eq_bands"] = player.equalizer.get()
                eq_data["name"] = player.equalizer.name
        player.queue = []
        player.store("playing_song", None)
        player.store("prev_requester", None)
        player.store("prev_song", None)
        player.store("requester", None)
        player.store("autoplay_notified", False)
        await player.stop()
        channel_id = player.fetch("notify_channel")
        notify_channel = player.guild.get_channel_or_thread(channel_id)
        if notify_channel:
            # TODO Use Text input to get a message from owner to send?
            await self.cog.send_embed_msg(notify_channel, title=_("Bot Owner Action"), description=_("Player stopped."))
        await self.cog.api_interface.persistent_queue_api.drop(player.guild.id)
        await self.cog.clean_up_guild_config(
            "last_known_vc_and_notify_channels",
            "last_known_track",
            "currently_auto_playing_in",
            guild_ids=[player.guild.id],
        )
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class AudioStatsDisconnectAllButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        disconnect_type: Literal["all", "inactive"],
        style: discord.ButtonStyle,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emojis.POWER,
            row=row,
        )

        self.disconnect_type = disconnect_type
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if not await self.view.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to perform this action.")
                ),
                ephemeral=True,
            )
            return

        players = (
            self.cog.lavalink.player_manager.connected_players
            if self.disconnect_type == "all"
            else self.cog.lavalink.player_manager.not_playing_players
        )
        if not players:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No Players Available For Action - Try Refreshing.")
                ),
                ephemeral=True,
            )
            return
        async for player in AsyncIter(players):
            self.view.bot.dispatch("red_audio_audio_disconnect", player.guild)
            self.cog.update_player_lock(player, False)
            player.queue = []
            channel_id = player.fetch("notify_channel")
            notify_channel = player.guild.get_channel_or_thread(channel_id)
            if player.equalizer.changed:
                async with self.cog.config.custom("EQUALIZER", player.guild.id).all() as eq_data:  # type: ignore
                    eq_data["eq_bands"] = player.equalizer.get()
                    eq_data["name"] = player.equalizer.name
            await player.stop(requester=interaction.user)
            await player.disconnect(requester=interaction.user)
            if notify_channel:
                # TODO Use Text input to get a message from owner to send
                await self.cog.send_embed_msg(
                    notify_channel,
                    title=_("Bot Owner Action"),
                    description=_("Player disconnected."),
                )
            self.cog._ll_guild_updates.discard(player.guild.id)  # noqa
            await self.cog.api_interface.persistent_queue_api.drop(player.guild.id)
            await self.cog.clean_up_guild_config(
                "last_known_vc_and_notify_channels",
                "last_known_track",
                "currently_auto_playing_in",
                guild_ids=[player.guild.id],
            )
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await (await interaction.original_message()).edit(view=self.view, **kwargs)


class LabelButton(discord.ui.Button):
    def __init__(
        self,
        disconnect_type_translation: str,
        multiple=True,
        row: int = None,
    ):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji=None,
            row=row,
        )
        self.label = _("Disconnect {} {}").format(
            disconnect_type_translation, _("players") if multiple else _("player")
        )


class YesButton(discord.ui.Button):
    interaction: discord.Interaction

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(style=style, emoji=None, row=row, label=_("Yes"))
        self.responded = asyncio.Event()
        self.cog = cog
        self.interaction = None  # type: ignore

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
            return

        self.responded.set()
        self.interaction = interaction


class NoButton(discord.ui.Button):
    interaction: discord.Interaction

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(style=style, emoji=None, row=row, label=_("No"))
        self.responded = asyncio.Event()
        self.cog = cog
        self.interaction = None  # type: ignore

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
            return
        self.responded.set()
        self.interaction = interaction


class DoneButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.CHECK,
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
        self.view.done = True
        self.view.cancelled = False
        self.view.stop()
        await self.view.on_timeout()
