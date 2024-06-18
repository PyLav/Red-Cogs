from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from functools import partial
from pathlib import Path

import aiohttp
import discord
from apscheduler.job import Job
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_list, inline
from tabulate import tabulate

from pylav.compat import json
from pylav.constants.misc import EQ_BAND_MAPPING
from pylav.core.client import Client
from pylav.core.context import PyLavContext
from pylav.events.node import NodeChangedEvent, NodeConnectedEvent, NodeDisconnectedEvent, WebSocketClosedEvent
from pylav.events.player import (
    FiltersAppliedEvent,
    PlayerAutoDisconnectedAloneEvent,
    PlayerAutoDisconnectedEmptyQueueEvent,
    PlayerAutoPausedEvent,
    PlayerAutoResumedEvent,
    PlayerConnectedEvent,
    PlayerDisconnectedEvent,
    PlayerMovedEvent,
    PlayerPausedEvent,
    PlayerRepeatEvent,
    PlayerRestoredEvent,
    PlayerResumedEvent,
    PlayerStoppedEvent,
    PlayerVolumeChangedEvent,
)
from pylav.events.plugins import SegmentSkippedEvent
from pylav.events.queue import QueueEndEvent, QueueShuffledEvent, QueueTracksAddedEvent, QueueTracksRemovedEvent
from pylav.events.track import (
    TrackAutoPlayEvent,
    TrackEndEvent,
    TrackExceptionEvent,
    TrackPreviousRequestedEvent,
    TrackResumedEvent,
    TrackSeekEvent,
    TrackSkippedEvent,
    TrackStuckEvent,
)
from pylav.events.track.track_start import (
    TrackStartAppleMusicEvent,
    TrackStartBandcampEvent,
    TrackStartDeezerEvent,
    TrackStartEvent,
    TrackStartFloweryTTSEvent,
    TrackStartGCTTSEvent,
    TrackStartGetYarnEvent,
    TrackStartHTTPEvent,
    TrackStartLocalFileEvent,
    TrackStartMixCloudEvent,
    TrackStartNicoNicoEvent,
    TrackStartPornHubEvent,
    TrackStartSoundCloudEvent,
    TrackStartSoundgasmEvent,
    TrackStartSpeakEvent,
    TrackStartSpotifyEvent,
    TrackStartTwitchEvent,
    TrackStartVimeoEvent,
    TrackStartYouTubeEvent,
    TrackStartYouTubeMusicEvent,
)
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import format_time_dd_hh_mm_ss
from pylav.logging import getLogger
from pylav.players.filters import Equalizer, Volume
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

_ = Translator("PyLavNotifier", Path(__file__))

LOGGER = getLogger("PyLav.cog.Notifier")


@cog_i18n(_)
class PyLavNotifier(DISCORD_COG_TYPE_MIXIN):
    """Listen to events from the PyLav player and send them as messages to the specified channel"""

    lavalink: Client

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(
            notify_channel_id=None,
            node_connected=dict(enabled=True, mention=True),
            node_disconnected=dict(enabled=True, mention=True),
        )
        self._config.register_guild(
            track_stuck=dict(enabled=True, mention=True),
            track_exception=dict(enabled=True, mention=True),
            track_end=dict(enabled=True, mention=True),
            track_start=dict(enabled=False, mention=True),
            track_start_youtube_music=dict(enabled=True, mention=True),
            track_start_spotify=dict(enabled=True, mention=True),
            track_start_apple_music=dict(enabled=True, mention=True),
            track_start_deezer=dict(enabled=True, mention=True),
            track_start_localfile=dict(enabled=True, mention=True),
            track_start_http=dict(enabled=True, mention=True),
            track_start_speak=dict(enabled=True, mention=True),
            track_start_youtube=dict(enabled=True, mention=True),
            track_start_clypit=dict(enabled=True, mention=True),
            track_start_getyarn=dict(enabled=True, mention=True),
            track_start_mixcloud=dict(enabled=True, mention=True),
            track_start_ocrmix=dict(enabled=True, mention=True),
            track_start_pornhub=dict(enabled=True, mention=True),
            track_start_reddit=dict(enabled=True, mention=True),
            track_start_soundgasm=dict(enabled=True, mention=True),
            track_start_tiktok=dict(enabled=True, mention=True),
            track_start_bandcamp=dict(enabled=True, mention=True),
            track_start_soundcloud=dict(enabled=True, mention=True),
            track_start_twitch=dict(enabled=True, mention=True),
            track_start_vimeo=dict(enabled=True, mention=True),
            track_start_gctts=dict(enabled=True, mention=True),
            track_start_flowery_tts=dict(enabled=True, mention=True),
            track_start_niconico=dict(enabled=True, mention=True),
            track_skipped=dict(enabled=True, mention=True),
            track_seek=dict(enabled=True, mention=True),
            track_replaced=dict(enabled=True, mention=True),
            track_previous_requested=dict(enabled=True, mention=True),
            tracks_requested=dict(enabled=True, mention=True),
            track_autoplay=dict(enabled=True, mention=True),
            track_resumed=dict(enabled=True, mention=True),
            queue_shuffled=dict(enabled=True, mention=True),
            queue_end=dict(enabled=True, mention=True),
            queue_track_position_changed=dict(enabled=True, mention=True),
            queue_tracks_removed=dict(enabled=True, mention=True),
            player_paused=dict(enabled=True, mention=True),
            player_stopped=dict(enabled=True, mention=True),
            player_resumed=dict(enabled=True, mention=True),
            player_moved=dict(enabled=True, mention=True),
            player_disconnected=dict(enabled=True, mention=True),
            player_connected=dict(enabled=True, mention=True),
            volume_changed=dict(enabled=True, mention=True),
            player_repeat=dict(enabled=True, mention=True),
            player_restored=dict(enabled=True, mention=True),
            segment_skipped=dict(enabled=True, mention=True),
            segments_loaded=dict(enabled=False, mention=True),
            filters_applied=dict(enabled=True, mention=True),
            node_connected=dict(enabled=False, mention=True),
            node_disconnected=dict(enabled=False, mention=True),
            node_changed=dict(enabled=False, mention=True),
            websocket_closed=dict(enabled=False, mention=True),
            player_auto_paused=dict(enabled=True, mention=True),
            player_auto_resumed=dict(enabled=True, mention=True),
            player_auto_disconnected=dict(enabled=True, mention=True),
            player_auto_disconnected_empty_queue=dict(enabled=True, mention=True),
            webhook_url=None,
            webhook_channel_id=None,
        )
        self._message_queue: dict[discord.TextChannel | discord.VoiceChannel | discord.Thread, list[discord.Embed]] = (
            defaultdict(list)
        )
        self._scheduled_jobs: list[Job] = []
        self._webhook_cache: dict[int, discord.Webhook] = {}
        self._session = aiohttp.ClientSession(json_serialize=json.dumps, auto_decompress=False)

    async def initialize(self, *args, **kwargs) -> None:
        for guild_id, guild_data in (await self._config.all_guilds()).items():
            if url := guild_data.get("webhook_url"):
                self._webhook_cache[guild_id] = discord.Webhook.from_url(url=url, session=self._session)
        self._scheduled_jobs.append(
            self.pylav.scheduler.add_job(
                self.chunk_embed_task,
                trigger="interval",
                seconds=10,
                max_instances=1,
                replace_existing=True,
                coalesce=True,
            )
        )

    async def cog_unload(self) -> None:
        for job in self._scheduled_jobs:
            job.remove()
        if not self._session.closed:
            await self._session.close()

    async def chunk_embed_task(self) -> None:
        await asyncio.gather(
            *[
                self.send_embed_batch(channel=channel, embed_list=embed_list)
                for channel, embed_list in self._message_queue.items()
                if embed_list
            ]
        )

    async def send_embed_batch(
        self, channel: discord.TextChannel | discord.VoiceChannel | discord.Thread, embed_list: list[discord.Embed]
    ) -> None:
        if not embed_list:
            return
        LOGGER.trace("Starting MPNotifier schedule message dispatcher for %s", channel)

        if channel.guild.id in self._webhook_cache and self._webhook_cache[channel.guild.id].channel_id == channel.id:
            send = partial(
                self._webhook_cache[channel.guild.id].send,
                thread=channel if isinstance(channel, discord.Thread) else discord.utils.MISSING,
            )
        else:
            send = channel.send

        embeds = embed_list[:10]
        if not embeds:
            return
        self._message_queue[channel] = embed_list[10:]
        dispatch_mapping = {send: embeds}
        if not dispatch_mapping:
            LOGGER.trace("No embeds to dispatch")
            return

        LOGGER.trace("Sending up to last 10 embeds to %s channels", len(dispatch_mapping))

        await asyncio.gather(
            *[send(embeds=embeds) for send, embeds in dispatch_mapping.items()], return_exceptions=True
        )

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="plnotifier")
    async def command_plnotify(self, context: PyLavContext):
        """Configure the PyLavNotifier cog"""

    @command_plnotify.command(name="version")
    async def command_plnotify_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and PyLav"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (EightBitANSI.paint_white(self.__class__.__name__), EightBitANSI.paint_blue(self.__version__)),
            (EightBitANSI.paint_white("PyLav"), EightBitANSI.paint_blue(context.pylav.lib_version)),
        ]

        await context.send(
            embed=await context.pylav.construct_embed(
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Library / Cog"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Version"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plnotify.command(name="webhook")
    async def command_plnotify_webhook(
        self,
        context: PyLavContext,
        channel: discord.TextChannel | discord.VoiceChannel | discord.Thread,
        use_thread: bool = True,
    ) -> None:  # sourcery skip: low-code-quality
        """Set the notify channel for the player"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not isinstance(channel, discord.Thread):
            if not channel.permissions_for(context.guild.me).manage_webhooks:
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to manage webhooks in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            if use_thread and not (
                (permission := channel.permissions_for(context.guild.me)).create_public_threads
                and permission.send_messages_in_threads
            ):
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to create a thread in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            webhook = await channel.create_webhook(
                name=_("PyLavNotifier"),
                reason=_("PyLav Notifier - Requested by {author_variable_do_not_translate}.").format(
                    author_variable_do_not_translate=context.author
                ),
            )
            if not use_thread:
                existing_thread = None
                if isinstance(channel, discord.VoiceChannel):
                    existing_thread = channel
                else:
                    for thread in channel.guild.threads:
                        if thread.parent.id == channel.id and thread.name.startswith("PyLavNotifier"):
                            existing_thread = thread
                if not existing_thread:
                    message = await channel.send(
                        _("This thread will be used by PyLav to post notifications about the player.")
                    )
                    existing_thread = await channel.create_thread(
                        invitable=False,
                        name=_("PyLavNotifier"),
                        message=message,
                        auto_archive_duration=10080,
                        reason=_("PyLav Notifier - Requested by {author_variable_do_not_translate}.").format(
                            author_variable_do_not_translate=context.author
                        ),
                    )
            else:
                existing_thread = channel
            channel = existing_thread
            if old_url := await self._config.guild(context.guild).webhook_url():
                with contextlib.suppress(discord.HTTPException):
                    await discord.Webhook.from_url(url=old_url, session=self._session).delete(
                        reason=_("A new webhook was being created.")
                    )

            await self._config.guild(context.guild).webhook_url.set(webhook.url)
            await self._config.guild(context.guild).webhook_channel_id.set(channel.id)
            self._webhook_cache[context.guild.id] = webhook
        else:
            existing_webhook_url = await self._config.guild(context.guild).webhook_url()
            existing_webhook_channel_id = await self._config.guild(context.guild).webhook_channel_id()
            webhook = (
                discord.Webhook.from_url(url=existing_webhook_url, session=self._session)
                if channel.id == existing_webhook_channel_id
                else None
            )
            if not webhook:
                if not channel.parent.permissions_for(context.guild.me).manage_webhooks:
                    await context.send(
                        embed=await self.pylav.construct_embed(
                            description=_(
                                "I do not have permission to manage webhooks in {channel_variable_do_not_translate}."
                            ).format(channel_variable_do_not_translate=channel.parent.mention),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )
                    return
                webhook_channel = channel.parent
                webhook = await webhook_channel.create_webhook(
                    name=_("PyLavNotifier"),
                    reason=_("PyLav Notifier - Requested by {author_variable_do_not_translate}.").format(
                        author_variable_do_not_translate=context.author
                    ),
                )
                if existing_webhook_url:
                    with contextlib.suppress(discord.HTTPException):
                        await discord.Webhook.from_url(url=existing_webhook_url, session=self._session).delete(
                            reason=_("A new webhook was being created.")
                        )
                await self._config.guild(context.guild).webhook_url.set(webhook.url)
                await self._config.guild(context.guild).webhook_channel_id.set(webhook_channel.id)
        self._webhook_cache[context.guild.id] = webhook
        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
        await config.update_notify_channel_id(channel.id if channel else 0)
        if await self.bot.is_owner(context.author):
            await self._config.notify_channel_id.set(channel.id)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("PyLavNotifier channel set to {channel_variable_do_not_translate}.").format(
                    channel_variable_do_not_translate=channel.mention
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plnotify.command(name="event")
    async def command_plnotify_event(
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
        possible_events = self.pylav.dispatch_manager.simple_event_names()

        if event not in possible_events:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Invalid event, possible events are:\n\n{events_variable_do_not_translate}.").format(
                        events_variable_do_not_translate=humanize_list(
                            sorted(list(map(inline, possible_events)), key=str.lower)
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await self._config.guild(guild=context.guild).set_raw(event, value={"enabled": toggle, "mention": use_mention})
        if event in {
            "node_connected",
            "node_disconnected",
        } and await self.bot.is_owner(context.author):
            await self._config.set_raw(event, value={"enabled": toggle, "mention": use_mention})

        await context.send(
            embed=await context.pylav.construct_embed(
                description=_(
                    "Event {event_variable_do_not_translate} set to {toggle_variable_do_not_translate}{extras_variable_do_not_translate}."
                ).format(
                    event_variable_do_not_translate=inline(event),
                    toggle_variable_do_not_translate=_("notify") if toggle else _("do not notify"),
                    extras_variable_do_not_translate=(
                        _(" with mentions") if use_mention and toggle else _(" without mentions") if toggle else ""
                    ),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_pylav_track_stuck_event(self, event: TrackStuckEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Stuck Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} is stuck for {threshold_variable_do_not_translate} seconds, skipping."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    threshold_variable_do_not_translate=event.threshold // 1000,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_exception_event(self, event: TrackExceptionEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_exception", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return

        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Exception Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] There was an error while playing {track_variable_do_not_translate}:\n{exception_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    exception_variable_do_not_translate=event.exception,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_end_event(self, event: TrackEndEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_end", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        match event.reason:
            case "finished":
                message = _(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has finished playing because the player reached the end of the tracks runtime."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.node.name,
                )
            case "replaced":
                message = _(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has finished playing because a new track started playing."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.node.name,
                )
            case "loadFailed":
                message = _(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has finished playing because it failed to start."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.node.name,
                )
            case "stopped":
                message = _(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has finished playing because the player was stopped."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.node.name,
                )
            case __:
                message = _(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has finished playing because the node told it to stop."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.node.name,
                )

        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track End Event"),
                description=message,
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start(self, event: TrackStartEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start", default={"enabled": False, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Track: {track_variable_do_not_translate} has "
                    "started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube_music_event(self, event: TrackStartYouTubeMusicEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_youtube_music", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("YouTube Music Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] YouTube Music track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_deezer_event(self, event: TrackStartDeezerEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_deezer", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Deezer Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Deezer track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_spotify_event(self, event: TrackStartSpotifyEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_spotify", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Spotify Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Spotify track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_apple_music_event(self, event: TrackStartAppleMusicEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_apple_music", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Apple Music Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Apple Music track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_localfile_event(self, event: TrackStartLocalFileEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_localfile", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Local Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Local track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_http_event(self, event: TrackStartHTTPEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_http", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("HTTP Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] HTTP track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_speak_event(self, event: TrackStartSpeakEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_speak", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Text-To-Speech Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Text-To-Speech track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube_event(self, event: TrackStartYouTubeEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_youtube", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("YouTube Track Start Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] YouTube track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_clypit_event(self, event: TrackStartGetYarnEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_clypit", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_getyarn_event(self, event: TrackStartGetYarnEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_getyarn", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_mixcloud_event(self, event: TrackStartMixCloudEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_mixcloud", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_ocrmix_event(self, event: TrackStartMixCloudEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_ocrmix", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_pornhub_event(self, event: TrackStartPornHubEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_pornhub", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    source_variable_do_not_translate=await event.track.query_source(),
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_reddit_event(self, event: TrackStartPornHubEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_reddit", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundgasm_event(self, event: TrackStartSoundgasmEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_soundgasm", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_tiktok_event(self, event: TrackStartSoundgasmEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_tiktok", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_bandcamp_event(self, event: TrackStartBandcampEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_bandcamp", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundcloud_event(self, event: TrackStartSoundCloudEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_soundcloud", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_twitch_event(self, event: TrackStartTwitchEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_twitch", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_vimeo_event(self, event: TrackStartVimeoEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_vimeo", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_gctts_event(self, event: TrackStartGCTTSEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_gctts", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_flowery_tts_event(self, event: TrackStartFloweryTTSEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_flowery_tts", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_niconico_event(self, event: TrackStartNicoNicoEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_niconico", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("{source_variable_do_not_translate} Track Start Event").format(
                    source_variable_do_not_translate=await event.track.query_source()
                ),
                description=_(
                    "[Node={node_variable_do_not_translate}] {source_variable_do_not_translate} track: {track_variable_do_not_translate} has started playing.\nRequested by: {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.node.name,
                    source_variable_do_not_translate=await event.track.query_source(),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_skipped_event(self, event: TrackSkippedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_skipped", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Skipped Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {track_variable_do_not_translate} has been skipped.\nRequested by {requester_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_seek_event(self, event: TrackSeekEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_seek", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Seek Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} requested that {track_variable_do_not_translate} "
                    "is sought from position {from_variable_do_not_translate} to position {after_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    from_variable_do_not_translate=format_time_dd_hh_mm_ss(event.before),
                    after_variable_do_not_translate=format_time_dd_hh_mm_ss(event.after),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_previous_requested_event(self, event: TrackPreviousRequestedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "previous_requested", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Previous Requested Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} requested that the previous track {track_variable_do_not_translate} be played"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_tracks_added_event(self, event: QueueTracksAddedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "tracks_requested", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Tracks Requested Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} added {track_count_variable_do_not_translate} to the queue."
                ).format(
                    track_count_variable_do_not_translate=(
                        _("{count_variable_do_not_translate} track").format(count_variable_do_not_translate=count)
                        if (count := len(event.tracks)) > 1
                        else await event.tracks[0].get_track_display_name(with_url=True)
                    ),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_auto_play_event(self, event: TrackAutoPlayEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_autoplay", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track AutoPlay Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Auto playing {track_variable_do_not_translate}."
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_resumed_event(self, event: TrackResumedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_resumed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Track Resumed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} resumed {track_variable_do_not_translate}"
                ).format(
                    track_variable_do_not_translate=await event.track.get_track_display_name(with_url=True),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_shuffled_event(self, event: QueueShuffledEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "queue_shuffled", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Queue Shuffled Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} shuffled the queue"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_end_event(self, event: QueueEndEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "queue_end", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Queue End Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] All tracks in the queue have been played"
                ).format(node_variable_do_not_translate=event.player.node.name),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_tracks_removed_event(self, event: QueueTracksRemovedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "queue_tracks_removed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Tracks Removed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} removed {track_count_variable_do_not_translate} tracks from the queue"
                ).format(
                    track_count_variable_do_not_translate=len(event.tracks),
                    requester_variable_do_not_translate=user,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_paused_event(self, event: PlayerPausedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_paused", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Paused Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} paused the player"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_stopped_event(self, event: PlayerStoppedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_stopped", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Stopped Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} stopped the player"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_resumed_event(self, event: PlayerResumedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_resumed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Resumed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} resumed the player"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_moved_event(self, event: PlayerMovedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_moved", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Moved Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} moved the player from {before_variable_do_not_translate} to {after_variable_do_not_translate}"
                ).format(
                    requester_variable_do_not_translate=user,
                    before_variable_do_not_translate=event.before,
                    after_variable_do_not_translate=event.after,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_disconnected_event(self, event: PlayerDisconnectedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_disconnected", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Disconnected Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} disconnected the player"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_connected_event(self, event: PlayerConnectedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_connected", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Connected Event"),
                description=_("[Node={node}] {requester} connected the player").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_volume_changed_event(self, event: PlayerVolumeChangedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "volume_changed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Volume Changed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} changed the player volume from {before_variable_do_not_translate} to {after_variable_do_not_translate}."
                ).format(
                    requester_variable_do_not_translate=user,
                    before_variable_do_not_translate=event.before,
                    after_variable_do_not_translate=event.after,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_repeat_event(self, event: PlayerRepeatEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_repeat", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user

        if event.type == "disable":
            self._message_queue[channel].append(
                await self.pylav.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_(
                        "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} disabled repeat"
                    ).format(
                        requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                    ),
                    messageable=channel,
                )
            )
        elif event.type == "queue":
            self._message_queue[channel].append(
                await self.pylav.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_(
                        "{requester_variable_do_not_translate} {status_variable_do_not_translate} repeat of the whole queue"
                    ).format(
                        requester_variable_do_not_translate=user,
                        status_variable_do_not_translate=_("enabled") if event.queue_after else _("disabled"),
                    ),
                    messageable=channel,
                )
            )
        else:
            self._message_queue[channel].append(
                await self.pylav.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_(
                        "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} {status_variable_do_not_translate} repeat for {track_variable_do_not_translate}"
                    ).format(
                        requester_variable_do_not_translate=user,
                        status_variable_do_not_translate=_("enabled") if event.current_after else _("disabled"),
                        track_variable_do_not_translate=await event.player.current.get_track_display_name(
                            with_url=True
                        ),
                        node_variable_do_not_translate=event.player.node.name,
                    ),
                    messageable=channel,
                )
            )

    @commands.Cog.listener()
    async def on_pylav_player_restored_event(self, event: PlayerRestoredEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_restored", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Restored Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} restored the player"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_segment_skipped_event(self, event: SegmentSkippedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "segment_skipped", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        segment = event.segment

        if segment.category == "intro":
            explanation = _("an intro section")
        elif segment.category == "outro":
            explanation = _("an outro section")
        elif segment.category == "preview":
            explanation = _("a preview section")
        elif segment.category == "music_offtopic":
            explanation = _("an off-topic section")
        elif segment.category == "filler":
            explanation = _("a filler section")
        elif segment.category == "sponsor":
            explanation = _("a sponsor section")
        elif segment.category == "selfpromo":
            explanation = _("a self-promotion section")
        else:
            explanation = _("an interaction section")

        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Sponsor Segment Skipped Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] Sponsorblock: Skipped {category_variable_do_not_translate} running from {start_variable_do_not_translate}s to {to_variable_do_not_translate}s"
                ).format(
                    category_variable_do_not_translate=explanation,
                    start_variable_do_not_translate=int(segment.start) // 1000,
                    to_variable_do_not_translate=int(segment.end) // 1000,
                    node_variable_do_not_translate=event.player.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_filters_applied_event(self, event: FiltersAppliedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "filters_applied", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        t_effect = EightBitANSI.paint_yellow(_("Effect"), bold=True, underline=True)
        default = _("Not changed")
        t_values = EightBitANSI.paint_yellow(_("Values"), bold=True, underline=True)
        data = []
        for effect in (
            event.volume,
            event.equalizer,
            event.karaoke,
            event.timescale,
            event.tremolo,
            event.vibrato,
            event.rotation,
            event.distortion,
            event.low_pass,
            event.channel_mix,
            event.pluginFilters.echo,
            event.pluginFilters.reverb,
        ):
            if not effect or isinstance(effect, Volume):
                continue

            data_ = {t_effect: effect.__class__.__name__}
            values = effect.to_dict()
            if not isinstance(effect, Equalizer):
                data_[t_values] = "\n".join(
                    f"{EightBitANSI.paint_white(k.title())}: {EightBitANSI.paint_green(v or default)}"
                    for k, v in values.items()
                )
            else:
                values = values["equalizer"]
                data_[t_values] = "\n".join(
                    [
                        "{band}: {gain}".format(
                            band=EightBitANSI.paint_white(EQ_BAND_MAPPING[band["band"]]),
                            gain=EightBitANSI.paint_green(band["gain"]),
                        )
                        for band in values
                        if band["gain"]
                    ]
                )
            data.append(data_)
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Filters Applied Event"),
                description="{translation1}\n\n__**{translation2}:**__"
                "\n{data}".format(
                    data=box(tabulate(data, headers="keys", tablefmt="fancy_grid"), lang="ansi") if data else _("None"),
                    translation2=discord.utils.escape_markdown(_("Currently Applied")),
                    translation1=discord.utils.escape_markdown(
                        _(
                            "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} changed the player filters"
                        ).format(
                            requester_variable_do_not_translate=user, node_variable_do_not_translate=event.node.name
                        )
                    ),
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_node_connected_event(self, event: NodeConnectedEvent) -> None:
        data = await self._config.get_raw("node_connected", default={"enabled": True, "mention": True})
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                await self.pylav.set_context_locale(notify_channel.guild)
                self._message_queue[notify_channel].append(
                    await self.pylav.construct_embed(
                        title=_("Node Connected Event"),
                        description=_("Node {name_variable_do_not_translate} has been connected").format(
                            name_variable_do_not_translate=inline(event.node.name)
                        ),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_disconnected_event(self, event: NodeDisconnectedEvent) -> None:
        data = await self._config.get_raw("node_disconnected", default={"enabled": True, "mention": True})
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                await self.pylav.set_context_locale(notify_channel.guild)
                self._message_queue[notify_channel].append(
                    await self.pylav.construct_embed(
                        title=_("Node Disconnected Event"),
                        description=_(
                            "Node {name_variable_do_not_translate} has been disconnected with code {code_variable_do_not_translate} and reason: {reason_variable_do_not_translate}"
                        ).format(
                            name_variable_do_not_translate=inline(event.node.name),
                            code_variable_do_not_translate=event.code,
                            reason_variable_do_not_translate=event.reason,
                        ),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_changed_event(self, event: NodeChangedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "node_changed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Node Changed Event"),
                description=_(
                    "The node which the player is connected to changed from {from_variable_do_not_translate} to {to_variable_do_not_translate}"
                ).format(
                    from_variable_do_not_translate=event.old_node.name, to_variable_do_not_translate=event.new_node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_web_socket_closed_event(self, event: WebSocketClosedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "websocket_closed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("WebSocket Closed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] The Lavalink websocket connection to Discord closed with"
                    " code {code_variable_do_not_translate} and reason {reason_variable_do_not_translate}"
                ).format(
                    code_variable_do_not_translate=event.code,
                    reason_variable_do_not_translate=event.reason,
                    node_variable_do_not_translate=event.node.name,
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_auto_paused_event(self, event: PlayerAutoPausedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_auto_paused", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Paused Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} automatically paused the player due to configured values"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_auto_resumed_event(self, event: PlayerAutoResumedEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_auto_resumed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Player Resumed Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} automatically resumed the player due to configured values"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_auto_disconnected_alone_event(self, event: PlayerAutoDisconnectedAloneEvent) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "player_auto_disconnected_alone", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Auto Player Disconnected Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} automatically disconnected the player as there is no one listening"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_auto_disconnected_empty_queue_event(
        self, event: PlayerAutoDisconnectedEmptyQueueEvent
    ) -> None:
        player = event.player
        await self.pylav.set_context_locale(player.guild)
        channel = await player.notify_channel()
        if channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "auto_disconnected_empty_queue", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        self._message_queue[channel].append(
            await self.pylav.construct_embed(
                title=_("Auto Player Disconnected Event"),
                description=_(
                    "[Node={node_variable_do_not_translate}] {requester_variable_do_not_translate} automatically disconnected the player as the queue is empty"
                ).format(
                    requester_variable_do_not_translate=user, node_variable_do_not_translate=event.player.node.name
                ),
                messageable=channel,
            )
        )
