import hashlib
import re
from abc import ABC
from functools import partial
from pathlib import Path
from re import Pattern
from typing import Final, Optional

import discord
from discord import app_commands
from discord.app_commands import Choice
from expiringdict import ExpiringDict
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.query import SEARCH_REGEX
from pylav.types import InteractionT, PyLavCogMixin
from pylav.utils import PyLavContext, format_time
from pylavcogs_shared.converters.numeric import RangeConverter
from pylavcogs_shared.ui.menus.queue import QueueMenu
from pylavcogs_shared.ui.sources.queue import QueueSource
from pylavcogs_shared.utils import rgetattr
from pylavcogs_shared.utils.decorators import requires_player
from pylavcogs_shared.utils.validators import valid_query_attachment

LOGGER = getLogger("red.3pt.PyLavPlayer.commands.hybrids")
_ = Translator("PyLavPlayer", Path(__file__))
# taken from https://github.com/Cog-Creators/Red-DiscordBot/blob/ec55622418810731e1ee2ede1569f81f9bddeeec/redbot/cogs/audio/core/utilities/miscellaneous.py#L28
_RE_TIME_CONVERTER: Final[Pattern] = re.compile(r"(?:(\d+):)?([0-5]?\d):([0-5]\d)")


class HybridCommands(PyLavCogMixin, ABC):
    _track_cache: ExpiringDict

    @commands.hybrid_command(name="play", description="Plays a specified query.", aliases=["p"])
    @commands.guild_only()
    async def command_play(self, context: PyLavContext, *, query: str = None):  # sourcery no-metrics
        """Attempt to play the queries which you provide.

        Separate multiple queries with a new line (`shift + enter`).

        If you want to play a a local track, you can do so by specifying the full path or path relatively to the local tracks folder.
        For example if my local tracks folder is: `/home/draper/music`

        I can play a single track with `track.mp3` or `/home/draper/music/track.mp3`
        I can play everything inside a folder with `sub-folder/folder`
        I can play everything inside a folder and its sub-folders with the `all:` prefix i.e. `all:sub-folder/folder`

        You can search specify services by using the following prefixes (dependant on service availability):
        `ytmsearch:` - Will search YouTube Music
        `spsearch:` - Will search Spotify
        `amsearch:` - Will search Apple Music
        `scsearch:` - Will search SoundCloud
        `ytsearch:` - Will search YouTube

        You can trigger text-to-speech by using the following prefixes (dependant on service availability):
        `speak:` - The bot will speak the query  (limited to 200 characters)
        `tts://` - The bot will speak the query
        """

        if isinstance(context, discord.Interaction):
            send = partial(context.followup.send, wait=True)
            if not context.response.is_done():
                await context.response.defer(ephemeral=True)
            author = context.user
        else:
            send = context.send
            author = context.author
        if query is None:
            if attachments := context.message.attachments:
                query = "\n".join(
                    attachment.url for attachment in attachments if valid_query_attachment(attachment.filename)
                )
        if not query:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("You need to provide a query to play."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        player = self.lavalink.get_player(context.guild.id)
        if player is None:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(config.forced_channel_id)) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.lavalink.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect."), messageable=context
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await send(
                    embed=await self.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}.").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.lavalink.connect_player(channel=channel, requester=author)

        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        search_queries = [q for q in queries if q.is_search]
        non_search_queries = [q for q in queries if not q.is_search]
        total_tracks_enqueue = 0
        single_track = None
        if search_queries:
            total_tracks_from_search = 0
            for query in search_queries:
                single_track = track = Track(node=player.node, data=None, query=query, requester=author.id)
                await player.add(requester=author.id, track=track)
                if not player.is_playing:
                    await player.next(requester=author)
                total_tracks_enqueue += 1
                total_tracks_from_search += 1
        if non_search_queries:
            successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
                *non_search_queries, requester=author, player=player
            )
            if successful:
                single_track = successful[0]
            total_tracks_enqueue += count
            failed_queries = []
            failed_queries.extend(failed)
            if count:
                if count == 1:
                    await player.add(requester=author.id, track=successful[0])
                else:
                    await player.bulk_add(requester=author.id, tracks_and_queries=successful)
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=author)

        if total_tracks_enqueue > 1:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("{track_count} tracks enqueued.").format(track_count=total_tracks_enqueue),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif total_tracks_enqueue == 1:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("{track} enqueued.").format(
                        track=await single_track.get_track_display_name(with_url=True)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("No tracks were found for your query."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @app_commands.command(name="search", description="Search for a track then play the selected response.")
    @app_commands.guild_only()
    async def slash_search(self, interaction: InteractionT, *, query: str):
        """Search for a track then play the selected response.

        If a prefix is not used it will default to search on YouTube Music.

        You can search specify services by using the following prefixes (dependant on service availability):
        `ytmsearch:` - Will search YouTube Music
        `spsearch:` - Will search Spotify
        `amsearch:` - Will search Apple Music
        `scsearch:` - Will search SoundCloud
        `ytsearch:` - Will search YouTube

        You can trigger text-to-speech by using the following prefixes (dependant on service availability):
        `speak:` - The bot will speak the query  (limited to 200 characters)
        `tts://` - The bot will speak the query
        """
        if query == "000":
            raise commands.BadArgument(_("You haven't select something to play."))
        _track = self._track_cache.get(query)
        track = query if _track is None else await _track.query_identifier()
        await self.command_play.callback(self, interaction, query=track)

    @slash_search.autocomplete("query")
    async def slash_searchl_autocomplete_query(self, interaction: InteractionT, current: str):

        if not (match := SEARCH_REGEX.match(current)) or not match.group("search_query"):
            return [
                Choice(
                    name=_("Search must start with ytmsearch:, spsearch:, amsearch:, scsearch:, ytsearch:"),
                    value="000",
                )
            ]
        tracks = await interaction.client.lavalink.get_tracks(await Query.from_string(current), fullsearch=True)
        if not tracks:
            return [
                Choice(
                    name="No results found.",
                    value="000",
                )
            ]
        tracks = tracks["tracks"][:25]
        if not tracks:
            return [
                Choice(
                    name="No results found.",
                    value="000",
                )
            ]
        choices = []
        node = interaction.client.lavalink.node_manager.available_nodes[0]
        for track in tracks:
            track = Track(
                node=node, data=track, query=await Query.from_base64(track["track"]), requester=interaction.user.id
            )
            track_id = hashlib.md5(track["track"].encode()).hexdigest()
            self._track_cache[track_id] = track
            choices.append(
                Choice(
                    name=await track.get_track_display_name(max_length=95, unformatted=True, with_url=False),
                    value=track_id,
                )
            )
        return choices

    @slash_search.error
    async def slash_search_error(self, interaction: InteractionT, error: Exception):
        error = getattr(error, "original", error)
        if isinstance(error, commands.BadArgument):
            await interaction.response.send_message(
                embed=await self.lavalink.construct_embed(
                    description=_(
                        "You haven't select something to play, "
                        "search must start with `ytmsearch:`, `spsearch:`, `amsearch:`, `scsearch:`, `ytsearch:`"
                    ),
                    messageable=interaction,
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="connect", description="Connects the Player to the specified channel or your current channel."
    )
    @commands.guild_only()
    async def command_connect(self, context: PyLavContext, *, channel: Optional[discord.VoiceChannel] = None):
        """Connect the bot to the specified channel or your current channel."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        if (channel := context.guild.get_channel_or_thread(config.forced_channel_id)) is None:
            channel = channel or rgetattr(context, "author.voice.channel", None)
            if not channel:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_(
                            "You need to be in a voice channel if you don't specify which channel I need to connect to."
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        if not ((permission := channel.permissions_for(context.me)) and permission.connect and permission.speak):
            if permission.connect:
                description = _("I don't have permission to connect to that channel.").format(channel=channel.mention)
            else:
                description = _("I don't have permission to speak in {channel}.").format(channel=channel.mention)
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("I don't have permission to connect to {channel}.").format(channel=description),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if (player := context.player) is None:
            player = await context.lavalink.connect_player(context.author, channel=channel, self_deaf=True)
        else:
            await player.move_to(context.author, channel, self_deaf=True)

        if player.forced_vc:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("I'm forced to only join {channel}.").format(channel=player.forced_vc.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Connected to {channel}").format(channel=player.channel.mention), messageable=context
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(name="np", description="Shows the track currently being played.", aliases=["now"])
    @commands.guild_only()
    @requires_player()
    async def command_now(self, context: PyLavContext):
        """Shows the track currently being played."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        current_embed = await context.player.get_currently_playing_message(messageable=context)
        await context.send(embed=current_embed, ephemeral=True)

    @commands.hybrid_command(name="skip", description="Skips or votes to skip the current track.")
    @commands.guild_only()
    @requires_player()
    async def command_skip(self, context: PyLavContext):
        """Skips the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not context.player.current and not context.player.autoplay_enabled:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        if context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Skipped - {track}").format(
                        track=await context.player.current.get_track_display_name(with_url=True)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Autoplay started."), messageable=context),
                ephemeral=True,
            )
        await context.player.skip(requester=context.author)

    @commands.hybrid_command(name="stop", description="Stops the player and remove all tracks from the queue.")
    @commands.guild_only()
    @requires_player()
    async def command_stop(self, context: PyLavContext):
        """Stops the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.stop(context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player stopped"), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="dc", description="Disconnects the player from the voice channel.", aliases=["disconnect"]
    )
    @requires_player()
    async def command_disconnect(self, context: PyLavContext):
        """Disconnects the player from the voice channel."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        LOGGER.info("Disconnecting from voice channel - %s", context.author)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        channel = context.player.channel
        await context.player.disconnect(requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Disconnected from {channel}").format(channel=channel.mention), messageable=context
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="queue", description="Shows the current queue for the player.", aliases=["q"])
    @commands.guild_only()
    @requires_player()
    async def command_queue(self, context: PyLavContext):
        """Shows the current queue for the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        await QueueMenu(
            cog=self,
            bot=self.bot,
            source=QueueSource(guild_id=context.guild.id, cog=self),
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(ctx=context)

    @commands.hybrid_command(name="shuffle", description="Shuffles the player's queue.")
    @commands.guild_only()
    @requires_player()
    async def command_shuffle(self, context: PyLavContext):
        """Shuffles the player's queue."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if context.player.queue.empty():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("There is nothing in the queue."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.shuffle_queue(context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("{queue_size} tracks shuffled").format(queue_size=context.player.queue.size()),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="repeat", description="Set whether to repeat current song or queue.")
    @commands.guild_only()
    @requires_player()
    async def command_repeat(self, context: PyLavContext, queue: Optional[bool] = None):
        """Set whether to repeat current song or queue.

        If no argument is given, the current repeat mode will be toggled between current track and off.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if queue:
            await context.player.set_repeat("queue", True, context.author)
            msg = _("Repeating the queue")
        elif context.player.config.repeat_queue or context.player.config.repeat_current:
            await context.player.set_repeat("disable", False, context.author)
            msg = _("Repeating disabled")
        else:
            await context.player.set_repeat("current", True, context.author)
            msg = _("Repeating {track}").format(
                track=await context.player.current.get_track_display_name(with_url=True)
                if context.player.current
                else _("current track")
            )
        await context.send(
            embed=await context.lavalink.construct_embed(description=msg, messageable=context), ephemeral=True
        )

    @commands.hybrid_command(name="pause", description="Pause the player.")
    @commands.guild_only()
    @requires_player()
    async def command_pause(self, context: PyLavContext):
        """Pause the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if context.player.paused:
            if context.interaction:
                description = _("Player already paused did you mean to run `/resume`.")
            else:
                description = _("Player already paused did you mean to run `{prefix}{command}`.").format(
                    prefix=context.prefix, command=self.command_resume.qualified_name
                )
            await context.send(
                embed=await context.lavalink.construct_embed(description=description, messageable=context),
                ephemeral=True,
            )
            return

        await context.player.set_pause(True, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player paused."), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(name="resume", description="Resume the player.")
    @commands.guild_only()
    @requires_player()
    async def command_resume(self, context: PyLavContext):
        """Resume the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not context.player.paused:
            if context.interaction:
                description = _("Player already paused did you mean to run `/pause`.")
            else:
                description = _("Player already paused did you mean to run `{prefix}{command}`.").format(
                    prefix=context.prefix, command=self.command_pause.qualified_name
                )
            await context.send(
                embed=await context.lavalink.construct_embed(description=description, messageable=context),
                ephemeral=True,
            )
            return

        await context.player.set_pause(False, context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player resumed."), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(name="volume", description="Set the player volume.")
    @commands.guild_only()
    @requires_player()
    async def command_volume(self, context: PyLavContext, volume: RangeConverter[int, 0, 1000]):
        """Set the player volume.

        The volume is a value from 0-1000.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        config = context.player.config
        max_volume = min(
            await config.fetch_max_volume(), await self.lavalink.player_manager.global_config.fetch_max_volume()
        )
        if volume > max_volume:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume cannot be higher than {max_volume}.").format(max_volume=max_volume),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.player.set_volume(volume, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Player volume set to {volume}%.").format(volume=volume), messageable=context
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="seek", description="Seek the current track.")
    @commands.guild_only()
    @requires_player()
    async def command_seek(self, context: PyLavContext, seek: str):
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
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return

        if not context.player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("Nothing playing."), messageable=context),
                ephemeral=True,
            )
            return

        if not context.player.current.is_seekable:
            if context.player.current.stream:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        title=_("Unable to seek track"),
                        description=_("Can't seek on a stream."),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
            else:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("Unable to seek track."), messageable=context
                    ),
                    ephemeral=True,
                )
            return

        if context.player.paused:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Cannot seek when the player is paused."), messageable=context
                ),
                ephemeral=True,
            )
            return

        try:
            seek = int(seek)
            seek_ms = context.player.position + seek * 1000

            if seek_ms <= 0:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("Moved {seconds}s to 00:00:00.").format(seconds=seek), messageable=context
                    ),
                    ephemeral=True,
                )
            else:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("Moved {seconds}s to {time}.").format(
                            seconds=seek,
                            time=format_time(seek_ms),
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
        except ValueError:  # Taken from https://github.com/Cog-Creators/Red-DiscordBot/blob/ec55622418810731e1ee2ede1569f81f9bddeeec/redbot/cogs/audio/core/utilities/miscellaneous.py#L28
            match = _RE_TIME_CONVERTER.match(seek)
            if match is not None:
                hr = int(match.group(1)) if match.group(1) else 0
                mn = int(match.group(2)) if match.group(2) else 0
                sec = int(match.group(3)) if match.group(3) else 0
                pos = sec + (mn * 60) + (hr * 3600)
                seek_ms = pos * 1000
            else:
                seek_ms = 0

            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Moved to {time}.").format(time=format_time(seek_ms)), messageable=context
                ),
                ephemeral=True,
            )

        await context.player.seek(seek_ms, context.author, False)

    @commands.hybrid_command(name="prev", description="Play the previous tracks.", aliases=["previous"])
    @commands.guild_only()
    @requires_player()
    async def command_previous(self, context: PyLavContext):
        """Play the previous tracks.

        A history of last 100 tracks are kept.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not context.player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return

        if context.player.history.empty():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("No previous in player history."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.player.previous(requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Playing previous track: {track}.").format(
                    track=await context.player.current.get_track_display_name(with_url=True)
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
