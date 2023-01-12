from __future__ import annotations

import contextlib
import datetime
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.core.context import PyLavContext
from pylav.extension.red.utils import rgetattr
from pylav.extension.red.utils.decorators import invoker_is_dj
from pylav.helpers.format.strings import shorten_string
from pylav.helpers.time import get_now_utc
from pylav.logging import getLogger
from pylav.players.player import Player
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Player.commands.player")
_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
class PlayerCommands(DISCORD_COG_TYPE_MIXIN):
    @commands.command(
        name="bump",
        description=shorten_string(max_length=100, string=_("Plays the specified track in the queue")),
    )
    @commands.guild_only()
    @invoker_is_dj()
    async def command_bump(self, context: PyLavContext, queue_number: int, after_current: bool = False):
        """
        Plays the specified track in the queue.

        If you specify the `after_current` argument, the track will be played after the current track, otherwise it will replace the current track
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        player = context.player

        if player.queue.empty():
            await context.send(
                embed=await context.construct_embed(
                    description=shorten_string(max_length=100, string=_("Queue is empty")),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if queue_number < 1 or queue_number > player.queue.size():
            await context.send(
                embed=await context.construct_embed(
                    description=_("Track index must be between 1 and {size}").format(size=player.queue.size()),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        queue_number -= 1

        # noinspection PyUnusedLocal
        track = None

        with contextlib.suppress(ValueError):
            track = player.queue.popindex(queue_number)
        if not track:
            await context.send(
                embed=await context.construct_embed(
                    description=_("There is no track in position {position}").format(position=queue_number),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if after_current:
            await player.move_track(track, context.author, 0)
            await context.send(
                embed=await context.construct_embed(
                    description=_("{track} will play after {current} finishes ({eta})").format(
                        track=await track.get_track_display_name(with_url=True),
                        current=await player.current.get_track_display_name(with_url=True),
                        eta=discord.utils.format_dt(
                            get_now_utc()
                            + datetime.timedelta(
                                milliseconds=await player.current.duration() - await player.fetch_position()
                            ),
                            style="R",
                        ),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_("{track} will start now\n{current} has been skipped").format(
                        track=await track.get_track_display_name(with_url=True),
                        current=await player.current.get_track_display_name(with_url=True),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            await player.play(track=track, requester=context.author, query=await track.query())

    @commands.command(
        name="playnext",
        description=shorten_string(max_length=100, string=_("Enqueue a track at the top of the queue")),
        aliases=["pn"],
    )
    @commands.guild_only()
    @invoker_is_dj()
    async def command_playnext(self, context: PyLavContext, *, query: str):
        """Enqueue a track at the top of the queue"""
        if isinstance(context, discord.Interaction) and not context.response.is_done():
            await context.response.defer(ephemeral=True)

        player = context.player

        if player is None:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(context.author, "voice.channel", None)
                if not channel:
                    await context.send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect"), messageable=context
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=context.author)

        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        search_queries = [q for q in queries if q.is_search]
        non_search_queries = [q for q in queries if not q.is_search]
        total_tracks_enqueue = 0
        single_track = None
        if search_queries:
            single_track, total_tracks_enqueue = await self._process_search_queries(
                context, player, search_queries, single_track, total_tracks_enqueue
            )
        if non_search_queries:
            single_track, total_tracks_enqueue = await self._process_non_search_queries(
                context, non_search_queries, player, single_track, total_tracks_enqueue
            )
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=context.author)

        await self._send_play_next_message(context, single_track, total_tracks_enqueue)

    @staticmethod
    async def _process_search_queries(
        context: PyLavContext,
        player: Player,
        search_queries: list[Query],
        single_track: Track | None,
        total_tracks_enqueue: int,
    ) -> tuple[Track, int]:
        total_tracks_from_search = 0
        for query in search_queries:
            single_track = track = await Track.build_track(
                node=player.node,
                data=None,
                query=query,
                requester=context.author.id,
                partial=query.is_partial,
            )
            await player.add(requester=context.author.id, track=track, index=0)
            if not player.is_playing:
                await player.next(requester=context.author)
            total_tracks_enqueue += 1
            total_tracks_from_search += 1
        return single_track, total_tracks_enqueue

    async def _process_non_search_queries(
        self,
        context: PyLavContext,
        non_search_queries: list[Query],
        player: Player,
        single_track: Track,
        total_tracks_enqueue: int,
    ) -> tuple[Track, int]:
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            *non_search_queries, requester=context.author, player=player
        )
        if successful:
            single_track = successful[0]
        total_tracks_enqueue += count
        failed_queries = []
        failed_queries.extend(failed)
        if count:
            if count == 1:
                await player.add(requester=context.author.id, track=successful[0], index=0)
            else:
                await player.bulk_add(requester=context.author.id, tracks_and_queries=successful, index=0)
        return single_track, total_tracks_enqueue

    async def _send_play_next_message(
        self, context: PyLavContext, single_track: Track, total_tracks_enqueue: int
    ) -> None:
        if total_tracks_enqueue > 1:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("{track_count} tracks enqueued").format(track_count=total_tracks_enqueue),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif total_tracks_enqueue == 1:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("{track} enqueued").format(
                        track=await single_track.get_track_display_name(with_url=True)
                    ),
                    thumbnail=await single_track.artworkUrl(),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("No tracks were found for your query"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @commands.command(name="remove", description=_("Remove the specified track from the queue"))
    @commands.guild_only()
    @invoker_is_dj()
    async def command_remove(self, context: PyLavContext, track_url_or_index: str, remove_duplicates: bool = False):
        """
        Remove the specified track from the queue.

        If you specify the `remove_duplicates` argument, all tracks that are the same as your URL or the index track will be removed.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        player = context.player
        # noinspection PyUnusedLocal
        queue_number = None
        if player.queue.empty():
            await context.send(
                embed=await context.construct_embed(description=_("Queue is empty"), messageable=context),
                ephemeral=True,
            )
            return
        with contextlib.suppress(ValueError):
            queue_number = int(track_url_or_index)
        # noinspection PyUnusedLocal
        track = None
        number_removed = 0
        if queue_number:
            if queue_number < 1 or queue_number > player.queue.size():
                await context.send(
                    embed=await context.construct_embed(
                        description=_("Track index must be between 1 and {size}").format(size=player.queue.size()),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            queue_number -= 1
            with contextlib.suppress(ValueError):
                track = player.queue.popindex(queue_number)
                number_removed += 1
            if not track:
                await context.send(
                    embed=await context.construct_embed(
                        description=_("There is no track in position {position}").format(position=queue_number),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        else:
            try:
                data = await self.pylav.decode_track(track_url_or_index, raise_on_failure=True)
                track = await Track.build_track(
                    node=player.node,
                    data=data,
                    query=await Query.from_string(data.info.uri),
                    requester=context.author.id,
                )
            except Exception:  # noqa
                track = await Track.build_track(
                    node=player.node,
                    data=None,
                    query=await Query.from_string(track_url_or_index),
                    requester=context.author.id,
                )
        try:
            number_removed += await player.remove_from_queue(
                track, requester=context.author, duplicates=remove_duplicates
            )
        except IndexError:
            if not number_removed:
                await context.send(
                    embed=await context.construct_embed(
                        description=_("{track} not found in queue").format(
                            track=await track.get_track_display_name(with_url=True)
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        await context.send(
            embed=await context.construct_embed(
                description=_("Removed {times} {entry_plural} of {track} from the queue").format(
                    times=number_removed,
                    track=await track.get_track_display_name(with_url=True),
                    entry_plural=_("entry") if number_removed == 1 else _("entries"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
