from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.filters import Equalizer
from pylav.types import BotT
from pylav.utils import PyLavContext
from pylavcogs_shared.converters.equalizer import BassBoostConverter
from pylavcogs_shared.utils.decorators import can_run_command_in_channel, requires_player

LOGGER = getLogger("red.3pt.PyLavEqualizer")

_ = Translator("PyLavEqualizer", Path(__file__))


@cog_i18n(_)
class PyLavEqualizer(commands.Cog):
    """Apply equalizer presets to the PyLav player."""

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._slash_sync_task = None
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(enable_slash=True)
        self._config.register_guild(persist_eq=False)

    async def initialize(self, *args, **kwargs) -> None:
        self._slash_sync_task = asyncio.create_task(self._sync_tree())

    async def _sync_tree(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.tree.sync()

    async def cog_unload(self) -> None:
        if self._slash_sync_task is not None:
            self._slash_sync_task.cancel()

    @commands.group(name="eqset")
    @commands.guild_only()
    @commands.guildowner_or_permissions(manage_guild=True)
    async def command_eqset(self, ctx: PyLavContext) -> None:
        """Configure the Player behaviour when a preset is set."""

    @command_eqset.command(name="persist")
    async def command_eqset_persist(self, context: PyLavContext) -> None:
        """Persist the last used preset."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        async with self._config.guild(context.guild).all() as guild_config:
            guild_config["persist_eq"] = state = not guild_config["persist_eq"]

        if state:
            if context.player:
                context.player.config.effects["equalizer"] = {}
                await context.player.config.save()
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("The player will now apply the last used preset when it is created."),
                ),
                ephemeral=True,
            )
        else:
            if context.player:
                context.player.config.effects["equalizer"] = context.player.equalizer.to_dict()
                await context.player.config.save()
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("Last used preset will no longer be saved."),
                ),
                ephemeral=True,
            )

    @commands.hybrid_group(name="eq", description="Apply an Equalizer preset to the player.", aliases=["equalizer"])
    @commands.guild_only()
    @requires_player()
    @can_run_command_in_channel()
    async def command_eq(self, ctx: PyLavContext) -> None:
        """Apply an Equalizer preset to the player."""

    @command_eq.command(name="bassboost", aliases=["bb"])
    async def command_eq_bassboost(self, context: PyLavContext, level: BassBoostConverter) -> None:
        """Apply a Bass boost preset to the player.

        Arguments:
            - Maximum
            - Insane
            - Extreme
            - High
            - Very High
            - Medium
            - Cut-off
            - Off
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if level == "Off":
            await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
            if await self._config.guild(context.guild).persist_eq():
                context.player.config.effects["equalizer"] = {}
                await context.player.config.save()
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("Bass boost preset has been disabled."),
                ),
                ephemeral=True,
            )
            return
        if level == "Maximum":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 1.0}, {"band": 1, "gain": 1.0}], name=_("Bass boost - Maximum")
            )
        elif level == "Insane":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 1.0}, {"band": 1, "gain": 0.75}], name=_("Bass boost - Insane")
            )
        elif level == "Extreme":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.75}, {"band": 1, "gain": 0.75}], name=_("Bass boost - Extreme")
            )
        elif level == "Very High":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.75}, {"band": 1, "gain": 0.5}], name=_("Bass boost - Very High")
            )
        elif level == "High":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.5}, {"band": 1, "gain": 0.25}], name=_("Bass boost - High")
            )
        elif level == "Medium":
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.25}, {"band": 1, "gain": 0.15}], name=_("Bass boost - Medium")
            )
        else:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": -0.25}, {"band": 1, "gain": -0.25}], name=_("Bass boost - Cut-off")
            )
        await context.player.set_equalizer(
            requester=context.author,
            equalizer=equalizer,
        )
        if await self._config.guild(context.guild).persist_eq():
            context.player.config.effects["equalizer"] = equalizer.to_dict()
            await context.player.config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("Preset has been set to {name}.").format(name=equalizer.name),
            ),
            ephemeral=True,
        )

    @command_eq.command(name="piano")
    async def command_eq_piano(self, context: PyLavContext) -> None:
        """Apply a Piano preset to the player.

        Suitable for acoustic tracks, or tacks with an emphasis on female vocals.

        Can also be used as a bass cut-off.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        equalizer = Equalizer(
            levels=[
                {"band": 0, "gain": -0.25},
                {"band": 1, "gain": -0.25},
                {"band": 2, "gain": -0.125},
                {"band": 4, "gain": 0.25},
                {"band": 5, "gain": 0.25},
                {"band": 7, "gain": -0.25},
                {"band": 8, "gain": -0.25},
                {"band": 11, "gain": 0.5},
                {"band": 12, "gain": 0.25},
                {"band": 13, "gain": -0.025},
            ],
            name=_("Piano"),
        )
        await context.player.set_equalizer(
            requester=context.author,
            equalizer=equalizer,
        )
        if await self._config.guild(context.guild).persist_eq():
            context.player.config.effects["equalizer"] = equalizer.to_dict()
            await context.player.config.save()

        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("Piano preset has been set."),
            ),
            ephemeral=True,
        )

    @command_eq.command(name="rock", aliases=["metal"])
    async def command_eq_rock(self, context: PyLavContext) -> None:
        """Apply an experimental Metal/Rock equalizer preset.

        Expect clipping on songs with heavy bass.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        equalizer = Equalizer(
            levels=[
                {"band": 1, "gain": 0.1},
                {"band": 2, "gain": 0.1},
                {"band": 3, "gain": 0.15},
                {"band": 4, "gain": 0.13},
                {"band": 5, "gain": 0.1},
                {"band": 7, "gain": 0.125},
                {"band": 8, "gain": 0.175},
                {"band": 9, "gain": 0.175},
                {"band": 10, "gain": 0.125},
                {"band": 11, "gain": 0.125},
                {"band": 12, "gain": 0.1},
                {"band": 13, "gain": 0.075},
            ],
            name=_("Metal"),
        )
        await context.player.set_equalizer(
            requester=context.author,
            equalizer=equalizer,
        )
        if await self._config.guild(context.guild).persist_eq():
            context.player.config.effects["equalizer"] = equalizer.to_dict()
            await context.player.config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("Rock/Metal preset has been set."),
            ),
            ephemeral=True,
        )

    @command_eq.command(name="remove", aliases=["reset"])
    async def command_eq_remove(self, context: PyLavContext) -> None:
        """Remove any equalizer preset from the player."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
        if await self._config.guild(context.guild).persist_eq():
            context.player.config.effects["equalizer"] = {}
            await context.player.config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("Equalizer preset has been reset."),
            ),
            ephemeral=True,
        )
