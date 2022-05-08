from __future__ import annotations

from pathlib import Path

from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n

from pylav import Client
from pylav.types import BotT

LOGGER = getLogger("red.3pt.PyLavLocalFiles")

_ = Translator("PyLavLocalFiles", Path(__file__))


@cog_i18n(_)
class PyLavLocalFiles(commands.Cog):
    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._init_task = None
        self.lavalink = Client(bot=self.bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))

    async def initialize(self) -> None:
        await self.lavalink.register(self)
        await self.lavalink.initialize()

    async def cog_unload(self) -> None:
        if self._init_task is not None:
            self._init_task.cancel()
        await self.bot.lavalink.unregister(cog=self)
