from __future__ import annotations

import typing
from pathlib import Path

import discord
from discord import app_commands
from discord.app_commands import Range
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

from pylav.constants.misc import EQ_BAND_MAPPING
from pylav.core.context import PyLavContext
from pylav.exceptions.node import NodeHasNoFiltersException
from pylav.extension.red.converters.equalizer import BassBoostConverter
from pylav.extension.red.utils.decorators import invoker_is_dj, requires_player
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.filters import Equalizer
from pylav.storage.models.equilizer import Equalizer as EqualizerModel
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE
from pylav.type_hints.dict_typing import JSON_DICT_TYPE

LOGGER = getLogger("PyLav.cog.Effects")

_ = Translator("PyLavEffects", Path(__file__))


@cog_i18n(_)
class PyLavEffects(DISCORD_COG_TYPE_MIXIN):
    """Apply filters and effects to the PyLav player"""

    __version__ = "1.0.0"

    slash_fx = app_commands.Group(name="fx", description="Apply or remove filters")

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(enable_slash=True)
        self._config.register_guild(persist_fx=False, persist_eq=False)

    @commands.group(name="fxset")
    @commands.guild_only()
    @commands.guildowner_or_permissions(manage_guild=True)
    async def command_fxset(self, ctx: PyLavContext) -> None:
        """Configure the Player behaviour when an effect is set"""

    @command_fxset.command(name="version")
    async def command_fxset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and its PyLav dependencies"""
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

    @commands.group(name="eq")
    @commands.guild_only()
    @commands.guildowner_or_permissions(manage_guild=True)
    async def command_fxset_eq(self, ctx: PyLavContext) -> None:
        """Configure the Player behaviour when an equalizer preset is set"""

    @command_fxset_eq.command(name="persist")
    async def command_fxset_eq_persist(self, context: PyLavContext) -> None:
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

    @slash_fx.command(
        name="nightcore",
        description=shorten_string(max_length=100, string=_("Apply a Nightcore preset to the player")),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_nightcore(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Apply a Nightcore filter to the player"""

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        if context.player.equalizer.name == "Nightcore":
            await context.player.remove_nightcore(requester=context.author)
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("Nightcore effect has been disabled"),
                ),
                ephemeral=True,
            )
        else:
            try:
                await context.player.apply_nightcore(requester=context.author)
            except NodeHasNoFiltersException as exc:
                await context.send(
                    embed=await self.pylav.construct_embed(
                        messageable=context,
                        description=exc.message,
                    ),
                    ephemeral=True,
                )
            else:
                await context.send(
                    embed=await self.pylav.construct_embed(
                        messageable=context,
                        description=_("Nightcore effect has been enabled"),
                    ),
                    ephemeral=True,
                )

    @slash_fx.command(name="varporwave", description=_("Apply a Vaporwave preset to the player"))
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_varporwave(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Apply a Vaporwave filter to the player"""

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        if context.player.equalizer.name == "Vaporwave":
            await context.player.remove_vaporwave(requester=context.author)
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("Vaporwave effect has been disabled"),
                ),
                ephemeral=True,
            )
        else:
            try:
                await context.player.apply_vaporwave(requester=context.author)
            except NodeHasNoFiltersException as exc:
                await context.send(
                    embed=await self.pylav.construct_embed(
                        messageable=context,
                        description=exc.message,
                    ),
                    ephemeral=True,
                )
            else:
                await context.send(
                    embed=await self.pylav.construct_embed(
                        messageable=context,
                        description=_("Vaporwave effect has been enabled"),
                    ),
                    ephemeral=True,
                )

    @slash_fx.command(name="vibrato", description=_("Apply a vibrato filter to the player"))
    @app_commands.describe(
        frequency=_("The vibrato frequency"),
        depth=_("The vibrato depth value"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_vibrato(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        frequency: Range[float, 0.01, 14.0] = None,
        depth: Range[float, 0.01, 1.0] = None,
        reset: bool = False,
    ) -> None:
        """Apply a vibrato filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("vibrato"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Vibrato functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.vibrato.frequency = frequency or context.player.vibrato.frequency
        context.player.vibrato.depth = depth or context.player.vibrato.depth
        await context.player.set_vibrato(vibrato=context.player.vibrato, requester=context.author, forced=reset)
        default = _("Not changed")

        data = [
            (
                EightBitANSI.paint_white(_("Frequency")),
                EightBitANSI.paint_blue(context.player.vibrato.frequency or default),
            ),
            (EightBitANSI.paint_white(_("Depth")), EightBitANSI.paint_blue(context.player.vibrato.depth or default)),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New vibrato effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="tremolo", description=_("Apply a tremolo filter to the player"))
    @app_commands.describe(
        frequency=_("The tremolo frequency"),
        depth=_("The tremolo depth value"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_tremolo(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        frequency: Range[float, 0.01, None] = None,
        depth: Range[float, 0.01, 1.0] = None,
        reset: bool = False,
    ) -> None:
        """Apply a tremolo filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("tremolo"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Tremolo functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.tremolo.frequency = frequency or context.player.tremolo.frequency
        context.player.tremolo.depth = depth or context.player.tremolo.depth
        await context.player.set_tremolo(tremolo=context.player.tremolo, requester=context.author, forced=reset)
        default = _("Not changed")

        data = [
            (
                EightBitANSI.paint_white(_("Frequency")),
                EightBitANSI.paint_blue(context.player.tremolo.frequency or default),
            ),
            (EightBitANSI.paint_white(_("Depth")), EightBitANSI.paint_blue(context.player.tremolo.depth or default)),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New tremolo effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="timescale", description=_("Apply a timescale filter to the player"))
    @app_commands.describe(
        speed=_("The timescale speed value"),
        pitch=_("The timescale pitch value"),
        rate=_("The timescale rate value"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_timescale(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        speed: Range[float, 0.0, None] = None,
        pitch: Range[float, 0.0, None] = None,
        rate: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a timescale filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("timescale"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Timescale functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.timescale.speed = speed or context.player.timescale.speed
        context.player.timescale.pitch = pitch or context.player.timescale.pitch
        context.player.timescale.rate = rate or context.player.timescale.rate
        await context.player.set_timescale(timescale=context.player.timescale, requester=context.author, forced=reset)
        default = _("Not changed")
        data = [
            (EightBitANSI.paint_white(_("Speed")), EightBitANSI.paint_blue(context.player.timescale.speed or default)),
            (EightBitANSI.paint_white(_("Pitch")), EightBitANSI.paint_blue(context.player.timescale.pitch or default)),
            (EightBitANSI.paint_white(_("Rate")), EightBitANSI.paint_blue(context.player.timescale.rate or default)),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New timescale effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="rotation", description=_("Apply a rotation filter to the player"))
    @app_commands.describe(
        hertz=_("The rotation hertz frequency"), reset=_("Reset any existing effects currently applied to the player")
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_rotation(
        self, interaction: DISCORD_INTERACTION_TYPE, hertz: Range[float, 0.0, None] = None, reset: bool = False
    ) -> None:
        """Apply a rotation filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("rotation"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Rotation functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.rotation.hertz = hertz or context.player.rotation.hertz
        await context.player.set_rotation(rotation=context.player.rotation, requester=context.author, forced=reset)
        default = _("Not changed")

        data = [
            (
                EightBitANSI.paint_white(_("Frequency hertz")),
                EightBitANSI.paint_blue(context.player.rotation.hertz or default),
            ),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New rotation effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="lowpass", description=_("Apply a low pass filter to the player"))
    @app_commands.describe(
        smoothing=_("The low pass smoothing value"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_lowpass(
        self, interaction: DISCORD_INTERACTION_TYPE, smoothing: Range[float, 0.0, None] = None, reset: bool = False
    ) -> None:
        """Apply a low pass filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("lowPass"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the LowPass functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.low_pass.smoothing = smoothing or context.player.low_pass.smoothing
        await context.player.set_low_pass(low_pass=context.player.low_pass, requester=context.author, forced=reset)
        default = _("Not changed")

        data = [
            (
                EightBitANSI.paint_white(_("Smoothing factor")),
                EightBitANSI.paint_blue(context.player.low_pass.smoothing or default),
            ),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New low pass effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="karaoke", description=_("Apply a karaoke filter to the player"))
    @app_commands.describe(
        level=_("The level value"),
        mono_level=_("The mono level value"),
        filter_band=_("The filter band"),
        filter_width=_("The filter width value"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_karaoke(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        level: Range[float, 0.0, None] = None,
        mono_level: Range[float, 0.0, None] = None,
        filter_band: Range[float, 0.0, None] = None,
        filter_width: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a karaoke filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("karaoke"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Karaoke functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.karaoke.level = level or context.player.karaoke.level
        context.player.karaoke.mono_level = mono_level or context.player.karaoke.mono_level
        context.player.karaoke.filter_band = filter_band or context.player.karaoke.filter_band
        context.player.karaoke.filter_width = filter_width or context.player.karaoke.filter_width
        await context.player.set_karaoke(karaoke=context.player.karaoke, requester=context.author, forced=reset)
        default = _("Not changed")
        data = [
            (EightBitANSI.paint_white(_("Level")), EightBitANSI.paint_blue(context.player.karaoke.level or default)),
            (
                EightBitANSI.paint_white(_("Mono Level")),
                EightBitANSI.paint_blue(context.player.karaoke.mono_level or default),
            ),
            (
                EightBitANSI.paint_white(_("Filter Band")),
                EightBitANSI.paint_blue(context.player.karaoke.filter_band or default),
            ),
            (
                EightBitANSI.paint_white(_("Filter Width")),
                EightBitANSI.paint_blue(context.player.karaoke.filter_width or default),
            ),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New karaoke effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="channelmix", description=_("Apply a channel mix filter to the player"))
    @app_commands.describe(
        left_to_left=_("The channel mix left to left weight"),
        left_to_right=_("The channel mix left to right weight"),
        right_to_left=_("The channel mix right to left weight"),
        right_to_right=_("The channel mix right to right weight"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_channelmix(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        left_to_left: Range[float, 0.0, None] = None,
        left_to_right: Range[float, 0.0, None] = None,
        right_to_left: Range[float, 0.0, None] = None,
        right_to_right: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a channel mix filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("channelMix"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the ChannelMix functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.channel_mix.left_to_left = left_to_left or context.player.channel_mix.left_to_left
        context.player.channel_mix.left_to_right = left_to_right or context.player.channel_mix.left_to_right
        context.player.channel_mix.right_to_left = right_to_left or context.player.channel_mix.right_to_left
        context.player.channel_mix.right_to_right = right_to_right or context.player.channel_mix.right_to_right
        await context.player.set_channel_mix(
            channel_mix=context.player.channel_mix, requester=context.author, forced=reset
        )
        default = _("Not changed")

        data = [
            (
                EightBitANSI.paint_white(_("Left to Left")),
                EightBitANSI.paint_blue(context.player.channel_mix.left_to_left or default),
            ),
            (
                EightBitANSI.paint_white(_("Left to Right")),
                EightBitANSI.paint_blue(context.player.channel_mix.left_to_right or default),
            ),
            (
                EightBitANSI.paint_white(_("Right to Left")),
                EightBitANSI.paint_blue(context.player.channel_mix.right_to_left or default),
            ),
            (
                EightBitANSI.paint_white(_("Right to Right")),
                EightBitANSI.paint_blue(context.player.channel_mix.right_to_right or default),
            ),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New channel mix effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="distortion", description=_("Apply a distortion filter to the player"))
    @app_commands.describe(
        sin_offset=_("The distortion Sine offset"),
        sin_scale=_("The distortion Sine scale"),
        cos_offset=_("The distortion Cosine offset"),
        cos_scale=_("The distortion Cosine scale"),
        tan_offset=_("The distortion Tangent offset"),
        tan_scale=_("The distortion Tangent scale"),
        offset=_("The distortion offset"),
        scale=_("The distortion scale"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_distortion(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        sin_offset: Range[float, 0.0, None] = None,
        sin_scale: Range[float, 0.0, None] = None,
        cos_offset: Range[float, 0.0, None] = None,
        cos_scale: Range[float, 0.0, None] = None,
        tan_offset: Range[float, 0.0, None] = None,
        tan_scale: Range[float, 0.0, None] = None,
        offset: Range[float, 0.0, None] = None,
        scale: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:  # sourcery skip: low-code-quality
        """Apply a distortion filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("distortion"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Distortion functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.distortion.sin_offset = sin_offset or context.player.distortion.sin_offset
        context.player.distortion.sin_scale = sin_scale or context.player.distortion.sin_scale
        context.player.distortion.cos_offset = cos_offset or context.player.distortion.cos_offset
        context.player.distortion.cos_scale = cos_scale or context.player.distortion.cos_scale
        context.player.distortion.tan_offset = tan_offset or context.player.distortion.tan_offset
        context.player.distortion.tan_scale = tan_scale or context.player.distortion.tan_scale
        context.player.distortion.offset = offset or context.player.distortion.offset
        context.player.distortion.scale = scale or context.player.distortion.scale
        await context.player.set_distortion(
            distortion=context.player.distortion, requester=context.author, forced=reset
        )
        default = _("Not changed")
        data = [
            (
                EightBitANSI.paint_white(_("Sine Offset")),
                EightBitANSI.paint_blue(context.player.distortion.sin_offset or default),
            ),
            (
                EightBitANSI.paint_white(_("Sine Scale")),
                EightBitANSI.paint_blue(context.player.distortion.sin_scale or default),
            ),
            (
                EightBitANSI.paint_white(_("Cosine Offset")),
                EightBitANSI.paint_blue(context.player.distortion.cos_offset or default),
            ),
            (
                EightBitANSI.paint_white(_("Cosine Scale")),
                EightBitANSI.paint_blue(context.player.distortion.cos_scale or default),
            ),
            (
                EightBitANSI.paint_white(_("Tangent Offset")),
                EightBitANSI.paint_blue(context.player.distortion.tan_offset or default),
            ),
            (
                EightBitANSI.paint_white(_("Tangent Scale")),
                EightBitANSI.paint_blue(context.player.distortion.tan_scale or default),
            ),
            (
                EightBitANSI.paint_white(_("Offset")),
                EightBitANSI.paint_blue(context.player.distortion.offset or default),
            ),
            (EightBitANSI.paint_white(_("Scale")), EightBitANSI.paint_blue(context.player.distortion.scale or default)),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New distortion effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="echo", description=_("Apply a echo filter to the player"))
    @app_commands.describe(
        delay=_("The delay of the echo"),
        decay=_("The decay of the echo"),
        reset=_("Reset any existing effects currently applied to the player"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_echo(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        delay: Range[float, 0.0, None] = None,
        decay: Range[float, 0.0, 1.0] = None,
        reset: bool = False,
    ) -> None:
        """Apply a echo filter to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not context.player.node.has_filter("echo"):
            await context.send(
                embed=await self.pylav.construct_embed(
                    messageable=context,
                    description=_("The current node does not have the Echo functionality enabled"),
                ),
                ephemeral=True,
            )
            return
        context.player.echo.delay = delay or context.player.echo.delay
        context.player.echo.decay = decay or context.player.echo.decay
        await context.player.set_echo(echo=context.player.echo, requester=context.author, forced=reset)
        default = _("Not changed")

        data = [
            (EightBitANSI.paint_white(_("Delay")), EightBitANSI.paint_blue(context.player.echo.delay or default)),
            (EightBitANSI.paint_white(_("Decay")), EightBitANSI.paint_blue(context.player.echo.decay or default)),
            (
                EightBitANSI.paint_white(_("Reset previous filters")),
                EightBitANSI.paint_red(_("Yes")) if reset else EightBitANSI.paint_green(_("No")),
            ),
        ]
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context,
                title=_("New echo effect applied to the player"),
                description=box(
                    tabulate(
                        data,
                        headers=(
                            EightBitANSI.paint_yellow(_("Setting"), bold=True, underline=True),
                            EightBitANSI.paint_yellow(_("Value"), bold=True, underline=True),
                        ),
                        tablefmt="fancy_grid",
                    ),
                    lang="ansi",
                ),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="show", description=_("Show the current filters applied to the player"))
    @app_commands.guild_only()
    @requires_player(slash=True)
    async def slash_fx_show(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Show the current filters applied to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        t_effect = EightBitANSI.paint_yellow(_("Effect"), bold=True, underline=True)
        t_values = EightBitANSI.paint_yellow(_("Values"), bold=True, underline=True)
        default = _("Not changed")

        data = []
        for effect in (
            context.player.karaoke,
            context.player.timescale,
            context.player.tremolo,
            context.player.vibrato,
            context.player.rotation,
            context.player.distortion,
            context.player.low_pass,
            context.player.channel_mix,
            context.player.echo,
        ):
            data_ = {t_effect: effect.__class__.__name__}

            if effect:
                values = effect.to_dict()
                if not isinstance(effect, Equalizer):
                    data_[t_values] = "\n".join(
                        f"{EightBitANSI.paint_white(k.title())}: {EightBitANSI.paint_green(v or default)}"
                        for k, v in values.items()
                    )
                else:
                    eq_value = typing.cast(list[JSON_DICT_TYPE], values["bands"])
                    data_[t_values] = "\n".join(
                        [
                            "{band}: {gain}".format(
                                band=EightBitANSI.paint_white(EQ_BAND_MAPPING[band["band"]]),
                                gain=EightBitANSI.paint_green(band["gain"]),
                            )
                            for band in eq_value
                            if band["gain"]
                        ]
                    )
            else:
                data_[t_values] = EightBitANSI.paint_blue(_("N/A"))
            data.append(data_)

        await context.send(
            embed=await self.pylav.construct_embed(
                title=_("Current filters applied to the player"),
                description="__**{translation}:**__\n{data}".format(
                    data=box(tabulate(data, headers="keys", tablefmt="fancy_grid", maxcolwidths=[10, 18]), lang="ansi")  # type: ignore
                    if data
                    else _("None"),
                    translation=discord.utils.escape_markdown(_("Currently Applied")),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="reset", description=_("Reset any existing filters currently applied to the player"))
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_reset(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Reset any existing filters currently applied to the player"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        await context.player.set_filters(requester=context.author, reset_not_set=True)
        await context.player.set_equalizer(requester=context.author, equalizer=Equalizer.default())
        if await self._config.guild(context.guild).persist_eq():
            effects = await context.player.config.fetch_effects()
            effects["equalizer"] = {}
            await context.player.config.update_effects(effects)
        await context.send(
            embed=await self.pylav.construct_embed(
                messageable=context, description=_("Reset any existing filters currently applied to the player")
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="bassboost")
    @app_commands.describe(level=shorten_string(max_length=100, string=_("The bass boost level to apply")))
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_bassboost(self, interaction: DISCORD_INTERACTION_TYPE, level: BassBoostConverter) -> None:
        """Apply a Bass boost equalizer preset to the player.

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
            # Credits goes to toπ#3141,
            # https://discord.com/channels/125227483518861312/418817098278764544/1003697316529709216
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

    @slash_fx.command(name="piano")
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_piano(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
        """Apply a Piano equalizer preset to the player.

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

    @slash_fx.command(name="rock")
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_rock(self, interaction: DISCORD_INTERACTION_TYPE) -> None:
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

    @slash_fx.command(name="customeq", description=_("Apply and/or save a custom equalizer setting"))
    @app_commands.describe(
        name=_("The name of the specified equalizer"),
        description=_("A brief description of the equalizer"),
        band_25=_("Control the 25Hz band of this equalizer"),
        band_40=_("Control the 40Hz band of this equalizer"),
        band_63=_("Control the 63Hz band of this equalizer"),
        band_100=_("Control the 100Hz band of this equalizer"),
        band_160=_("Control the 160Hz band of this equalizer"),
        band_250=_("Control the 250Hz band of this equalizer"),
        band_400=_("Control the 400Hz band of this equalizer"),
        band_630=_("Control the 630Hz band of this equalizer"),
        band_1000=_("Control the 1kHz band of this equalizer"),
        band_1600=_("Control the 1.6kHz band of this equalizer"),
        band_2500=_("Control the 2.5kHz band of this equalizer"),
        band_4000=_("Control the 4kHz band of this equalizer"),
        band_6300=_("Control the 6.3kHz band of this equalizer"),
        band_10000=_("Control the 10kHz band of this equalizer"),
        band_16000=_("Control the 16kHz band of this equalizer"),
        save=_("Should the equalizer you specified be saved?"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_custom(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        name: str,
        description: str = None,
        band_25: Range[float, -0.25, 1.0] = None,
        band_40: Range[float, -0.25, 1.0] = None,
        band_63: Range[float, -0.25, 1.0] = None,
        band_100: Range[float, -0.25, 1.0] = None,
        band_160: Range[float, -0.25, 1.0] = None,
        band_250: Range[float, -0.25, 1.0] = None,
        band_400: Range[float, -0.25, 1.0] = None,
        band_630: Range[float, -0.25, 1.0] = None,
        band_1000: Range[float, -0.25, 1.0] = None,
        band_1600: Range[float, -0.25, 1.0] = None,
        band_2500: Range[float, -0.25, 1.0] = None,
        band_4000: Range[float, -0.25, 1.0] = None,
        band_6300: Range[float, -0.25, 1.0] = None,
        band_10000: Range[float, -0.25, 1.0] = None,
        band_16000: Range[float, -0.25, 1.0] = None,
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
            band_25=band_25 or 0.0,
            band_40=band_40 or 0.0,
            band_63=band_63 or 0.0,
            band_100=band_100 or 0.0,
            band_160=band_160 or 0.0,
            band_250=band_250 or 0.0,
            band_400=band_400 or 0.0,
            band_630=band_630 or 0.0,
            band_1000=band_1000 or 0.0,
            band_1600=band_1600 or 0.0,
            band_2500=band_2500 or 0.0,
            band_4000=band_4000 or 0.0,
            band_6300=band_6300 or 0.0,
            band_10000=band_10000 or 0.0,
            band_16000=band_16000 or 0.0,
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

    @slash_fx.command(name="saveeq", description=_("Save the current applied EQ"))
    @app_commands.describe(
        name=_("The name of the equalizer"),
        description=_("A brief description of the equalizer"),
    )
    @app_commands.guild_only()
    @requires_player(slash=True)
    @invoker_is_dj(slash=True)
    async def slash_fx_save(self, interaction: DISCORD_INTERACTION_TYPE, name: str, description: str = None):
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
