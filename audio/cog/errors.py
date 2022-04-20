from __future__ import annotations

import discord
from redbot.core import commands


class MediaPlayerError(commands.CommandError):
    """
    Base class for all media player errors.
    """


class MediaPlayerCheckError(MediaPlayerError):
    """
    Base class for all check errors.
    """


class MediaPlayerNotFoundError(MediaPlayerCheckError, commands.CheckFailure):
    """
    Raised when a media player is not found.
    """

    def __init__(self, context: commands.Context | discord.Interaction) -> None:
        self.context = context
