from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, TypeVar

import discord
from discord.ext.commands import Cog
from redbot.core import Config, commands
from redbot.core.bot import Red

from pylav import Client, converters


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

    # COMMANDS
    @abstractmethod
    async def command_play(self, ctx: commands.Context, *, query: converters.QueryConverter):
        raise NotImplementedError()

    @abstractmethod
    async def command_now(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_skip(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_stop(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_pause(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_queue(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_shuffle(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_repeat(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_disconnect(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_resume(self, ctx: commands.Context):
        raise NotImplementedError()

    @abstractmethod
    async def command_volume(self, ctx: commands.Context, volume: int):
        raise NotImplementedError()

    # @abstractmethod
    # async def command_remove(self, ctx: commands.Context, index: int):
    #     raise NotImplementedError()


if TYPE_CHECKING:
    from audio import MediaPlayer

    COG_TYPE = TypeVar("COG_TYPE", bound=MediaPlayer)
else:
    try:
        from audio import MediaPlayer

        COG_TYPE = TypeVar("COG_TYPE", bound=MediaPlayer)
    except ImportError:
        COG_TYPE = TypeVar("COG_TYPE", bound=Cog)


MY_GUILD = discord.Object(id=133049272517001216)
