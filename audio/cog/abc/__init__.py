from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

from pylav import Client


class MPMixin(ABC):
    bot: Red
    lavalink: Client
    config: Config
    now_ctx = discord.app_commands.ContextMenu

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def cog_load(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def format_help_for_context(self, context: commands.Context) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def cog_before_invoke(self, context: commands.Context) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def cog_unload(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        raise NotImplementedError()
