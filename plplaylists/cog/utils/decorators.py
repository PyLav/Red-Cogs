from __future__ import annotations

from pathlib import Path

from redbot.core import commands
from redbot.core.i18n import Translator

from pylav.utils import PyLavContext

_ = Translator("PyLavPlaylists", Path(__file__))


def always_hidden():
    async def pred(__: PyLavContext):
        return False

    return commands.check(pred)
