from abc import ABC
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import Range
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.utils import PyLavContext

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import QueueMenu
from audio.cog.menus.sources import QueueSource
from audio.cog.utils import rgetattr
from audio.cog.utils.decorators import requires_player

LOGGER = getLogger("red.3pt.mp.commands.hybrids")
_ = Translator("MediaPlayer", Path(__file__))


class HybridCommands(MPMixin, ABC):
    @commands.hybrid_command(name="play", description="Plays a specified query.", aliases=["p"])
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    async def command_play(self, context: PyLavContext, *, query: str):
        """Attempt to play the queries which you provide.

        Separate multiple queries with a new line (`shift + enter`).

        If you want to play a a local track, you can do so by specifying the full path or path relatively to the local tracks folder.
        For example if my local tracks folder is : `/home/draper/music`

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
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not query:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("You need to provide a query to play."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        player = context.player
        if player is None:
            channel = rgetattr(context, "author.voice.channel", None)
            if not channel:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("You must be in a voice channel to allow me to connect."), messageable=context
                    ),
                    ephemeral=True,
                )
                return
            player = await context.connect_player(channel=channel, self_deaf=True)
        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        search_queries = [q for q in queries if q.is_search]
        non_search_queries = [q for q in queries if not q.is_search]
        total_tracks_enqueue = 0
        total_tracks_from_search = 0
        failed_queries = []
        single_track = None
        async with context.typing():
            if search_queries:
                for query in search_queries:
                    single_track = track = Track(node=player.node, data=None, query=query, requester=context.author.id)
                    await player.add(requester=context.author.id, track=track)
                    if not player.is_playing:
                        await player.next(requester=context.author)
                    total_tracks_enqueue += 1
                    total_tracks_from_search += 1
            if non_search_queries:
                successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
                    *non_search_queries, requester=context.author, player=player
                )
                if successful:
                    single_track = successful[0]
                total_tracks_enqueue += count
                failed_queries.extend(failed)
                if count:
                    if count == 1:
                        await player.add(requester=context.author.id, track=successful[0])
                    else:
                        await player.bulk_add(requester=context.author.id, tracks_and_queries=successful)
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=context.author)

        if total_tracks_enqueue > 1:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{track_count} tracks enqueued.").format(track_count=total_tracks_enqueue),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif total_tracks_enqueue == 1:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{track} enqueued.").format(
                        track=await single_track.get_track_display_name(with_url=True)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("No tracks were found for your query."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @commands.hybrid_command(
        name="connect", description="Connects the Player to the specified channel or your current channel."
    )
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    async def command_connect(self, context: PyLavContext, *, channel: Optional[discord.VoiceChannel] = None):
        """Connect the bot to the specified channel or your current channel."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

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
        if (player := context.lavalink.get_player(context.guild)) is None:
            await context.lavalink.connect_player(context.author, channel=channel, self_deaf=True)
        else:
            await player.move_to(context.author, channel, self_deaf=True)

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Connected to {channel}").format(channel=channel.mention), messageable=context
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="np", description="Shows the track currently being played.", aliases=["now"])
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_now(self, context: PyLavContext):
        """Shows the track currently being played."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        current_embed = await player.get_currently_playing_message(messageable=context)
        await context.send(embed=current_embed, ephemeral=True)

    @commands.hybrid_command(name="skip", description="Skips or votes to skip the current track.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_skip(self, context: PyLavContext):
        """Skips the current track."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Skipped - {track}").format(
                    track=await player.current.get_track_display_name(with_url=True)
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
        await player.skip(requester=context.author)

    @commands.hybrid_command(name="stop", description="Stops the player and remove all tracks from the queue.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_stop(self, context: PyLavContext):
        """Stops the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not player.current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Player is not currently playing anything."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await player.stop(context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player stopped"), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(
        name="dc", description="Disconnects the player from the voice channel.", aliases=["disconnect"]
    )
    @app_commands.guilds(MY_GUILD)
    @requires_player()
    async def command_disconnect(self, context: PyLavContext):
        """Disconnects the player from the voice channel."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        LOGGER.info("Disconnecting from voice channel - %s", context.author)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        channel = player.channel
        await player.disconnect(requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Disconnected from {channel}").format(channel=channel.mention), messageable=context
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="queue", description="Shows the current queue for the player.", aliases=["q"])
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_queue(self, context: PyLavContext):
        """Shows the current queue for the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        await QueueMenu(
            cog=self,  # type: ignore
            bot=self.bot,
            source=QueueSource(guild_id=context.guild.id, cog=self),  # type: ignore
            original_author=context.author if not context.interaction else context.interaction.user,
        ).start(ctx=context)

    @commands.hybrid_command(name="shuffle", description="Shuffles the player's queue.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_shuffle(self, context: PyLavContext):
        """Shuffles the player's queue."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if player.queue.empty():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("There is nothing in the queue."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await player.shuffle_queue(context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("{queue_size} tracks shuffled").format(
                    queue_size=player.queue.size(), messageable=context
                ),
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="repeat", description="Set whether to repeat current song or queue.")
    @app_commands.guilds(MY_GUILD)
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
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if queue:
            await player.set_repeat("queue", True, context.author)
            msg = _("Repeating the queue")
        else:
            if player.repeat_queue or player.repeat_current:
                await player.set_repeat("disable", False, context.author)
                msg = _("Repeating disabled")
            else:
                await player.set_repeat("current", True, context.author)
                msg = _("Repeating {track}").format(track=await player.current.get_track_display_name(with_url=True))
        await context.send(
            embed=await context.lavalink.construct_embed(description=msg, messageable=context), ephemeral=True
        )

    @commands.hybrid_command(name="pause", description="Pause the player.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_pause(self, context: PyLavContext):
        """Pause the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if player.paused:
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

        await player.set_pause(True, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player paused."), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(name="resume", description="Resume the player.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_resume(self, context: PyLavContext):
        """Resume the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        if not player.paused:
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

        await player.set_pause(False, context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(description=_("Player resumed."), messageable=context),
            ephemeral=True,
        )

    @commands.hybrid_command(name="volume", description="Set the player volume.")
    @app_commands.guilds(MY_GUILD)
    @commands.guild_only()
    @requires_player()
    async def command_volume(self, context: PyLavContext, volume: Range[int, 0, 1000] = 100):
        """Set the player volume.

        The volume is a value from 0-1000.
        """

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return
        await player.set_volume(volume, requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Player volume set to {volume}%.").format(volume=volume), messageable=context
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="prev", description="Play the previous tracks.", aliases=["previous"])
    @app_commands.guilds(MY_GUILD)
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

        player = context.lavalink.get_player(context.guild)
        if not player:
            await context.send(
                embed=await context.lavalink.construct_embed(description=_("No player detected."), messageable=context),
                ephemeral=True,
            )
            return

        if player.history.empty():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("No previous in player history."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await player.previous(requester=context.author)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Playing previous track: {track}.").format(
                    track=await player.current.get_track_display_name(with_url=True)
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
