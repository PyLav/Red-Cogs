from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import discord
from discord import AppCommandType
from expiringdict import ExpiringDict
from redbot.core import Config
from redbot.core.i18n import Translator, cog_i18n

from pylav.extension.red.utils import CompositeMetaClass
from pylav.type_hints.bot import DISCORD_BOT_TYPE

from audio.config_commands import ConfigCommands
from audio.context_menus import ContextMenus
from audio.hybrid_commands import HybridCommands
from audio.player_commands import PlayerCommands
from audio.slash_commands import SlashCommands
from audio.utility_commands import UtilityCommands

_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
class PyLavPlayer(
    HybridCommands,
    UtilityCommands,
    PlayerCommands,
    ConfigCommands,
    ContextMenus,
    SlashCommands,
    metaclass=CompositeMetaClass,
):
    """A Media player using the PyLav library"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_guild(enable_slash=True, enable_context=True)
        self._config.register_global(
            enable_slash=False,
            enable_context=False,
        )
        self.context_user_play = discord.app_commands.ContextMenu(
            name=_("Play from activity"),
            callback=self._context_user_play,
            type=AppCommandType.user,
            extras={"red_force_enable": True},
        )
        self.context_message_play = discord.app_commands.ContextMenu(
            name=_("Play from message"),
            callback=self._context_message_play,
            type=AppCommandType.message,
            extras={"red_force_enable": True},
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
        await self._config.user_from_id(user_id).clear()
