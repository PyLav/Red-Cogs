import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Union

import aiohttp
import discord
import ujson
from apscheduler.job import Job
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_list, inline
from tabulate import tabulate

import pylavcogs_shared
from pylav import events
from pylav.filters import Equalizer, Volume
from pylav.types import BotT
from pylav.utils import PyLavContext, format_time

_ = Translator("PyLavNotifier", Path(__file__))

LOGGER = getLogger("red.3pt.PyLavNotifier")

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


@cog_i18n(_)
class PyLavNotifier(commands.Cog):
    """Listen to events from the PyLav player and sent them as messages to the specified channel."""

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
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
            track_start_youtube_music=dict(enabled=True, mention=True),
            track_start_spotify=dict(enabled=True, mention=True),
            track_start_apple_music=dict(enabled=True, mention=True),
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
            webhook_url=None,
        )
        self._message_queue: dict[
            Union[discord.TextChannel, discord.VoiceChannel, discord.Thread], list[discord.Embed]
        ] = defaultdict(list)
        self._scheduled_jobs: list[Job] = []
        self._webhook_cache: dict[int, discord.Webhook] = {}
        self._session = aiohttp.ClientSession(json_serialize=ujson.dumps, auto_decompress=False)

    async def initialize(self, *args, **kwargs) -> None:
        for guild_id, guild_data in (await self._config.all_guilds()).items():
            if url := guild_data.get("webhook_url"):
                self._webhook_cache[guild_id] = discord.Webhook.from_url(url=url, session=self._session)
        self._scheduled_jobs.append(
            self.lavalink.scheduler.add_job(
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
        self, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread], embed_list: list[discord.Embed]
    ) -> None:
        if not embed_list:
            return
        LOGGER.trace("Starting MPNotifier schedule message dispatcher for %s.", channel)

        if channel.guild.id in self._webhook_cache and self._webhook_cache[channel.guild.id].channel_id == channel.id:
            send = self._webhook_cache[channel.guild.id].send
        else:
            send = channel.send

        embeds = embed_list[:10]
        if not embeds:
            return
        self._message_queue[channel] = embed_list[10:]
        dispatch_mapping = {send: embeds}
        if not dispatch_mapping:
            LOGGER.trace("No embeds to dispatch.")
            return

        LOGGER.trace("Sending up to last 10 embeds to %s channels", len(dispatch_mapping))

        await asyncio.gather(*[send(embeds=embeds) for send, embeds in dispatch_mapping.items()])

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="plnotifier")
    async def command_plnotify(self, context: PyLavContext):
        """Configure the PyLavNotifier cog."""

    @command_plnotify.command(name="version")
    async def command_plnotify_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and it's PyLav dependencies."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (self.__class__.__name__, self.__version__),
            ("PyLavCogs-Shared", pylavcogs_shared.__VERSION__),
            ("PyLav", self.bot.lavalink.lib_version),
        ]

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=box(tabulate(data, headers=(_("Library/Cog"), _("Version")), tablefmt="fancy_grid")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plnotify.command(name="webhook")
    async def command_plnotify_webhook(
        self, context: PyLavContext, *, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]
    ) -> None:
        """Set the notify channel for the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not isinstance(channel, discord.Thread):
            if not channel.permissions_for(context.guild.me).manage_webhooks:
                await context.send(
                    embed=await self.lavalink.construct_embed(
                        description=_("I do not have permission to manage webhooks in {channel}.").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            webhook = await channel.create_webhook(
                name=_("PyLavNotifier"),
                reason=_("PyLav Notifier - Requested by {author}").format(author=context.author),
            )
            await self._config.webhook_url.set(webhook.url)
            self._webhook_cache[context.guild.id] = webhook
        if context.player:
            config = context.player.config
            context.player.notify_channel = channel
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        config.notify_channel = channel.id
        await config.save()
        if await self.bot.is_owner(context.author):
            await self._config.notify_channel_id.set(channel.id)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLavNotifier channel set to {channel}").format(channel=channel.mention),
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
        if event not in POSSIBLE_EVENTS:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Invalid event, possible events are:\n\n{events}.").format(
                        events=humanize_list(sorted(list(map(inline, POSSIBLE_EVENTS)), key=str.lower))
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

    @commands.Cog.listener()
    async def on_pylav_track_stuck(self, event: events.TrackStuckEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Stuck Event"),
                description=_("[Node={node}] {track} is stuck for {threshold} seconds, skipping.").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    threshold=event.threshold // 1000,
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_exception(self, event: events.TrackExceptionEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_exception", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return

        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Exception Event"),
                description=_("[Node={node}] There was an error while playing {track}:\n{exception}").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    exception=event.exception,
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_end(self, event: events.TrackEndEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_end", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if event.reason == "FINISHED":
            reason = _("the player reached the end of the tracks runtime.")
        elif event.reason == "REPLACED":
            reason = _("a new track started playing.")
        elif event.reason == "LOAD_FAILED":
            reason = _("it failed to start.")
        elif event.reason == "STOPPED":
            reason = _("because the player was stopped.")
        else:  # CLEANUP
            reason = _("the node told it to stop.")
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track End Event"),
                description=_("[Node={node}] {track} has finished playing because {reason}").format(
                    track=await event.track.get_track_display_name(with_url=True), reason=reason, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube_music(self, event: events.TrackStartYouTubeMusicEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("YouTube Music Track Start Event"),
                description=_(
                    "[Node={node}] YouTube Music track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_spotify(self, event: events.TrackStartSpotifyEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Spotify Track Start Event"),
                description=_(
                    "[Node={node}] Spotify track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_apple_music(self, event: events.TrackStartAppleMusicEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Apple Music Track Start Event"),
                description=_(
                    "[Node={node}] Apple Music track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_localfile(self, event: events.TrackStartLocalFileEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Local Track Start Event"),
                description=_(
                    "[Node={node}] Local track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_http(self, event: events.TrackStartHTTPEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("HTTP Track Start Event"),
                description=_(
                    "[Node={node}] HTTP track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_speak(self, event: events.TrackStartSpeakEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Text-To-Speech Track Start Event"),
                description=_(
                    "[Node={node}] Text-To-Speech track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube(self, event: events.TrackStartYouTubeEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("YouTube Track Start Event"),
                description=_(
                    "[Node={node}] YouTube track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_clypit(self, event: events.TrackStartGetYarnEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_getyarn(self, event: events.TrackStartGetYarnEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_mixcloud(self, event: events.TrackStartMixCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_ocrmix(self, event: events.TrackStartMixCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_pornhub(self, event: events.TrackStartPornHubEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_reddit(self, event: events.TrackStartPornHubEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundgasm(self, event: events.TrackStartSoundgasmEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_tiktok(self, event: events.TrackStartSoundgasmEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_bandcamp(self, event: events.TrackStartBandcampEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundcloud(self, event: events.TrackStartSoundCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_twitch(self, event: events.TrackStartTwitchEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_vimeo(self, event: events.TrackStartVimeoEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_gctts(self, event: events.TrackStartGCTTSEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_niconicoo(self, event: events.TrackStartNicoNicoEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("{source} Track Start Event").format(source=await event.track.query_source()),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_skipped(self, event: events.TrackSkippedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Skipped Event"),
                description=_("[Node={node}] {track} has been skipped.\nRequested by {requester}").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_seek(self, event: events.TrackSeekEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Seek Event"),
                description=_(
                    "[Node={node}] {requester} requested that {track} "
                    "is sought from position {fro} to position {after}."
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    fro=format_time(event.before),
                    after=format_time(event.after),
                    requester=user,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def pylav_track_previous_requested(self, event: events.TrackPreviousRequestedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Previous Requested Event"),
                description=_("[Node={node}] {requester} requested that the previous track {track} be played.").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_tracks_requested(self, event: events.TracksRequestedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Tracks Requested Event"),
                description=_("[Node={node}] {requester} added {track_count}  to the queue.").format(
                    track_count=_("{count} track").format(count=count)
                    if (count := len(event.tracks)) > 1
                    else await event.tracks[0].get_track_display_name(with_url=True),
                    requester=user,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_autoplay(self, event: events.TrackAutoPlayEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "track_autoplay", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track AutoPlay Event"),
                description=_("[Node={node}] Auto-playing {track}.").format(
                    track=await event.track.get_track_display_name(with_url=True), node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_resumed(self, event: events.TrackResumedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Track Resumed Event"),
                description=_("[Node={node}] {requester} resumed {track}.").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_shuffled(self, event: events.QueueShuffledEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Queue Shuffled Event"),
                description=_("[Node={node}] {requester} shuffled the queue.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_end(self, event: events.QueueEndEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "queue_end", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Queue End Event"),
                description=_("[Node={node}] All tracks in the queue have been played.").format(
                    node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_tracks_removed(self, event: events.QueueTracksRemovedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Tracks Removed Event"),
                description=_("[Node={node}] {requester} removed {track_count} tracks from the queue.").format(
                    track_count=len(event.tracks), requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_paused(self, event: events.PlayerPausedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Paused Event"),
                description=_("[Node={node}] {requester} paused the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_stopped(self, event: events.PlayerStoppedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Stopped Event"),
                description=_("[Node={node}] {requester} stopped the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_resumed(self, event: events.PlayerResumedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Resumed Event"),
                description=_("[Node={node}] {requester} resumed the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_moved(self, event: events.PlayerMovedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Moved Event"),
                description=_("[Node={node}] {requester} moved the player from {before} to {after}.").format(
                    requester=user, before=event.before, after=event.after, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_disconnected(self, event: events.PlayerDisconnectedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Disconnected Event"),
                description=_("[Node={node}] {requester} disconnected the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_connected(self, event: events.PlayerConnectedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Connected Event"),
                description=_("[Node={node}] {requester} connected the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_volume_changed(self, event: events.PlayerVolumeChangedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Volume Changed Event"),
                description=_("[Node={node}] {requester} changed the player's volume from {before} to {after}.").format(
                    requester=user, before=event.before, after=event.after, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_repeat(self, event: events.PlayerRepeatEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
            self._message_queue[player.notify_channel].append(
                await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("[Node={node}] {requester} disabled repeat.").format(
                        requester=user, node=event.player.node.name
                    ),
                    messageable=player.notify_channel,
                )
            )
        elif event.type == "queue":
            self._message_queue[player.notify_channel].append(
                await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("{requester} {status} repeat of the whole queue.").format(
                        requester=user, status=_("enabled") if event.queue_after else _("disabled")
                    ),
                    messageable=player.notify_channel,
                )
            )
        else:
            self._message_queue[player.notify_channel].append(
                await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("[Node={node}] {requester} {status} repeat for {track}.").format(
                        requester=user,
                        status=_("enabled") if event.current_after else _("disabled"),
                        track=await event.player.current.get_track_display_name(with_url=True),
                        node=event.player.node.name,
                    ),
                    messageable=player.notify_channel,
                )
            )

    @commands.Cog.listener()
    async def on_pylav_player_restored(self, event: events.PlayerRestoredEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Player Restored Event"),
                description=_("[Node={node}] {requester} restored the player.").format(
                    requester=user, node=event.player.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_segment_skipped(self, event: events.SegmentSkippedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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

        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Sponsor Segment Skipped Event"),
                description=_("[Node={node}] Sponsorblock: Skipped {category} running from {start}s to {to}s.").format(
                    category=explanation,
                    start=segment.start // 1000,
                    to=segment.end // 1000,
                    node=event.player.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_filters_applied(self, event: events.FiltersAppliedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
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
        t_effect = _("Effect")
        t_values = _("Values")
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
        ):
            if not effect or isinstance(effect, Volume):
                continue

            data_ = {t_effect: effect.__class__.__name__}
            if effect.changed:
                values = effect.to_dict()
                values.pop("off")
                if not isinstance(effect, Equalizer):
                    data_[t_values] = "\n".join(f"{k.title()}: {v}" for k, v in values.items())
                else:
                    values = values["equalizer"]
                    data_[t_values] = "\n".join(
                        [f"Band {band['band']}: {band['gain']}" for band in values if band["gain"]]
                    )
            else:
                data_[t_values] = _("N/A")
            data.append(data_)
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Filters Applied Event"),
                description=_(
                    "[Node={node}] {requester} changed the player filters.\n\n" "__**Currently Applied:**__" "\n{data}"
                ).format(
                    requester=user,
                    data=box(tabulate(data, headers="keys", tablefmt="fancy_grid")) if data else _("None"),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_node_connected(self, event: events.NodeConnectedEvent) -> None:
        data = await self._config.get_raw("node_connected", default={"enabled": True, "mention": True})
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                self._message_queue[notify_channel].append(
                    await self.lavalink.construct_embed(
                        title=_("Node Connected Event"),
                        description=_("Node {name} has been connected.").format(name=inline(event.node.name)),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_disconnected(self, event: events.NodeDisconnectedEvent) -> None:
        data = await self._config.get_raw("node_disconnected", default={"enabled": True, "mention": True})
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                self._message_queue[notify_channel].append(
                    await self.lavalink.construct_embed(
                        title=_("Node Disconnected Event"),
                        description=_(
                            "Node {name} has been disconnected with code {code} and reason: {reason}."
                        ).format(name=inline(event.node.name), code=event.code, reason=event.reason),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_changed(self, event: events.NodeChangedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "node_changed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("Node Changed Event"),
                description=_("The node which the player is connected to changed from {fro} to {to}.").format(
                    fro=event.old_node.name, to=event.new_node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_websocket_closed(self, event: events.WebSocketClosedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        data = await self._config.guild(guild=event.player.guild).get_raw(
            "websocket_closed", default={"enabled": True, "mention": True}
        )
        notify, mention = data["enabled"], data["mention"]
        if not notify:
            return
        self._message_queue[player.notify_channel].append(
            await self.lavalink.construct_embed(
                title=_("WebSocket Closed Event"),
                description=_(
                    "[Node={node}] The websocket connection to the Lavalink node closed with"
                    " code {code} and reason {reason}."
                ).format(code=event.code, reason=event.reason, node=event.node.name),
                messageable=player.notify_channel,
            )
        )
