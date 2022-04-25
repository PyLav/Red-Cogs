from __future__ import annotations

import asyncio
import itertools
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import discord
from discord import Emoji, PartialEmoji
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav.sql.models import PlaylistModel
from pylav.utils import AsyncIter

from audio.cog._types import CogT
from audio.cog.menus.modals import PlaylistSaveModal
from audio.cog.menus.selectors import PlaylistPlaySelector
from audio.cog.menus.sources import Base64Source
from audio.cog.utils import rgetattr

if TYPE_CHECKING:
    from audio.cog.menus.menus import PlaylistCreationFlow, PlaylistManageFlow

LOGGER = getLogger("red.3pt.mp.ui.buttons")

_ = Translator("MediaPlayer", Path(__file__))


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
            emoji=discord.PartialEmoji(name="previous", id=965672202424950795, animated=False),
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
            emoji=discord.PartialEmoji(name="stop", id=965672202563362926, animated=False),
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
            emoji=discord.PartialEmoji(name="pause", id=965672202466910268, animated=False),
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
            emoji=discord.PartialEmoji(name="play", id=965672202441723994, animated=False),
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
            emoji=discord.PartialEmoji(name="next", id=965672202416570428, animated=False),
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
            emoji=discord.PartialEmoji(name="volumeup", id=965672202517225492, animated=False),
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
            emoji=discord.PartialEmoji(name="volumedown", id=965672202399801374, animated=False),
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
            emoji=discord.PartialEmoji(name="loop", id=965672202143928362, animated=False),
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
        if player.repeat_current:
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
            emoji=discord.PartialEmoji(name="repeat", id=965672202412388352, animated=False),
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
        if player.repeat_current:
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
            emoji=discord.PartialEmoji(name="random", id=965672202458509463, animated=False),
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
            emoji=discord.PartialEmoji(name="minimize", animated=False, id=965672202424963142),
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
            emoji=discord.PartialEmoji(name="equalizer", animated=False, id=965672202454323250),
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
            emoji=discord.PartialEmoji(name="power", animated=False, id=965672202395586691),
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
            emoji=discord.PartialEmoji(name="plus", animated=False, id=965672202416570368),
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
            emoji=discord.PartialEmoji(name="minus", animated=False, id=965672202013925447),
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
            emoji=discord.PartialEmoji(name="musicalnote", animated=False, id=965674278144077824),
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


class SaveQueuePlaylistButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="playlist", animated=False, id=961593964790689793),
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        modal = PlaylistSaveModal(self.cog, self, _("What should the playlist name be?"))
        await interaction.response.send_modal(modal)


class EnqueuePlaylistButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
        emoji: Emoji | PartialEmoji = discord.PartialEmoji(name="playlist", animated=False, id=965672202093621319),
        playlist: PlaylistModel = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.playlist = playlist

    async def callback(self, interaction: discord.Interaction):
        from audio.cog.menus.menus import PlaylistPickerMenu
        from audio.cog.menus.sources import PlaylistPickerSource

        if not self.playlist:
            playlists = await self.cog.lavalink.playlist_db_manager.get_all_for_user(
                requester=interaction.user.id,
                vc=rgetattr(interaction.user, "voice.channel", None),
                guild=interaction.guild,
                channel=interaction.channel,  # type: ignore
            )
            playlists = list(itertools.chain.from_iterable(playlists))
            await PlaylistPickerMenu(
                cog=self.cog,
                bot=self.cog.bot,
                selector_cls=PlaylistPlaySelector,
                source=PlaylistPickerSource(
                    guild_id=interaction.guild.id,
                    cog=self.cog,
                    pages=playlists,
                    message_str=_("Playlists you can currently play"),
                ),
                delete_after_timeout=True,
                clear_buttons_after=True,
                starting_page=0,
                original_author=interaction.user,
                selector_text=_("Pick a playlist"),
            ).start(interaction)
        else:
            await self.cog.command_playlist_play.callback(self.cog, interaction, playlist=[self.playlist])  # type: ignore
        if hasattr(self.view, "prepare"):
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
            emoji=discord.PartialEmoji(name="settings", animated=False, id=961593964316729394),
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
            emoji=discord.PartialEmoji(name="power", animated=False, id=961593964354482256),
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
            emoji=discord.PartialEmoji(name="stop", id=961593964828459068, animated=False),
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
            emoji=discord.PartialEmoji(name="power", animated=False, id=961593964354482256),
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


class PlaylistUpsertButton(discord.ui.Button):
    view: PlaylistCreationFlow | PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        op: Literal["url", "name", "scope", "add", "remove"],
        label: str = None,
        emoji: str | Emoji | PartialEmoji = None,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            label=label,
            row=row,
        )
        self.cog = cog
        self.op = op

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        if self.op == "url":
            await self.view.prompt_url(interaction)
        elif self.op == "name":
            await self.view.prompt_name(interaction)
        elif self.op == "scope":
            await self.view.prompt_scope(interaction)
        elif self.op == "add":
            await self.view.prompt_add_tracks(interaction)
        elif self.op == "remove":
            await self.view.prompt_remove_tracks(interaction)


class DoneButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="check", animated=False, id=967466875535626260),
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


class PlaylistDeleteButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="trash", animated=False, id=967752655017484318),
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
        self.view.cancelled = False
        self.view.delete = not self.view.delete
        if self.view.delete:
            response = _("When you press done this playlist will be permanently delete...")
        else:
            response = _("This playlist will no longer be deleted once you press done...")

        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistClearButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="clear", animated=False, id=967756040521252924),
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
        self.view.cancelled = False
        self.view.clear = not self.view.clear
        if self.view.clear:
            response = _("Clearing all tracks from the playlist playlist...")
        else:
            response = _("No longer clearing tracks from the playlist...")

        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistDownloadButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
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

        async with self.view.playlist.to_yaml(guild=interaction.guild) as yaml_file:
            yaml_file: BytesIO
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction,
                    description=_("Here is your playlist: {name}{extras}").format(
                        name=await self.view.playlist.get_name_formatted(with_url=True),
                        extras=_(
                            "\n (compressed using gzip to make it possible to send via Discord "
                            "- you can use <https://gzip.swimburger.net/> to decompress it)"
                        ),
                    ),
                ),
                file=discord.File(filename=f"{self.view.playlist.name}.yaml", fp=yaml_file),
                ephemeral=True,
            )


class PlaylistUpdateButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=discord.PartialEmoji(name="update", animated=False, id=967810735851860059),
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
        self.view.cancelled = False
        self.view.update = not self.view.update
        if (self.view.playlist.url or self.view.url) and self.view.update:
            response = _("Updating playlist with the latest tracks...")
        else:
            self.view.update = False
            response = _("Not updating playlist...")
        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistInfoButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        playlist: PlaylistModel,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog
        self.playlist = playlist

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        from audio.cog.menus.menus import PaginatingMenu

        await PaginatingMenu(
            bot=self.cog.bot,
            cog=self.cog,
            source=Base64Source(
                guild_id=interaction.guild.id,
                cog=self.cog,
                author=interaction.user,
                entries=self.view.playlist.tracks,
                playlist=self.playlist,
            ),
            delete_after_timeout=True,
            starting_page=0,
            original_author=interaction.user,
        ).start(await self.cog.bot.get_context(interaction))


class PlaylistQueueButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
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
        self.view.queue = not self.view.queue
        if self.view.queue:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Adding the current queue to playlist...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No longer adding the current queue to playlist...")
                ),
                ephemeral=True,
            )


class PlaylistDedupeButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
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
        self.view.dedupe = not self.view.dedupe
        if self.view.dedupe:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Removing all duplicate tracks from the queue...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No longer all duplicate tracks from the queue...")
                ),
                ephemeral=True,
            )
