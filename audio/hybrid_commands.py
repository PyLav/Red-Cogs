from __future__ import annotations

import re
from pathlib import Path
from re import Pattern
from typing import Final

import discord
from discord import app_commands
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav.core.context import PyLavContext
from pylav.extension.red.ui.menus.queue import QueueMenu
from pylav.extension.red.ui.sources.queue import QueueSource
from pylav.extension.red.utils import rgetattr
from pylav.extension.red.utils.decorators import invoker_is_dj, requires_player
from pylav.extension.red.utils.validators import valid_query_attachment
from pylav.helpers.format.strings import format_time_dd_hh_mm_ss, shorten_string
from pylav.logging import getLogger
from pylav.nodes.api.responses.track import Track as TrackResponse
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Player.commands.hybrids")
_ = Translator("PyLavPlayer", Path(__file__))
# taken from https://github.com/Cog-Creators/Red-DiscordBot/blob/ec55622418810731e1ee2ede1569f81f9bddeeec/redbot/cogs/audio/core/utilities/miscellaneous.py#L28
_RE_TIME_CONVERTER: Final[Pattern] = re.compile(r"(?:(\d+):)?(\d+):(\d+)")
# The above was updated to allow for any `(\d+)?\d+:\d+` combination to include unusual time formats such as `1:75`


class HybridCommands(DISCORD_COG_TYPE_MIXIN):
    @commands.hybrid_command(
        name="play",
        description=shorten_string(max_length=100, string=_("Enqueue the specified query to be played.")),
        aliases=["p"],
    )
    @app_commands.describe(
        query=shorten_string(max_length=100, string=_("This argument is the query to play, a link or a search query."))
    )
    @commands.guild_only()
    @invoker_is_dj()
    async def command_play(self, context: PyLavContext, *, query: str = None):  # sourcery skip: low-code-quality
        """Attempt to play the queries which you provide.

        Separate multiple queries with a new line (`shift + enter`).

        If you want to play a local track, you can specify the full path relative to the local tracks' folder.
        For example, if my local tracks folder is: `/home/draper/music`.

        I can play a single track with `track.mp3` or `/home/draper/music/track.mp3`.
        I can play everything inside a folder with a `sub-folder/folder`.
        I can play everything inside a folder and its sub-folders with the `all:` prefix, i.e. `all:sub-folder/folder`.

        You can search specific services by using the following prefixes*:
        `dzsearch:`  - Deezer
        `spsearch:`  - Spotify
        `amsearch:`  - Apple Music
        `ytmsearch:` - YouTube Music
        `ytsearch:`  - YouTube
        `scsearch:`  - SoundCloud
        `ymsearch:`  - Yandex Music

        You can trigger text-to-speech by using the following prefixes*:
        `speak:` - I will speak the query (limited to 200 characters)
        `tts://` - I will speak the query
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if query is None:
            if attachments := context.message.attachments:
                query = "\n".join(
                    attachment.url for attachment in attachments if valid_query_attachment(attachment.filename)
                )
        if not query:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("You need to give me a query to enqueue."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        player = self.pylav.get_player(context.guild.id)
        if player is None:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(context.author, "voice.channel", None)
                if not channel:
                    await context.send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel, so I can connect to it."),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_name_variable_do_not_translate}."
                        ).format(channel_name_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=context.author)
        if isinstance(query, (Track, TrackResponse)):
            track = await Track.build_track(
                node=player.node,
                data=query,
                requester=context.author.id,
                query=None,
                player_instance=player,
            )
            if track is None:
                return
            await player.add(track=track, requester=context.author.id)
            if not (player.is_active or player.queue.empty()):
                await player.next(requester=context.author)
            await self._process_play_message(context, track, 1)
            return
        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        total_tracks_enqueue = 0
        single_track = None
        if queries:
            single_track, total_tracks_enqueue = await self._process_play_queries(
                context, queries, player, single_track, total_tracks_enqueue
            )
        if not (player.is_active or player.queue.empty()):
            await player.next(requester=context.author)

        await self._process_play_message(context, single_track, total_tracks_enqueue)

    async def _process_play_message(self, context, single_track, total_tracks_enqueue):
        artwork = None
        match total_tracks_enqueue:
            case 1:
                description = _("{track_name_variable_do_not_translate} enqueued.").format(
                    track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True)
                )
                artwork = await single_track.artworkUrl()
            case 0:
                description = _("No tracks were found for your query.")
            case __:
                description = _("{number_of_tracks_variable_do_not_translate} tracks enqueued.").format(
                    number_of_tracks_variable_do_not_translate=total_tracks_enqueue
                )
        await context.send(
            embed=await self.pylav.construct_embed(
                description=description,
                thumbnail=artwork,
                messageable=context,
            ),
            ephemeral=True,
        )

    async def _process_play_queries(self, context, queries, player, single_track, total_tracks_enqueue):
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            *queries, requester=context.author, player=player
        )
        if successful:
            single_track = successful[0]
        total_tracks_enqueue += count
        if count:
            if count == 1:
                await player.add(requester=context.author.id, track=successful[0])
            else:
                await player.bulk_add(requester=context.author.id, tracks_and_queries=successful)
        return single_track, total_tracks_enqueue

    @staticmethod
    async def _process_play_search_queries(context, player, search_queries, single_track, total_tracks_enqueue):
        total_tracks_from_search = 0
        for query in search_queries:
            single_track = track = await Track.build_track(
                node=player.node, data=None, query=query, requester=context.author.id, player_instance=player
            )
            if track is None:
                continue
            await player.add(requester=context.author.id, track=track)
            if not player.is_active:
                await player.next(requester=context.author)
            total_tracks_enqueue += 1
            total_tracks_from_search += 1
        return single_track, total_tracks_enqueue

    @commands.hybrid_command(
        name="connect",
        description=shorten_string(
            max_length=100, string=_("Request that I connect to the specified channel or your current channel.")
        ),
    )
    @app_commands.describe(channel=shorten_string(max_length=100, string=_("The voice channel to connect to.")))
    @commands.guild_only()
    @invoker_is_dj()
    async def command_connect(self, context: PyLavContext, *, channel: discord.VoiceChannel | None = None):
        """Request that I connect to the specified channel or your current channel."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        config = self.pylav.player_config_manager.get_config(context.guild.id)
        if (channel_ := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
            actual_channel = channel or rgetattr(context, "author.voice.channel", None)
            if not actual_channel:
                await context.send(
                    embed=await context.pylav.construct_embed(
                        description=_(
                            "You need to be in a voice channel if you do not specify which channel I should connect to."
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        else:
            actual_channel = channel_
        if not ((permission := actual_channel.permissions_for(context.me)) and permission.connect and permission.speak):
            if permission.connect:
                description = _(
                    "I do not have permission to connect to {channel_name_variable_do_not_translate}."
                ).format(channel_name_variable_do_not_translate=actual_channel.mention)
            else:
                description = _(
                    "I do not have permission to speak in {channel_name_variable_do_not_translate}."
                ).format(channel_name_variable_do_not_translate=actual_channel.mention)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=description,
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if not (
            (permission := actual_channel.permissions_for(context.author))
            and permission.connect
            and permission.view_channel
        ):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "You do not have permission to connect to {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=actual_channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if (player := context.player) is None:
            player = await context.pylav.connect_player(context.author, channel=actual_channel)
        else:
            await player.move_to(context.author, channel=actual_channel)

        if (vc := await player.forced_vc()) and channel != actual_channel:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "I have been told only to join {channel_name_variable_do_not_translate} on this server."
                    ).format(channel_name_variable_do_not_translate=vc.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have successfully connected to {channel_name_variable_do_not_translate}.").format(
                        channel_name_variable_do_not_translate=player.channel.mention
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="np",
        description=shorten_string(
            max_length=100, string=_("Shows which track is currently being played on this server.")
        ),
        aliases=["now"],
    )
    @commands.guild_only()
    @requires_player()
    async def command_now(self, context: PyLavContext):
        """Shows which track is currently being played on this server."""
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
        current_embed = await context.player.get_currently_playing_message(messageable=context)
        await context.send(embed=current_embed, ephemeral=True)

    @commands.hybrid_command(
        name="skip",
        description=shorten_string(max_length=100, string=_("Skips the current track.")),
    )
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_skip(self, context: PyLavContext):
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

    @commands.hybrid_command(
        name="stop",
        description=shorten_string(max_length=100, string=_("Stops the player and clears the queue.")),
    )
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_stop(self, context: PyLavContext):
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

    @commands.hybrid_command(
        name="dc",
        description=shorten_string(
            max_length=100, string=_("Request that I disconnect from the current voice channel.")
        ),
        aliases=["disconnect"],
    )
    @requires_player()
    @invoker_is_dj()
    async def command_disconnect(self, context: PyLavContext):
        """Request that I disconnect from the current voice channel."""
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
        channel = context.player.channel
        await context.player.disconnect(requester=context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have disconnected from {channel_name_variable_do_not_translate} as requested.").format(
                    channel_name_variable_do_not_translate=channel.mention
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="queue",
        description=shorten_string(max_length=100, string=_("Shows the current queue for this server.")),
        aliases=["q"],
    )
    @commands.guild_only()
    @requires_player()
    async def command_queue(self, context: PyLavContext):
        """Shows the current queue for this server."""
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
        await QueueMenu(
            cog=self,
            bot=self.bot,
            source=QueueSource(guild_id=context.guild.id, cog=self),
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(ctx=context)

    @commands.hybrid_command(
        name="shuffle", description=shorten_string(max_length=100, string=_("Shuffles the current queue."))
    )
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_shuffle(self, context: PyLavContext):
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

    @commands.hybrid_command(
        name="repeat",
        description=shorten_string(max_length=100, string=_("Set whether to repeat the current song or queue.")),
    )
    @app_commands.describe(queue=shorten_string(max_length=100, string=_("Should the whole queue be repeated?")))
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_repeat(self, context: PyLavContext, queue: bool | None = None):
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

    @commands.hybrid_command(name="pause", description=shorten_string(max_length=100, string=_("Pause the player")))
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_pause(self, context: PyLavContext):
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
            description = _(
                "The player is already paused, did you mean to run {command_name_variable_do_not_translate}."
            ).format(
                command_name_variable_do_not_translate=f"`{'/' if context.interaction else context.clean_prefix}{self.command_resume.qualified_name}`",
            )
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

    @commands.hybrid_command(name="resume", description=shorten_string(max_length=100, string=_("Resume the player")))
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_resume(self, context: PyLavContext):
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
            description = _(
                "The player already resumed, did you mean to run {command_name_variable_do_not_translate}."
            ).format(
                command_name_variable_do_not_translate=f"`{'/' if context.interaction else context.clean_prefix}{self.command_pause.qualified_name}`",
            )
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

    @commands.hybrid_command(name="volume", description=_("Set the current volume for the player."))
    @app_commands.describe(volume=_("The volume to set"))
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_volume(self, context: PyLavContext, volume: int):
        """Set the current volume for the player.

        The volume is a percentage value between 0% and 1,000%, where 100% is the default volume.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if volume > 1000:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I can not set the volume above 1,000%."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume <= 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I can not set the volume lower than 0%"), messageable=context
                ),
                ephemeral=True,
            )
            return
        if not context.player:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        max_volume = await self.pylav.player_config_manager.get_max_volume(context.guild.id)
        if volume > max_volume:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "I have been told to restrict the maximum volume to {max_volume_variable_do_not_translate}%."
                    ).format(max_volume=max_volume),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.player.set_volume(volume, requester=context.author)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have set the player volume to {volume_variable_do_not_translate}%.").format(
                    volume_variable_do_not_translate=volume
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="seek", description=_("Seek the current track."))
    @app_commands.describe(seek=_("The player position to seek to"))
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_seek(self, context: PyLavContext, seek: str):  # sourcery skip: low-code-quality
        """Seek the current track.

        Seek can either be a number of seconds or a timestamp.

        Examples:
        `[p]seek 10` Seeks 10 seconds forward
        `[p]seek -20` Seeks 20 seconds backwards
        `[p]seek 0:30` Seeks to 0:30
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

        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if not await context.player.current.is_seekable():
            if await context.player.current.stream():
                await context.send(
                    embed=await context.pylav.construct_embed(
                        title=_("Unable to seek track"),
                        description=_("I can not seek this track as the server reports it is a live stream."),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
            else:
                await context.send(
                    embed=await context.pylav.construct_embed(
                        title=_("Unable to seek track"),
                        description=_(
                            "I can not seek this track as the server report that this track does not support seeking."
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
            return

        if context.player.paused:
            await context.send(
                embed=await context.pylav.construct_embed(
                    title=_("Unable to seek track"),
                    description=_("I can not seek the current track while the player is paused."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        try:
            seek = int(seek)
            if seek == 0:
                seek_ms = 0
            else:
                seek_ms = (await context.player.fetch_position()) + seek * 1000
        except (
            ValueError
        ):
            if seek[-1] == "%":
                seek = int(seek[:-1])
                if seek > 100:
                    await context.send(
                        embed=await context.pylav.construct_embed(
                            title=_("Unable to seek track"),
                            description=_("I can not seek the current track past 100%."),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )
                    return
                if seek < 0:
                    await context.send(
                        embed=await context.pylav.construct_embed(
                            title=_("Unable to seek track"),
                            description=_("I can not seek the current track before 0%."),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )
                    return
                seek_ms = await context.player.current.duration() * (seek / 100)
                seek = -round(((await context.player.fetch_position()) - seek_ms) / 1000)
            # Taken from https://github.com/Cog-Creators/Red-DiscordBot/blob/ec55622418810731e1ee2ede1569f81f9bddeeec/redbot/cogs/audio/core/utilities/miscellaneous.py#L28
            elif (match := _RE_TIME_CONVERTER.match(seek)) is not None:
                hr = int(match.group(1)) if match.group(1) else 0
                mn = int(match.group(2)) if match.group(2) else 0
                sec = int(match.group(3)) if match.group(3) else 0
                seek = sec + (mn * 60) + (hr * 3600)
                seek_ms = seek * 1000
            else:
                seek_ms = 0
                seek = 0
        if seek > 0:
            if seek_ms >= await context.player.current.duration():
                message = _(
                    "I have moved the current track forward {number_of_seconds_variable_do_not_translate} seconds to the end of the track."
                ).format(number_of_seconds_variable_do_not_translate=seek)
            else:
                message = _(
                    "I have moved the current track forward {number_of_seconds} seconds to position {timestamp_variable_do_not_translate}."
                ).format(timestamp_variable_do_not_translate=format_time_dd_hh_mm_ss(seek_ms), number_of_seconds=seek)
        elif seek < 0:
            if seek_ms <= 0:
                message = _(
                    "I have moved the current track back {number_of_seconds_variable_do_not_translate} seconds to the beginning."
                ).format(number_of_seconds_variable_do_not_translate=abs(seek))
            else:
                message = _(
                    "I have moved the current track back {number_of_seconds} seconds to position {timestamp_variable_do_not_translate}."
                ).format(
                    timestamp_variable_do_not_translate=format_time_dd_hh_mm_ss(seek_ms), number_of_seconds=abs(seek)
                )
        else:
            message = _("I have moved the current track to the beginning.")

        await context.send(
            embed=await context.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

        await context.player.seek(seek_ms, context.author, False)

    @commands.hybrid_command(name="prev", description=_("Play previously played tracks."), aliases=["previous"])
    @commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def command_previous(self, context: PyLavContext):
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
