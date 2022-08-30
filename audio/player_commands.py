import contextlib
from abc import ABC
from functools import partial
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.tracks import decode_track
from pylav.types import PyLavCogMixin
from pylav.utils import PyLavContext, format_time
from pylavcogs_shared.utils import rgetattr
from pylavcogs_shared.utils.decorators import invoker_is_dj

LOGGER = getLogger("red.3pt.PyLavPlayer.commands.player")
_ = Translator("PyLavPlayer", Path(__file__))


class PlayerCommands(PyLavCogMixin, ABC):
    @commands.command(name="bump", description=_("Plays the specified track in the queue."))
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
                embed=await context.construct_embed(description=_("Queue is empty."), messageable=context),
                ephemeral=True,
            )
            return
        if queue_number < 1 or queue_number > player.queue.size():
            await context.send(
                embed=await context.construct_embed(
                    description=_("Track index must be between 1 and {size}.").format(size=player.queue.size()),
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
                    description=_("There is no track in position {position}.").format(position=queue_number),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if after_current:
            await player.move_track(track, context.author, 0)
            await context.send(
                embed=await context.construct_embed(
                    description=_("{track} will play after {current} finishes (in {eta}).").format(
                        track=await track.get_track_display_name(with_url=True),
                        current=await player.current.get_track_display_name(with_url=True),
                        eta=format_time(player.current.duration - player.position),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_("{track} will start now\n{current} has been skipped.").format(
                        track=await track.get_track_display_name(with_url=True),
                        current=await player.current.get_track_display_name(with_url=True),
                        eta=format_time(player.current.duration - player.position),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            await player.play(track=track, requester=context.author, query=await track.query())

    @commands.command(name="playnext", description=_("Enqueue a track a song to the top of the queue."), aliases=["pn"])
    @commands.guild_only()
    @invoker_is_dj()
    async def command_playnext(self, context: PyLavContext, *, query: str):
        """Enqueue a track a song to the top of the queue."""
        if isinstance(context, discord.Interaction):
            send = partial(context.followup.send, wait=True)
            if not context.response.is_done():
                await context.response.defer(ephemeral=True)
            author = context.user
        else:
            send = context.send
            author = context.author

        player = context.player

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
                await player.add(requester=author.id, track=track, index=0)
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
                    await player.add(requester=author.id, track=successful[0], index=0)
                else:
                    await player.bulk_add(requester=author.id, tracks_and_queries=successful, index=0)
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
                    thumbnail=await single_track.thumbnail(),
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

    @commands.command(name="remove", description=_("Remove the specified track from the queue."))
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
        queue_number = None
        if player.queue.empty():
            await context.send(
                embed=await context.construct_embed(description=_("Queue is empty."), messageable=context),
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
                        description=_("Track index must be between 1 and {size}.").format(size=player.queue.size()),
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
                        description=_("There is no track in position {position}.").format(position=queue_number),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        else:
            try:
                data, __ = decode_track(track_url_or_index)
                track = Track(
                    node=player.node,
                    data=data,
                    query=await Query.from_base64(track_url_or_index),
                    requester=context.author.id,
                )
            except Exception:  # noqa
                track = Track(
                    node=player.node,
                    data=None,
                    query=await Query.from_string(track_url_or_index),
                    requester=context.author.id,
                )
                await track.search(player)
        try:
            number_removed += await player.remove_from_queue(
                track, requester=context.author, duplicates=remove_duplicates
            )
        except IndexError:
            if not number_removed:
                await context.send(
                    embed=await context.construct_embed(
                        description=_("{track} not found in queue.").format(
                            track=await track.get_track_display_name(with_url=True)
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        await context.send(
            embed=await context.construct_embed(
                description=_("Removed {times} {entry_plural} of {track} from the queue.").format(
                    times=number_removed,
                    track=await track.get_track_display_name(with_url=True),
                    entry_plural=_("entry") if number_removed == 1 else _("entries"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
