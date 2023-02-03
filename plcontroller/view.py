from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from redbot.core.i18n import Translator

from pylav.extension.red.utils import rgetattr
from pylav.helpers import emojis
from pylav.helpers.singleton import synchronized_method_call_with_self_threading_lock
from pylav.players.player import Player
from pylav.type_hints.bot import DISCORD_INTERACTION_TYPE

_ = Translator("PyLavController", Path(__file__))


if TYPE_CHECKING:
    from plcontroller.cog import PyLavController


class IncreaseVolumeButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.VOLUME_UP,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.volume(context, change_by=5)
        await self.view.update_view()


class DecreaseVolumeButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.VOLUME_DOWN,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.volume(context, change_by=-5)
        await self.view.update_view()


class StopTrackButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.STOP,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.stop(context)
        await self.view.update_view(forced=True)


class PauseTrackButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.PAUSE,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.pause(context)
        await self.view.update_view()


class ResumeTrackButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.PLAY,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.resume(context)
        await self.view.update_view()


class SkipTrackButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.NEXT,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.skip(context)
        await self.view.update_view()


class ToggleRepeatButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.LOOP,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        player = context.player
        if not player:
            return await context.send(
                embed=await self.cog.pylav.construct_embed(
                    description=_("I am not connected to any voice channel at the moment."), messageable=interaction
                ),
                ephemeral=True,
            )
        await self.cog.repeat(context, queue=await player.config.fetch_repeat_current())
        await self.view.update_view()


class QueueHistoryButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.PLAYLIST,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        if not (__ := context.player):
            return await context.send(
                embed=await self.cog.pylav.construct_embed(
                    description=_("I am not connected to any voice channel at the moment."), messageable=interaction
                ),
                ephemeral=True,
            )
        from pylav.extension.red.ui.menus.queue import QueueMenu
        from pylav.extension.red.ui.sources.queue import QueueSource

        await QueueMenu(
            cog=self.cog,
            bot=self.cog.bot,
            source=QueueSource(guild_id=interaction.guild.id, cog=self.cog, history=True),
            original_author=interaction.user,
            history=True,
        ).start(ctx=context)


class ToggleRepeatQueueButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.REPEAT,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        player = context.player
        if not player:
            return await context.send(
                embed=await self.cog.pylav.construct_embed(
                    description=_("I am not connected to any voice channel at the moment."), messageable=interaction
                ),
                ephemeral=True,
            )
        repeat_queue = bool(await player.config.fetch_repeat_current())
        await self.cog.repeat(context, queue=repeat_queue)
        await self.view.update_view()


class ShuffleButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.RANDOM,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.shuffle(context)
        await self.view.update_view()


class PreviousTrackButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji=emojis.PREVIOUS,
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        context = await self.cog.bot.get_context(interaction)
        await self.cog.previous(context)
        await self.view.update_view()


class RefreshButton(discord.ui.Button):
    def __init__(self, cog: PyLavController, style: discord.ButtonStyle, row: int = None, custom_id: str | None = None):
        super().__init__(
            style=style,
            emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
            row=row,
            custom_id=custom_id,
        )
        self.cog = cog

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await self.view.update_view()


class PersistentControllerView(discord.ui.View):
    def __init__(
        self,
        cog: PyLavController,
        channel: discord.TextChannel | discord.Thread | discord.VoiceChannel,
        message: discord.Message = None,
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.message: discord.Message | None = message
        self.channel = channel
        self.guild = channel.guild
        self._threading_lock = threading.Lock()

        self.repeat_queue_button_on = ToggleRepeatQueueButton(
            style=discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:repeat_queue_button_on:1",
        )
        self.repeat_button_on = ToggleRepeatButton(
            style=discord.ButtonStyle.blurple,
            row=1,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:repeat_button_on:2",
        )
        self.repeat_button_off = ToggleRepeatButton(
            style=discord.ButtonStyle.grey,
            row=1,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:repeat_button_off:3",
        )

        self.show_history_button = QueueHistoryButton(
            style=discord.ButtonStyle.grey,
            row=1,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:show_history_button:4",
        )

        self.decrease_volume_button = DecreaseVolumeButton(
            style=discord.ButtonStyle.red,
            row=3,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:decrease_volume_button:5",
        )
        self.increase_volume_button = IncreaseVolumeButton(
            style=discord.ButtonStyle.green,
            row=3,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:increase_volume_button:6",
        )

        self.refresh_button = RefreshButton(
            style=discord.ButtonStyle.green,
            row=3,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:refresh_button:13",
        )

        self.paused_button = PauseTrackButton(
            style=discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:paused_button:7",
        )
        self.resume_button = ResumeTrackButton(
            style=discord.ButtonStyle.blurple,
            row=2,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:resume_button:8",
        )

        self.previous_track_button = PreviousTrackButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:previous_track_button:9",
        )
        self.skip_button = SkipTrackButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:skip_button:10",
        )
        self.shuffle_button = ShuffleButton(
            style=discord.ButtonStyle.grey,
            row=2,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:shuffle_button:11",
        )

        self.stop_button = StopTrackButton(
            style=discord.ButtonStyle.red,
            row=4,
            cog=cog,
            custom_id="pylav__pylavcontroller_persistent_view:stop_button:12",
        )

    def set_message(self, message: discord.Message):
        self.message = message

    @synchronized_method_call_with_self_threading_lock()
    async def prepare(self):
        player = self.cog.pylav.get_player(self.channel.guild.id)
        self.clear_items()
        self.show_history_button.disabled = False
        self.repeat_button_on.disabled = False
        self.repeat_button_off.disabled = False
        self.repeat_queue_button_on.disabled = False
        self.decrease_volume_button.disabled = False
        self.increase_volume_button.disabled = False
        self.refresh_button.disabled = False
        self.paused_button.disabled = False
        self.resume_button.disabled = False
        self.previous_track_button.disabled = False
        self.skip_button.disabled = False
        self.shuffle_button.disabled = False
        self.stop_button.disabled = False

        if (player is not None) and (repeat_current := await player.config.fetch_repeat_current()):
            self.add_item(self.repeat_button_on)
        elif (player is not None) and (not repeat_current) and (await player.config.fetch_repeat_queue()):
            self.add_item(self.repeat_queue_button_on)
        else:
            self.add_item(self.repeat_button_off)
        self.add_item(self.show_history_button)
        self.add_item(self.decrease_volume_button)
        self.add_item(self.increase_volume_button)
        self.add_item(self.refresh_button)

        if player is not None and player.paused or player is None:
            self.add_item(self.resume_button)
        else:
            self.add_item(self.paused_button)

        self.add_item(self.previous_track_button)
        self.add_item(self.skip_button)
        self.add_item(self.shuffle_button)

        self.add_item(self.stop_button)

        if player is None:
            self.show_history_button.disabled = True
            self.repeat_button_off.disabled = True
            self.decrease_volume_button.disabled = True
            self.increase_volume_button.disabled = True

            self.resume_button.disabled = True
            self.previous_track_button.disabled = True
            self.skip_button.disabled = True
            self.shuffle_button.disabled = True

            self.stop_button.disabled = True
            return

        if player.queue.empty():
            self.shuffle_button.disabled = True
        if not player.current:
            self.stop_button.disabled = True

        if player.history.empty():
            self.previous_track_button.disabled = True
            self.show_history_button.disabled = True

    async def get_player(self) -> Player | None:
        if (player := self.cog.pylav.get_player(self.guild.id)) is None:
            config = self.cog.pylav.player_config_manager.get_config(self.guild.id)
            if (channel := self.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(self.channel, "author.voice.channel", None)
                if not channel:
                    await self.channel.send(
                        embed=await self.cog.pylav.construct_embed(
                            messageable=self.channel,
                            description=_("You must be in a voice channel to allow me to connect."),
                        ),
                        delete_after=10,
                    )
                    return
            if not ((permission := channel.permissions_for(self.guild.me)) and permission.connect and permission.speak):
                await self.channel.send(
                    embed=await self.cog.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=self.channel,
                    ),
                    delete_after=10,
                )
                return
            player = await self.cog.pylav.player_manager.create(channel=channel, self_deaf=True)
        return player

    async def get_now_playing_embed(self, forced: bool = False) -> discord.Embed:
        await asyncio.sleep(1)
        player = self.cog.pylav.get_player(self.guild.id)
        if player is None or player.current is None or forced:
            return await self.cog.pylav.construct_embed(
                description=_("I am not currently playing anything on this server."),
                messageable=self.channel,
            )
        return await player.get_currently_playing_message(embed=True, messageable=self.channel)

    @synchronized_method_call_with_self_threading_lock()
    async def update_view(self, forced: bool = False):
        await self.prepare()
        embed = await self.get_now_playing_embed(forced)
        await self.message.edit(view=self, embed=embed)
