from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, Literal

import discord
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.antispam import AntiSpam
from redbot.core.utils.chat_formatting import humanize_number

from plcontroller.view import PersistentControllerView
from pylav import logging
from pylav.core.context import PyLavContext
from pylav.events.queue import QueueEndEvent
from pylav.events.track import TrackEndEvent, TrackExceptionEvent, TrackStartEvent
from pylav.players.player import Player
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

_ = Translator("PyLavController", Path(__file__))

LOGGER = logging.getLogger("PyLav.cog.Controller")


@cog_i18n(_)
class PyLavController(
    DISCORD_COG_TYPE_MIXIN,
):
    """Set a channel to listens and control the music player."""

    __version__ = "1.0.0rc1"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_guild(
            channel=None,
            list_for_requests=False,
            list_for_searches=False,
            persistent_view_message_id=None,
            enable_antispam=True,
        )
        self._channel_cache: dict[int, int] = {}
        self._list_for_search_cache: dict[int, bool] = {}
        self._list_for_command_cache: dict[int, bool] = {}
        self._enable_antispam_cache: dict[int, bool] = {}
        self._view_cache: dict[int, PersistentControllerView] = {}
        intervals = [
            (timedelta(seconds=15), 1),
            (timedelta(minutes=1), 3),
            (timedelta(hours=1), 30),
        ]

        self.antispam: dict[int, dict[int, AntiSpam]] = defaultdict(lambda: defaultdict(partial(AntiSpam, intervals)))

    async def cog_unload(self) -> None:
        for view in self._view_cache.values():
            view.stop()
        self._view_cache.clear()

    async def initialize(self):
        await self.bot.wait_until_red_ready()

        guild_data = await self._config.all_guilds()

        for guild_id, data in guild_data.items():
            if channel_id := data["channel"]:
                self._channel_cache[guild_id] = channel_id
            self._list_for_command_cache[guild_id] = data["list_for_requests"]
            self._list_for_search_cache[guild_id] = data["list_for_searches"]
            self._enable_antispam_cache[guild_id] = data["enable_antispam"]
            if data["persistent_view_message_id"]:
                if channel := self.bot.get_channel(channel_id):
                    await self.prepare_channel(channel)

    @commands.group(name="plcontrollerset")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def command_plcontrollerset(self, context: PyLavContext):
        """Configure the PyLav Controller."""

    @command_plcontrollerset.command(name="channel")
    async def command_plcontrollerset_channel(
        self, context: PyLavContext, channel: discord.TextChannel | discord.Thread | discord.VoiceChannel
    ):
        """Set the channel to create the controller in."""
        channel_permissions = channel.permissions_for(context.guild.me)
        if not channel_permissions.send_messages:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I need 'Send Messages' permission in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if not channel_permissions.read_messages:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I need 'Read Messages' permission in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if not channel_permissions.embed_links:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I need 'Embed Links' permission in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if not channel_permissions.manage_messages:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I need 'Manage Messages' permission in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        await self._config.guild(context.guild).channel.set(channel.id)
        self._channel_cache[context.guild.id] = channel.id

        await context.send(
            embed=await context.construct_embed(
                description=_(
                    "I will now use {channel_name_variable_do_not_translate} for the controller functionality."
                ).format(channel_name_variable_do_not_translate=channel.mention),
                messageable=context,
            ),
            ephemeral=True,
        )

        await self.prepare_channel(channel)

    @command_plcontrollerset.command(name="acceptrequests", aliases=["ar", "listen"])
    async def command_plcontrollerset_acceptrequests(self, context: PyLavContext):
        """Toggle whether the controller should listen for requests."""
        current = await self._config.guild(context.guild).list_for_requests()
        await self._config.guild(context.guild).list_for_requests.set(not current)
        self._list_for_command_cache[context.guild.id] = not current

        if not current:
            await context.send(
                embed=await context.construct_embed(
                    description=_("From now on, I will accept user requests in the controller channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_("From now on, I will ignore user requests in the controller channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plcontrollerset.command(name="acceptsearches", aliases=["as", "search"])
    async def command_plcontrollerset_acceptsearches(self, context: PyLavContext):
        """Toggle whether the controller should listen for searches."""
        current = await self._config.guild(context.guild).list_for_searches()
        await self._config.guild(context.guild).list_for_searches.set(not current)
        self._list_for_search_cache[context.guild.id] = not current
        channel_id = self._channel_cache[context.guild.id]
        if channel := self.bot.get_channel(channel_id):
            if not current:
                self._view_cache[channel.id].enable_show_help()
            else:
                self._view_cache[channel.id].disable_show_help()

        if not current:
            await context.send(
                embed=await context.construct_embed(
                    description=_("From now on, I will accept user searches in the controller channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_("From now on, I will ignore user searches in the controller channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plcontrollerset.command(name="antispam", aliases=["spam"])
    async def command_plcontrollerset_antispam(self, context: PyLavContext):
        """Toggle whether the controller enable the antispam check."""
        current = await self._config.guild(context.guild).enable_antispam()
        await self._config.guild(context.guild).enable_antispam.set(not current)
        self._enable_antispam_cache[context.guild.id] = not current

        if not current:
            await context.send(
                embed=await context.construct_embed(
                    description=_("From now on, I will check user request against the antispam to avoid abuse."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "From now on, I will no longer check user request against the antispam to avoid abuse."
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )

    async def volume(self, context: PyLavContext, change_by: int):
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not connected to a voice channel."), messageable=context
                ),
                ephemeral=True,
            )
            return
        max_volume = await self.pylav.player_config_manager.get_max_volume(context.guild.id)
        new_vol = context.player.volume + change_by
        if new_vol > max_volume:
            await context.player.set_volume(max_volume, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "Volume limit reached, player volume set to {volume_variable_do_not_translate}%."
                    ).format(volume_variable_do_not_translate=humanize_number(context.player.volume)),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif new_vol < 0:
            await context.player.set_volume(0, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Minimum volume reached, player volume set to 0%."), messageable=context
                ),
                ephemeral=True,
            )
        else:
            await context.player.set_volume(new_vol, requester=context.author)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Player volume set to {volume_variable_do_not_translate}%").format(
                        volume_variable_do_not_translate=new_vol
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )

    async def repeat(self, context: PyLavContext, queue: bool | None = None):
        """Set whether to repeat the current song or queue.

        If no argument is given, the current repeat mode will be toggled between the current track and off.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if queue:
            await context.player.set_repeat("queue", True, context.author)
            msg = _("From now on, I will now repeat the entire queue.")
        elif await context.player.is_repeating():
            await context.player.set_repeat("disable", False, context.author)
            msg = _("From now on, I will no longer repeat any tracks.")
        else:
            await context.player.set_repeat("current", True, context.author)
            if context.player.current:
                msg = _("From now on, I will now repeat {track_name_variable_do_not_translate}.").format(
                    track_name_variable_do_not_translate=await context.player.current.get_track_display_name(
                        with_url=True
                    )
                )
            else:
                msg = _("From now on, I will now repeat the current track.")
        await context.send(
            embed=await context.pylav.construct_embed(description=msg, messageable=context), ephemeral=True
        )

    async def shuffle(self, context: PyLavContext):
        """Shuffles the current queue."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if context.player.queue.empty():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The server queue is currently empty."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if (await self.pylav.player_config_manager.get_shuffle(context.guild.id)) is False:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You are not allowed to shuffle the queue."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.shuffle_queue(context.author.id)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("{queue_size_variable_do_not_translate} tracks shuffled.").format(
                    queue_size_variable_do_not_translate=context.player.queue.size()
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    async def skip(self, context: PyLavContext):
        """Skips the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player or (not context.player.current and not context.player.autoplay_enabled):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have skipped {track_name_variable_do_not_translate} as requested.").format(
                        track_name_variable_do_not_translate=await context.player.current.get_track_display_name(
                            with_url=True
                        )
                    ),
                    thumbnail=await context.player.current.artworkUrl(),
                    messageable=context,
                ),
                ephemeral=True,
            )
        await context.player.skip(requester=context.author)

    async def resume(self, context: PyLavContext):
        """Resume the player"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if not context.player.paused:
            description = _("The player already resumed")
            await context.send(
                embed=await context.pylav.construct_embed(description=description, messageable=context),
                ephemeral=True,
            )
            return

        await context.player.set_pause(False, context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have now resumed the player as requested."), messageable=context
            ),
            ephemeral=True,
        )

    async def pause(self, context: PyLavContext):
        """Pause the player"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if context.player.paused:
            description = _("The player is already paused.")
            await context.send(
                embed=await context.pylav.construct_embed(description=description, messageable=context),
                ephemeral=True,
            )
            return

        await context.player.set_pause(True, requester=context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have now paused the player as requested."), messageable=context
            ),
            ephemeral=True,
        )

    async def stop(self, context: PyLavContext):
        """Stops the player and clears the queue."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player or not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.stop(context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have stopped the playback and cleared the queue as requested."), messageable=context
            ),
            ephemeral=True,
        )

    async def previous(self, context: PyLavContext):
        """Play previously played tracks.

        A history of the last 100 tracks played is kept.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if context.player.history.empty():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The history of tracks is currently empty."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.previous(requester=context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Playing previous track: {track_name_variable_do_not_translate}.").format(
                    track_name_variable_do_not_translate=await context.player.current.get_track_display_name(
                        with_url=True
                    )
                ),
                thumbnail=await context.player.current.artworkUrl(),
                messageable=context,
            ),
            ephemeral=True,
        )

    async def prepare_channel(self, channel: discord.TextChannel | discord.Thread | discord.VoiceChannel):
        existing_view_id = await self._config.guild(channel.guild).persistent_view_message_id()
        if existing_view_id:
            with contextlib.suppress(discord.NotFound):
                existing_view = await channel.fetch_message(existing_view_id)
                self._view_cache[channel.id] = PersistentControllerView(
                    cog=self, channel=channel, message=existing_view
                )
                await self._view_cache[channel.id].prepare()
                if channel.guild.id in self._list_for_search_cache and self._list_for_search_cache[channel.guild.id]:
                    self._view_cache[channel.id].enable_show_help()
                self.bot.add_view(self._view_cache[channel.id], message_id=existing_view_id)
                return
        self._view_cache[channel.id] = PersistentControllerView(cog=self, channel=channel)
        await self._view_cache[channel.id].prepare()
        if channel.guild.id in self._list_for_search_cache and self._list_for_search_cache[channel.guild.id]:
            self._view_cache[channel.id].enable_show_help()
        message = await self.send_channel_view(channel)
        await self._config.guild(channel.guild).persistent_view_message_id.set(message.id)
        self._view_cache[channel.id].set_message(message)
        self.bot.add_view(self._view_cache[channel.id], message_id=message.id)

    async def send_channel_view(
        self, channel: discord.TextChannel | discord.Thread | discord.VoiceChannel
    ) -> discord.Message:
        return await channel.send(
            embed=await self._view_cache[channel.id].get_now_playing_embed(), view=self._view_cache[channel.id]
        )

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        guild = message.guild
        if guild is None:
            return

        if message.author.bot:
            return

        if guild.id not in self._channel_cache:
            return

        if message.channel.id != self._channel_cache[guild.id]:
            return

        channel = self.bot.get_channel(self._channel_cache[guild.id])
        if channel is None:
            return

        if channel.id not in self._view_cache:
            return

        if await self.bot.cog_disabled_in_guild(self, guild):
            return

        player = await self._view_cache[channel.id].get_player()
        if player is None:
            return

        await self.process_potential_query(message, player)

    async def process_potential_query(self, message: discord.Message, player: Player):
        if (message.guild.id not in self._list_for_command_cache) or (
            self._list_for_command_cache[message.guild.id] is False
        ):
            await message.delete(delay=1)
            return

        if message.guild.id in self._enable_antispam_cache and self._enable_antispam_cache[message.guild.id]:
            if self.antispam[message.guild.id][message.author.id].spammy:
                await message.delete(delay=1)
                return
            self.antispam[message.guild.id][message.author.id].stamp()

        query = await Query.from_string(
            message.clean_content, dont_search=not self._list_for_search_cache[message.guild.id]
        )
        if query.invalid:
            await message.add_reaction("\N{CROSS MARK}")
            await message.delete(delay=5)
            return
        if query.is_search and not self._list_for_search_cache[message.guild.id]:
            await message.add_reaction("\N{CROSS MARK}")
            await message.delete(delay=5)
            return

        await message.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            query, player=player, requester=message.author
        )
        if successful:
            if query.is_search:
                successful = [successful[0]]
            await player.bulk_add(tracks_and_queries=successful, requester=message.author.id)
            if (not player.is_playing) and player.queue.size() > 0:
                await player.next(requester=message.author)
            delay = 10
        else:
            await message.clear_reactions()
            await message.add_reaction("\N{CROSS MARK}")
            delay = 5

        await message.delete(delay=delay)

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        await self._config.user_from_id(user_id).clear()

    @commands.Cog.listener()
    async def on_pylav_track_start_event(self, event: TrackStartEvent) -> None:
        await self.process_event(event)

    @commands.Cog.listener()
    async def on_pylav_queue_end_event(self, event: QueueEndEvent) -> None:
        await self.process_event(event)

    async def process_event(self, event: TrackStartEvent | TrackEndEvent | TrackExceptionEvent):
        await asyncio.sleep(1)
        if event.player.guild.id not in self._channel_cache:
            return
        channel = self.bot.get_channel(self._channel_cache[event.player.guild.id])
        if channel is None:
            return
        if await self.bot.cog_disabled_in_guild(self, channel.guild):
            return
        if channel.id not in self._view_cache:
            return
        await self._view_cache[channel.id].update_view()
