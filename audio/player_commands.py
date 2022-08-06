import contextlib
from abc import ABC
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator

from pylav import Query, Track
from pylav.tracks import decode_track
from pylav.types import PyLavCogMixin
from pylav.utils import PyLavContext, format_time
from pylavcogs_shared.utils.decorators import invoker_is_dj

LOGGER = getLogger("red.3pt.PyLavPlayer.commands.player")
_ = Translator("PyLavPlayer", Path(__file__))


class PlayerCommands(PyLavCogMixin, ABC):
    @commands.command(name="playnow", description="Plays the specified track in the queue.", aliases=["pn"])
    @commands.guild_only()
    @invoker_is_dj()
    async def command_playnow(self, context: PyLavContext, queue_number: int, after_current: bool = False):
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

    @commands.command(name="remove", description="Remove the specified track from the queue.")
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
                    requester=context.author.i,
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
