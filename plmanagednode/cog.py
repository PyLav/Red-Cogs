from __future__ import annotations

from pathlib import Path

from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.types import BotT

LOGGER = getLogger("red.3pt.PyLavManagedNode")

_ = Translator("PyLavManagedNode", Path(__file__))


@cog_i18n(_)
class PyLavManagedNode(commands.Cog):
    """Configure the managed Lavalink node used by PyLav."""

    __version__ = "0.0.0.1a"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
