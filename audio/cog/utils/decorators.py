from __future__ import annotations

from pathlib import Path

from redbot.core import commands
from redbot.core.i18n import Translator

from audio.cog import errors

_ = Translator("MediaPlayer", Path(__file__))


def always_hidden():
    async def pred(ctx: commands.Context):
        return False

    return commands.check(pred)


def requires_player():
    async def pred(context: commands.Context):
        # TODO: Check room setting if present allow bot to connect to it instead of throwing error
        player = context.cog.lavalink.get_player(context.guild)  # type:ignore
        if not player:
            raise errors.MediaPlayerNotFoundError(
                context,
            )

    return commands.check(pred)
