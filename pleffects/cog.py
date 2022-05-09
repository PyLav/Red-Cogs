from __future__ import annotations

from pathlib import Path

from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.types import BotT

LOGGER = getLogger("red.3pt.PyLavEffects")

_ = Translator("PyLavEffects", Path(__file__))


@cog_i18n(_)
class PyLavEffects(commands.Cog):
    """Apply filters and effects to the PyLav player."""

    __version__ = "0.0.0.1a"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
