from __future__ import annotations

from pathlib import Path

import discord
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

import pylavcogs_shared
from pylav.types import BotT
from pylav.utils import PyLavContext
from pylavcogs_shared.utils.decorators import can_run_command_in_channel, invoker_is_dj, requires_player

LOGGER = getLogger("red.3pt.PyLavEffects")

_ = Translator("PyLavEffects", Path(__file__))


@cog_i18n(_)
class PyLavEffects(commands.Cog):
    """Apply filters and effects to the PyLav player."""

    __version__ = "0.0.1.0a"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(enable_slash=True)
        self._config.register_guild(persist_fx=False)

    @commands.group(name="fxset")
    @commands.guild_only()
    @commands.guildowner_or_permissions(manage_guild=True)
    async def command_fxset(self, ctx: PyLavContext) -> None:
        """Configure the Player behaviour when an effect is set."""

    @command_fxset.command(name="version")
    async def command_fxset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and it's PyLav dependencies."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (self.__class__.__name__, self.__version__),
            ("PyLavCogs-Shared", pylavcogs_shared.__VERSION__),
            ("PyLav", self.bot.lavalink.lib_version),
        ]

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=box(tabulate(data, headers=(_("Library/Cog"), _("Version")), tablefmt="fancy_grid")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.hybrid_group(name="fx", description="Apply or remove bundled filters.", aliases=["effects"])
    @commands.guild_only()
    @requires_player()
    @can_run_command_in_channel()
    @invoker_is_dj()
    async def command_fx(self, ctx: PyLavContext) -> None:
        """Apply an Effect preset to the player."""

    @command_fx.command(name="nightcore", aliases=["nc"])
    async def command_fx_nightcore(self, context: PyLavContext) -> None:
        """Apply a Nightcore filter to the player."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if context.player.equalizer.name == "Nightcore":
            await context.player.remove_nightcore(requester=context.author)
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("Nightcore effect has been disabled."),
                ),
                ephemeral=True,
            )
        else:
            await context.player.apply_nightcore(requester=context.author)
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("Nightcore effect has been enabled."),
                ),
                ephemeral=True,
            )
