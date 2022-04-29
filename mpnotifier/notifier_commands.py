from pathlib import Path
from typing import Union

import discord
from redbot.core import Config, commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_list, inline

from pylav import Client
from pylav.types import BotT
from pylav.utils import PyLavContext

_ = Translator("MPNotifier", Path(__file__))

POSSIBLE_EVENTS = {
    "track_stuck",
    "track_exception",
    "track_end",
    "track_start_youtube_music",
    "track_start_spotify",
    "track_start_apple_music",
    "track_start_localfile",
    "track_start_http",
    "track_start_speak",
    "track_start_youtube",
    "track_start_clypit",
    "track_start_getyarn",
    "track_start_mixcloud",
    "track_start_ocrmix",
    "track_start_pornhub",
    "track_start_reddit",
    "track_start_soundgasm",
    "track_start_tiktok",
    "track_start_bandcamp",
    "track_start_soundcloud",
    "track_start_twitch",
    "track_start_vimeo",
    "track_start_gctts",
    "track_start_niconico",
    "track_start",
    "track_skipped",
    "track_seek",
    "track_replaced",
    "track_previous_requested",
    "tracks_requested",
    "track_autoplay",
    "track_resumed",
    "queue_shuffled",
    "queue_end",
    "queue_track_position_changed",
    "queue_tracks_removed",
    "player_update",
    "player_paused",
    "player_stopped",
    "player_resumed",
    "player_moved",
    "player_disconnected",
    "player_connected",
    "volume_changed",
    "player_repeat",
    "player_restored",
    "segment_skipped",
    "segments_loaded",
    "filters_applied",
    "node_connected",
    "node_disconnected",
    "node_changed",
    "websocket_closed",
}


class Commands:
    bot: BotT
    lavalink: Client
    _config = Config

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="notifyset")
    async def command_notifyset(self, context: PyLavContext):
        """Configure the MPNotifier cog."""

    @command_notifyset.command(name="channel")
    async def command_notifyset_channel(
        self, context: PyLavContext, *, channel: Union[discord.Thread, discord.TextChannel]
    ) -> None:
        """Set the notify channel for the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if context.player:
            config = context.player.config
            context.player.notify_channel = channel
        else:
            config = self.lavalink.player_config_manager.get_config(context.guild.id)
        config.notify_channel = channel.id
        await config.save()
        if await self.bot.is_owner(context.author):
            await self._config.notify_channel_id.set(channel.id)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("MP notify channel set to {channel}").format(channel=channel.mention), messageable=context
            ),
            ephemeral=True,
        )

    @command_notifyset.command(name="event")
    async def command_notifyset_event(
        self, context: PyLavContext, event: str, toggle: bool, use_mention: bool = False
    ) -> None:
        """Set whether or not to notify for the specified event.

        Arguments:
            event -- The event to set.
            toggle -- Whether or not to notify upon receiving this event.
            use_mention -- Whether or not to use a mention instead of the name for the action requested.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        event = event.lower()
        if event not in POSSIBLE_EVENTS:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Invalid event, possible events are:\n\n{events}.").format(
                        events=humanize_list(list(POSSIBLE_EVENTS))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await self._config.guild(guild=context.guild).set_raw(event, value=[toggle, use_mention])  # type: ignore
        if event in ["node_connected", "node_disconnected"] and await self.bot.is_owner(context.author):
            await self._config.set_raw({event: [toggle, use_mention]})

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Event {event} set to {toggle}{extras}.").format(
                    event=inline(event),
                    toggle=_("notify") if toggle else _("do not notify"),
                    extras=_(" with mentions") if use_mention and toggle else _(" without mentions") if toggle else "",
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
