from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import discord
from redbot.core import Config

from pylav import Client
from pylav.types import BotT
from pylav.utils import PyLavContext


class MPMixin(ABC):
    bot: BotT
    lavalink: Client
    config: Config

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def cog_load(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def format_help_for_context(self, context: PyLavContext) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def cog_before_invoke(self, context: PyLavContext) -> None:
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

    # COMMANDS
    @abstractmethod
    async def command_play(self, ctx: PyLavContext, *, query: str):
        raise NotImplementedError()

    @abstractmethod
    async def command_now(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_skip(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_stop(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_pause(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_queue(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_shuffle(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_repeat(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_disconnect(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_resume(self, ctx: PyLavContext):
        raise NotImplementedError()

    @abstractmethod
    async def command_volume(self, ctx: PyLavContext, volume: int):
        raise NotImplementedError()

    # @abstractmethod
    # async def command_remove(self, ctx: PyLavContext, index: int):
    #     raise NotImplementedError()


MY_GUILD = discord.Object(id=133049272517001216)
