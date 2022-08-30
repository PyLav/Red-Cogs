from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.app_commands import Range
from red_commons.logging import getLogger
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

import pylavcogs_shared
from pylav.types import BotT, InteractionT
from pylav.utils import PyLavContext
from pylavcogs_shared.utils.decorators import invoker_is_dj, requires_player

LOGGER = getLogger("red.3pt.PyLavEffects")

T_ = Translator("PyLavEffects", Path(__file__))
_ = lambda s: s


@cog_i18n(T_)
class PyLavEffects(commands.Cog):
    """Apply filters and effects to the PyLav player."""

    __version__ = "0.0.1.0a"

    slash_fx = app_commands.Group(name="fx", description="Apply or remove bundled filters.")

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

    @slash_fx.command(name="nightcore", description=_("Apply a Nightcore preset to the player."))
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_nightcore(self, interaction: InteractionT) -> None:
        """Apply a Nightcore filter to the player."""

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

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

    @slash_fx.command(name="vibrato", description=_("Apply a vibrato filter to the player."))
    @app_commands.describe(
        frequency=_("The vibrato frequency"),
        depth=_("The vibrato depth"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_vibrato(
        self,
        interaction: InteractionT,
        frequency: Range[float, 0.01, 14.0] = None,
        depth: Range[float, 0.01, 1.0] = None,
        reset: bool = False,
    ) -> None:
        """Apply a vibrato filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.vibrato.frequency = frequency or context.player.vibrato.frequency
        context.player.vibrato.depth = depth or context.player.vibrato.depth
        await context.player.set_vibrato(vibrato=context.player.vibrato, requester=context.author, forced=reset)
        data = [
            (_("Frequency"), context.player.vibrato.frequency),
            (_("Depth"), context.player.vibrato.depth),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New vibrato effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="tremolo", description=_("Apply a tremolo filter to the player."))
    @app_commands.describe(
        frequency=_("The tremolo frequency"),
        depth=_("The tremolo depth"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_tremolo(
        self,
        interaction: InteractionT,
        frequency: Range[float, 0.01, None] = None,
        depth: Range[float, 0.01, 1.0] = None,
        reset: bool = False,
    ) -> None:
        """Apply a tremolo filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.tremolo.frequency = frequency or context.player.tremolo.frequency
        context.player.tremolo.depth = depth or context.player.tremolo.depth
        await context.player.set_tremolo(tremolo=context.player.tremolo, requester=context.author, forced=reset)
        data = [
            (_("Frequency"), context.player.tremolo.frequency),
            (_("Depth"), context.player.tremolo.depth),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New tremolo effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="timescale", description=_("Apply a timescale filter to the player."))
    @app_commands.describe(
        speed=_("The timescale speed"),
        pitch=_("The timescale pitch"),
        rate=_("The timescale rate"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_timescale(
        self,
        interaction: InteractionT,
        speed: Range[float, 0.0, None] = None,
        pitch: Range[float, 0.0, None] = None,
        rate: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a timescale filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.timescale.speed = speed or context.player.timescale.speed
        context.player.timescale.pitch = pitch or context.player.timescale.pitch
        context.player.timescale.rate = rate or context.player.timescale.rate
        await context.player.set_timescale(timescale=context.player.timescale, requester=context.author, forced=reset)
        data = [
            (_("Speed"), context.player.timescale.speed),
            (_("Pitch"), context.player.timescale.pitch),
            (_("Rate"), context.player.timescale.rate),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New timescale effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="rotation", description=_("Apply a rotation filter to the player."))
    @app_commands.describe(
        hertz=_("The rotation hertz frequency"), reset=_("Reset any existing effects currently applied to the player.")
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_rotation(
        self, interaction: InteractionT, hertz: Range[float, 0.0, None] = None, reset: bool = False
    ) -> None:
        """Apply a rotation filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.rotation.speed = hertz or context.player.rotation.hertz
        await context.player.set_rotation(rotation=context.player.rotation, requester=context.author, forced=reset)
        data = [
            (_("Frequency hertz"), context.player.rotation.speed),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New rotation effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="lowpass", description=_("Apply a low pass filter to the player."))
    @app_commands.describe(
        smoothing=_("The low pass hertz frequency"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_lowpass(
        self, interaction: InteractionT, smoothing: Range[float, 0.0, None] = None, reset: bool = False
    ) -> None:
        """Apply a low pass filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.low_pass.speed = smoothing or context.player.low_pass.smoothing
        await context.player.set_low_pass(low_pass=context.player.low_pass, requester=context.author, forced=reset)
        data = [
            (_("Smoothing factor"), context.player.low_pass.speed),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New low pass effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="karaoke", description=_("Apply a karaoke filter to the player."))
    @app_commands.describe(
        level=_("The karaoke speed"),
        mono_level=_("The karaoke speed"),
        filter_band=_("The karaoke pitch"),
        filter_width=_("The karaoke rate"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_karaoke(
        self,
        interaction: InteractionT,
        level: Range[float, 0.0, None] = None,
        mono_level: Range[float, 0.0, None] = None,
        filter_band: Range[float, 0.0, None] = None,
        filter_width: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a karaoke filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.karaoke.level = level or context.player.karaoke.level
        context.player.karaoke.mono_level = mono_level or context.player.karaoke.mono_level
        context.player.karaoke.filter_band = filter_band or context.player.karaoke.filter_band
        context.player.karaoke.filter_width = filter_width or context.player.karaoke.filter_width
        await context.player.set_karaoke(karaoke=context.player.karaoke, requester=context.author, forced=reset)
        data = [
            (_("Level"), context.player.karaoke.level),
            (_("Mono Level"), context.player.karaoke.mono_level),
            (_("Filter Band"), context.player.karaoke.filter_band),
            (_("Filter Width"), context.player.karaoke.filter_width),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New karaoke effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="channelmix", description=_("Apply a channel mix filter to the player."))
    @app_commands.describe(
        left_to_left=_("The channel mix left to left weight"),
        left_to_right=_("The channel mix left to left weight"),
        right_to_left=_("The channel mix right to left weight"),
        right_to_right=_("The channel mix right to right weight"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_channelmix(
        self,
        interaction: InteractionT,
        left_to_left: Range[float, 0.0, None] = None,
        left_to_right: Range[float, 0.0, None] = None,
        right_to_left: Range[float, 0.0, None] = None,
        right_to_right: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a channel mix filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        context.player.channel_mix.left_to_left = left_to_left or context.player.channel_mix.left_to_left
        context.player.channel_mix.left_to_right = left_to_right or context.player.channel_mix.left_to_right
        context.player.channel_mix.right_to_left = right_to_left or context.player.channel_mix.right_to_left
        context.player.channel_mix.right_to_right = right_to_right or context.player.channel_mix.right_to_right
        await context.player.set_channel_mix(
            channel_mix=context.player.channel_mix, requester=context.author, forced=reset
        )
        data = [
            (_("Left to Left"), context.player.channel_mix.left_to_left),
            (_("Left to Right "), context.player.channel_mix.left_to_right),
            (_("Right to Left"), context.player.channel_mix.right_to_left),
            (_("Right to Right"), context.player.channel_mix.right_to_right),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New channel mix effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="distortion", description=_("Apply a distortion filter to the player."))
    @app_commands.describe(
        sin_offset=_("The distortion Sine offset"),
        sin_scale=_("The distortion Sine scale"),
        cos_offset=_("The distortion Cosine offset"),
        cos_scale=_("The distortion Cosine scale"),
        tan_offset=_("The distortion Tangent offset"),
        tan_scale=_("The distortion Tangent scale"),
        offset=_("The distortion offset"),
        scale=_("The distortion scale"),
        reset=_("Reset any existing effects currently applied to the player."),
    )
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_distortion(
        self,
        interaction: InteractionT,
        sin_offset: Range[float, 0.0, None] = None,
        sin_scale: Range[float, 0.0, None] = None,
        cos_offset: Range[float, 0.0, None] = None,
        cos_scale: Range[float, 0.0, None] = None,
        tan_offset: Range[float, 0.0, None] = None,
        tan_scale: Range[float, 0.0, None] = None,
        offset: Range[float, 0.0, None] = None,
        scale: Range[float, 0.0, None] = None,
        reset: bool = False,
    ) -> None:
        """Apply a distortion filter to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
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
        data = [
            (_("Sine Offset"), context.player.distortion.sin_offset),
            (_("Sine Scale"), context.player.distortion.sin_scale),
            (_("Cosine Offset"), context.player.distortion.cos_offset),
            (_("Cosine Scale"), context.player.distortion.cos_scale),
            (_("Tangent Offset"), context.player.distortion.tan_offset),
            (_("Tangent Scale"), context.player.distortion.tan_scale),
            (_("Offset"), context.player.distortion.offset),
            (_("Scale"), context.player.distortion.scale),
            (_("Reset previous filters"), _("Yes") if reset else _("No")),
        ]
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context,
                title=_("New distortion effect applied to the player."),
                description=tabulate(data, headers=(_("Setting"), _("Value")), tablefmt="fancy_grid"),
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="show", description=_("Show the current filters applied to the player."))
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_show(self, interaction: InteractionT) -> None:
        """Show the current filters applied to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        t_effect = _("Effect")
        t_values = _("Values")
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
        ):
            data_ = {t_effect: effect.__class__.__name__}

            if effect.changed:
                values = effect.to_dict()
                values.pop("off")
                data_[t_values] = "\n".join(f"{k.title()}: {v}" for k, v in values.items())
            else:
                data_[t_values] = _("N/A")
            data.append(data_)

        await context.send(
            embed=await self.lavalink.construct_embed(
                title=_("Current filters applied to the player."),
                description=_("__**Currently Applied:**__\n{data}").format(
                    data=box(tabulate(data, headers="keys", tablefmt="fancy_grid", maxcolwidths=[10, 18]))
                    if data
                    else _("None"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @slash_fx.command(name="reset", description=_("Reset any existing filters currently applied to the player."))
    @app_commands.guild_only()
    @requires_player()
    @invoker_is_dj()
    async def slash_fx_reset(self, interaction: InteractionT) -> None:
        """Reset any existing filters currently applied to the player."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)

        await context.player.set_filters(requester=context.author, reset_not_set=True)
        await context.send(
            embed=await self.lavalink.construct_embed(
                messageable=context, description=_("Reset any existing filters currently applied to the player.")
            ),
            ephemeral=True,
        )


_ = T_
