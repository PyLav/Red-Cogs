from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.app_commands import Range
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

from pylav.core.context import PyLavContext
from pylav.extension.red.converters.equalizer import BassBoostConverter
from pylav.extension.red.utils.decorators import invoker_is_dj, requires_player
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.filters import Equalizer
from pylav.storage.models.equilizer import Equalizer as EqualizerModel
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

LOGGER = getLogger("PyLav.cog.Equalizer")

_ = Translator("PyLavEqualizer", Path(__file__))


@cog_i18n(_)
class PyLavEqualizer(DISCORD_COG_TYPE_MIXIN):
    """Apply equalizer presets to the PyLav player"""

    __version__ = "1.0.0.rc2"

    slash_eq = app_commands.Group(
        name="eq",
        description=shorten_string(max_length=100, string=_("Apply an Equalizer preset to the player")),
    )

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(enable_slash=True)
        self._config.register_guild(persist_eq=False)

    @commands.group(name="eqset")
    @commands.guild_only()
    @commands.guildowner_or_permissions(manage_guild=True)
    async def command_eqset(self, ctx: PyLavContext) -> None:
        """Configure the Player behaviour when a preset is set"""

    @command_eqset.command(name="version")
    async def command_eqset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and it's PyLav dependencies"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (EightBitANSI.paint_white(self.__class__.__name__), EightBitANSI.paint_blue(self.__version__)),
            (EightBitANSI.paint_white("PyLav"), EightBitANSI.paint_blue(context.pylav.lib_version)),
        ]

        await context.send(
            embed=await context.pylav.construct_embed(
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Library/Cog"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Version"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_eqset.command(name="persist")
    async def command_eqset_persist(self, context: PyLavContext) -> None:
        """Persist the last used preset"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        async with self._config.guild(context.guild).all() as guild_config:
            guild_config["persist_eq"] = state = not guild_config["persist_eq"]

        if state:
            if context.player:
                effects = await context.player.config.fetch_effects()
                effects["equalizer"] = {}
                await context.player.config.update_effects(effects)
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The player will now apply the last used preset when it is created"),
                ),
                ephemeral=True,
            )
        else:
            if context.player:
                effects = await context.player.config.fetch_effects()
                effects["equalizer"] = context.player.equalizer.to_dict()
                await context.player.config.update_effects(effects)
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("Last used preset will no longer be saved"),
                ),
                ephemeral=True,
            )

    @slash_eq.command(name="bassboost")
    @app_commands.describe(level=shorten_string(max_length=100, string=_("The bass boost level to apply")))
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_bassboost(self, interaction: DISCORD_INTERACTION_TYPE, level: BassBoostConverter) -> None:
        """Apply a Bass boost preset to the player.

        Arguments:
            - Maximum
            - Insane
            - Extreme
            - High
            - Very High
            - Medium
            - Fined Tuned
            - Cut-off
            - Off
        """
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("equalizer"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Equalizer functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        if level == "Off":
            await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
            if await self._config.guild(context.guild).persist_eq():
                effects = await context.player.config.fetch_effects()
                effects["equalizer"] = []  # type: ignore
                await context.player.config.update_effects(effects)
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("Bass boost preset has been disabled"),
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
        elif level == "Fine Tuned":
            # Credits goes to toπ#3141,  https://discord.com/channels/125227483518861312/418817098278764544/1003697316529709216
            equalizer = Equalizer(
                levels=[
                    {"band": 0, "gain": 0.2},
                    {"band": 1, "gain": 0.15},
                    {"band": 2, "gain": 0.1},
                    {"band": 3, "gain": 0.05},
                    {"band": 4, "gain": 0.0},
                    {"band": 5, "gain": -0.05},
                    {"band": 6, "gain": -0.1},
                    {"band": 7, "gain": -0.1},
                    {"band": 8, "gain": -0.1},
                    {"band": 9, "gain": -0.1},
                    {"band": 10, "gain": -0.1},
                    {"band": 11, "gain": -0.1},
                    {"band": 12, "gain": -0.1},
                    {"band": 13, "gain": -0.1},
                    {"band": 14, "gain": -0.1},
                ],
                name=_("Bass boost - Fine Tuned"),
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
            effects = await context.player.config.fetch_effects()
            effects["equalizer"] = context.player.equalizer.to_dict()
            await context.player.config.update_effects(effects)
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                description=_("Preset has been set to {name}").format(name=equalizer.name),
            ),
            ephemeral=True,
        )

    @slash_eq.command(name="piano")
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_piano(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Apply a Piano preset to the player.

        Suitable for acoustic tracks, or tacks with an emphasis on female vocals.

        Can also be used as a bass cut-off.
        """
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("equalizer"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Equalizer functionality enabled"),
                ),
                ephemeral=True,
            )
            return
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
            effects = await context.player.config.fetch_effects()
            effects["equalizer"] = equalizer.to_dict()
            await context.player.config.update_effects(effects)

        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                description=_("Piano preset has been set"),
            ),
            ephemeral=True,
        )

    @slash_eq.command(name="rock")
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_rock(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Apply an experimental Metal/Rock equalizer preset.

        Expect clipping on songs with heavy bass.
        """
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("equalizer"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Equalizer functionality enabled"),
                ),
                ephemeral=True,
            )
            return

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
            effects = await context.player.config.fetch_effects()
            effects["equalizer"] = equalizer.to_dict()
            await context.player.config.update_effects(effects)
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                description=_("Rock/Metal preset has been set"),
            ),
            ephemeral=True,
        )

    @slash_eq.command(name="reset")
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_remove(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Remove any equalizer preset from the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("equalizer"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Equalizer functionality enabled"),
                ),
                ephemeral=True,
            )
            return

        await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
        if await self._config.guild(context.guild).persist_eq():
            effects = await context.player.config.fetch_effects()
            effects["equalizer"] = {}
            await context.player.config.update_effects(effects)
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                description=_("Equalizer preset has been reset"),
            ),
            ephemeral=True,
        )

    @slash_eq.command(name="custom", description=_("Apply and/or save a custom equalizer setting"))
    @app_commands.describe(
        name=_("The name of the specified equalizer"),
        description=_("A brief description of the equalizer"),
        band_25Hz=_("Control the 25Hz band of this equalizer"),
        band_40Hz=_("Control the 40Hz band of this equalizer"),
        band_63Hz=_("Control the 63Hz band of this equalizer"),
        band_100Hz=_("Control the 100Hz band of this equalizer"),
        band_160Hz=_("Control the 160Hz band of this equalizer"),
        band_250Hz=_("Control the 250Hz band of this equalizer"),
        band_400Hz=_("Control the 400Hz band of this equalizer"),
        band_630Hz=_("Control the 630Hz band of this equalizer"),
        band_1kHz=_("Control the 1kHz band of this equalizer"),
        band_1_6kHz=_("Control the 1.6kHz band of this equalizer"),
        band_2_5kHz=_("Control the 2.5kHz band of this equalizer"),
        band_4kHz=_("Control the 4kHz band of this equalizer"),
        band_6_3kHz=_("Control the 6.3kHz band of this equalizer"),
        band_10kHz=_("Control the 10kHz band of this equalizer"),
        band_16kHz=_("Control the 16kHz band of this equalizer"),
        save=_("Should the equalizer you specified be saved?"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_custom(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        name: str,
        description: str = None,
        band_25Hz: Range[float, -0.25, 1.0] = None,
        band_40Hz: Range[float, -0.25, 1.0] = None,
        band_63Hz: Range[float, -0.25, 1.0] = None,
        band_100Hz: Range[float, -0.25, 1.0] = None,
        band_160Hz: Range[float, -0.25, 1.0] = None,
        band_250Hz: Range[float, -0.25, 1.0] = None,
        band_400Hz: Range[float, -0.25, 1.0] = None,
        band_630Hz: Range[float, -0.25, 1.0] = None,
        band_1kHz: Range[float, -0.25, 1.0] = None,
        band_1_6kHz: Range[float, -0.25, 1.0] = None,
        band_2_5kHz: Range[float, -0.25, 1.0] = None,
        band_4kHz: Range[float, -0.25, 1.0] = None,
        band_6_3kHz: Range[float, -0.25, 1.0] = None,
        band_10kHz: Range[float, -0.25, 1.0] = None,
        band_16kHz: Range[float, -0.25, 1.0] = None,
        save: bool = False,
    ) -> None:  # sourcery skip: low-code-quality
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        eq_model = EqualizerModel(
            name=name,
            description=description,
            author=context.author.id,
            scope=context.guild.id,
            id=context.message.id,
            band_25=band_25Hz or 0.0,
            band_40=band_40Hz or 0.0,
            band_63=band_63Hz or 0.0,
            band_100=band_100Hz or 0.0,
            band_160=band_160Hz or 0.0,
            band_250=band_250Hz or 0.0,
            band_400=band_400Hz or 0.0,
            band_630=band_630Hz or 0.0,
            band_1000=band_1kHz or 0.0,
            band_1600=band_1_6kHz or 0.0,
            band_2500=band_2_5kHz or 0.0,
            band_4000=band_4kHz or 0.0,
            band_6300=band_6_3kHz or 0.0,
            band_10000=band_10kHz or 0.0,
            band_16000=band_16kHz or 0.0,
        )
        if eq := eq_model.to_filter():
            if save:
                await eq_model.save()
            if not context.player.node.has_filter("equalizer"):
                await context.send(
                    embed=await self.pylav.construct_embed(
                        messageable=context,
                        description=_("The current node does not have the Equalizer functionality enabled"),
                    ),
                    ephemeral=True,
                )
                return
            await context.player.set_equalizer(requester=context.author, equalizer=eq)

        else:
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("No changes were made to the equalizer, discarding request"),
                ),
                ephemeral=True,
            )

    @slash_eq.command(name="save", description=_("Save the current applied EQ"))
    @app_commands.describe(
        name=_("The name of the equalizer"),
        description=_("A brief description of the equalizer"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_eq_save(self, interaction: DISCORD_INTERACTION_TYPE, name: str, description: str = None):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        if not context.player.equalizer:
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("No changes were made to the equalizer, discarding request"),
                ),
                ephemeral=True,
            )
            return

        data = context.player.equalizer.to_dict()
        data["name"] = name
        eq = context.player.equalizer.from_dict(data)
        eq_model = EqualizerModel.from_filter(
            equalizer=eq, context=context, scope=context.guild.id, description=description
        )
        await eq_model.save()
