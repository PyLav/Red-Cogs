from __future__ import annotations

import asyncio
from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n

from pylav import Client
from pylav.exceptions import NoNodeAvailable, NoNodeWithRequestFunctionalityAvailable
from pylav.filters import Equalizer
from pylav.types import BotT
from pylav.utils import PyLavContext
from pylavcogs_shared.errors import MediaPlayerNotFoundError, UnauthorizedChannelError
from pylavcogs_shared.utils.decorators import requires_player

LOGGER = getLogger("red.3pt.PyLavEqualizer")

_ = Translator("PyLavEqualizer", Path(__file__))


@cog_i18n(_)
class PyLavEqualizer(commands.Cog):
    """Apply equalizer presets to the PyLav player."""

    __version__ = "0.0.0.1a"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._init_task = None
        self._slash_sync_task = None
        self.lavalink = Client(bot=self.bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        self.config = Config.get_conf(self, identifier=208903205982044161)
        self.config.register_global(enable_slash=True)
        self.config.register_guild(persist_eq=False)

    async def initialize(self) -> None:
        await self.lavalink.register(self)
        await self.lavalink.initialize()
        self._slash_sync_task = asyncio.create_task(self._sync_tree())

    async def _sync_tree(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.tree.sync()

    async def cog_unload(self) -> None:
        if self._init_task is not None:
            self._init_task.cancel()
        if self._slash_sync_task is not None:
            self._slash_sync_task.cancel()
        await self.bot.lavalink.unregister(cog=self)

    async def cog_check(self, ctx: PyLavContext) -> bool:
        if not ctx.guild or self.command_eqset in ctx.command.parents or self.command_eqset == ctx.command:
            return True
        if ctx.player:
            config = ctx.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(ctx.guild.id)
        if config.text_channel_id and config.text_channel_id != ctx.channel.id:
            raise UnauthorizedChannelError(channel=config.text_channel_id)
        return True

    async def cog_command_error(self, context: PyLavContext, error: Exception) -> None:
        error = getattr(error, "original", error)
        unhandled = True
        if isinstance(error, MediaPlayerNotFoundError):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context, description=_("This command requires an existing player to be run.")
                ),
                ephemeral=True,
            )
        elif isinstance(error, NoNodeAvailable):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_(
                        "MediaPlayer cog is currently temporarily unavailable due to an outage with "
                        "the backend services, please try again later."
                    ),
                    footer=_("No Lavalink node currently available.")
                    if await self.bot.is_owner(context.author)
                    else None,
                ),
                ephemeral=True,
            )
        elif isinstance(error, NoNodeWithRequestFunctionalityAvailable):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("MediaPlayer is currently unable to process tracks belonging to {feature}.").format(
                        feature=error.feature
                    ),
                    footer=_("No Lavalink node currently available with feature {feature}.").format(
                        feature=error.feature
                    )
                    if await self.bot.is_owner(context.author)
                    else None,
                ),
                ephemeral=True,
            )
        elif isinstance(error, UnauthorizedChannelError):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := context.guild.get_channel_or_thread(error.channel))
                        else None
                    ),
                ),
                ephemeral=True,
                delete_after=10,
            )
        if unhandled:
            await self.bot.on_command_error(context, error, unhandled_by_cog=True)  # type: ignore

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
        async with self.config.guild(context.guild).all() as guild_config:
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
    async def command_eq(self, ctx: PyLavContext) -> None:
        """Apply an Equalizer preset to the player."""

    @command_eq.command(name="bassboost", aliases=["bb"])
    async def command_eq_bassboost(self, context: PyLavContext, level: int = 2) -> None:
        """Apply a Bass boost preset to the player.

        The level is a value between 0 and 7.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if level < 0 or level > 7:
            raise commands.BadArgument(_("The level must be between 0 and 7."))

        if level == 0:
            await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
            if await self.config.guild(context.guild).persist_eq():
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
        if level == 7:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 1.0}, {"band": 1, "gain": 1.0}], name=_("Base boost - Maximum")
            )
        elif level == 6:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 1.0}, {"band": 1, "gain": 0.75}], name=_("Base boost - Insane")
            )
        elif level == 5:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.75}, {"band": 1, "gain": 0.75}], name=_("Base boost - Extreme")
            )
        elif level == 4:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.75}, {"band": 1, "gain": 0.5}], name=_("Base boost - Very high")
            )
        elif level == 3:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.5}, {"band": 1, "gain": 0.25}], name=_("Base boost - High")
            )
        elif level == 2:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": 0.25}, {"band": 1, "gain": 0.15}], name=_("Base boost - Medium")
            )
        else:
            equalizer = Equalizer(
                levels=[{"band": 0, "gain": -0.25}, {"band": 1, "gain": -0.25}], name=_("Base boost - Cut-off")
            )
        await context.player.set_equalizer(
            requester=context.author,
            equalizer=equalizer,
        )
        if await self.config.guild(context.guild).persist_eq():
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
        if await self.config.guild(context.guild).persist_eq():
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
        if await self.config.guild(context.guild).persist_eq():
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
        if await self.config.guild(context.guild).persist_eq():
            context.player.config.effects["equalizer"] = {}
            await context.player.config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                description=_("Equalizer preset has been reset."),
            ),
            ephemeral=True,
        )
