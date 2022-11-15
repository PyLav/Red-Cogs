from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Literal

import discord
from discord import AppCommandType
from expiringdict import ExpiringDict
from red_commons.logging import getLogger
from redbot.core import Config
from redbot.core import commands as red_commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.types import BotT

from audio.config_commands import ConfigCommands
from audio.context_menus import ContextMenus
from audio.hybrid_commands import HybridCommands
from audio.player_commands import PlayerCommands
from audio.slash_commands import SlashCommands
from audio.utility_commands import UtilityCommands


class CompositeMetaClass(type(red_commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """


_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
class PyLavPlayer(
    red_commands.Cog,
    HybridCommands,
    UtilityCommands,
    PlayerCommands,
    ConfigCommands,
    ContextMenus,
    SlashCommands,
    metaclass=CompositeMetaClass,
):
    """A Media player using the PyLav library"""

    __version__ = "1.0.0.0rc1"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_guild(enable_slash=True, enable_context=True)
        self._config.register_global(
            enable_slash=False,
            enable_context=False,
        )
        self.context_user_play = discord.app_commands.ContextMenu(
            name="Play from Spotify/Apple Music", callback=self._context_user_play, type=AppCommandType.user
        )
        self.context_message_play = discord.app_commands.ContextMenu(
            name="Play from message", callback=self._context_message_play, type=AppCommandType.message
        )
        self.bot.tree.add_command(self.context_user_play)
        self.bot.tree.add_command(self.context_message_play)
        self._track_cache = ExpiringDict(max_len=float("inf"), max_age_seconds=60)  # type: ignore

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.context_user_play, type=AppCommandType.user)
        self.bot.tree.remove_command(self.context_message_play, type=AppCommandType.message)

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """
        Method for finding users data inside the cog and deleting it.
        """
        await self._config.user_from_id(user_id).clear()
