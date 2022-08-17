import datetime
import typing
from abc import ABC
from pathlib import Path
from typing import Union

import asyncstdlib
import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.commands import TimedeltaConverter
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import bold, box, humanize_number, humanize_timedelta
from tabulate import tabulate

import pylavcogs_shared
from pylav.converters import PlaylistConverter
from pylav.types import PyLavCogMixin
from pylav.utils import PyLavContext
from pylavcogs_shared.ui.prompts.playlists import maybe_prompt_for_playlist

LOGGER = getLogger("red.3pt.PyLavPlayer.commands.config")

_ = Translator("PyLavPlayer", Path(__file__))


class ConfigCommands(PyLavCogMixin, ABC):
    @commands.group(name="playerset")
    async def command_playerset(self, context: PyLavContext) -> None:
        """Player configuration commands."""

    @command_playerset.command(name="version")
    async def command_playerset_version(self, context: PyLavContext) -> None:
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

    @commands.is_owner()
    @command_playerset.group(name="global", aliases=["owner"])
    async def command_playerset_global(self, context: PyLavContext) -> None:
        """Global configuration options."""

    @command_playerset_global.command(name="vol", aliases=["volume"])
    async def command_playerset_global_volume(self, context: PyLavContext, volume: int) -> None:
        """Set the maximum volume server can set."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if volume > 1000:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume must be less than 1000."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume < 0:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume must be greater than 0."), messageable=context
                ),
                ephemeral=True,
            )
            return
        self.lavalink.player_manager.global_config.max_volume = volume
        await self.lavalink.player_manager.global_config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Max volume set to {volume}%.").format(volume=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="deafen", aliases=["deaf"])
    async def command_playerset_global_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should deafen itself when playing."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        self.lavalink.player_manager.global_config.self_deaf = toggle
        await self.lavalink.player_manager.global_config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Deafen set to {deafen}.").format(deafen=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="shuffle")
    async def command_playerset_global_shuffle(
        self, context: PyLavContext, toggle: typing.Optional[bool] = None
    ) -> None:
        """Set whether the bot should shuffle its queue after every new song added."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        self.lavalink.player_manager.global_config.shuffle = toggle
        await self.lavalink.player_manager.global_config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Shuffle set to {shuffle}.").format(shuffle=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="auto")
    async def command_playerset_global_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should automatically play songs when it's queue is empty."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        self.lavalink.player_manager.global_config.auto_play = toggle
        await self.lavalink.player_manager.global_config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Auto-Play set to {auto}.").format(auto=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.group(name="dc")
    async def command_playerset_global_dc(self, context: PyLavContext) -> None:
        """Set whether the bot should disconnect from the voice voice channel."""

    @command_playerset_global_dc.command(name="empty")
    async def command_playerset_global_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=60) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice voice channel when the queue is empty.
            - `<duration>`: How longer after the queue is empty should the player be disconnected. Default is 60 seconds.
            Accepts: seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be given in seconds)
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        self.lavalink.player_manager.global_config.empty_queue_dc["enabled"] = toggle
        self.lavalink.player_manager.global_config.empty_queue_dc["time"] = after.total_seconds() if after else 60
        await self.lavalink.player_manager.global_config.save()
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}.").format(duration=timedelta_str)
        else:
            extras = ""
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Disconnect from voice channel when queue is empty set to {empty}{extras}.").format(
                    empty=_("Enabled") if toggle else _("Disabled"), extras=extras
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global_dc.command(name="alone")
    async def command_playerset_global_dc_alone(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=60) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice voice channel when alone.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice voice channel when it detects that it is alone.
            - `<duration>`: How longer after detecting should the player be disconnected Default is 60 seconds.
            Accepts: seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be given in seconds)
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        self.lavalink.player_manager.global_config.alone_dc["enabled"] = toggle
        self.lavalink.player_manager.global_config.alone_dc["time"] = after.total_seconds() if after else 60
        await self.lavalink.player_manager.global_config.save()
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}.").format(duration=timedelta_str)
        else:
            extras = ""

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Disconnect from voice channel when alone set to {empty}{extras}.").format(
                    empty=_("Enabled") if toggle else _("Disabled"), extras=extras
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @command_playerset.group(name="server", aliases=["guild"])
    async def command_playerset_server(self, context: PyLavContext) -> None:
        """Server configuration options."""

    @command_playerset_server.command(name="vol", aliases=["volume"])
    async def command_playerset_server_volume(self, context: PyLavContext, volume: int) -> None:
        """Set the maximum volume a user can set."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if volume > 1000:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume must be less than 1000."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume < 0:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Volume must be greater than 0."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if volume > await self.lavalink.player_manager.global_config.fetch_max_volume():
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Volume must be between 0 and {volume}%.").format(
                        volume=humanize_number(self.lavalink.player_manager.global_config.max_volume)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        max_volume = await asyncstdlib.min(
            [await config.fetch_max_volume(), await self.lavalink.player_manager.global_config.fetch_max_volume()]
        )
        if volume > max_volume:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Volume must be between 0 and {volume}%.").format(volume=humanize_number(max_volume)),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        config.volume = volume
        config.max_volume = volume
        if context.player and context.player.volume > volume:
            await context.player.set_volume(volume, requester=context.author)
        await config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Max volume set to {volume}%.").format(volume=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="deafen", aliases=["deaf"])
    async def command_playerset_server_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should deafen itself when playing."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.lavalink.player_manager.global_config.fetch_self_deaf() is True:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("My owner told me to always deafen myself."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        if context.player and context.me.voice.self_deaf != toggle:
            await context.player.self_deafen(toggle)
        else:
            config.self_deaf = toggle
            await config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Deafen set to {deafen}.").format(deafen=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="shuffle")
    async def command_playerset_server_shuffle(
        self, context: PyLavContext, toggle: typing.Optional[bool] = None
    ) -> None:
        """Set whether the bot should shuffle its queue after every new song added."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if (await self.lavalink.player_manager.global_config.fetch_shuffle()) is False:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Shuffle is globally disabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            await context.player.set_shuffle(toggle)
        else:
            if context.player:
                config = context.player.config
            else:
                config = await self.lavalink.player_config_manager.get_config(context.guild.id)
            config.shuffle = toggle
            await config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Shuffle set to {shuffle}.").format(shuffle=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="auto")
    async def command_playerset_server_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should automatically play songs when it's queue is empty."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.lavalink.player_manager.global_config.fetch_auto_play() is False:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Auto-Play is globally disabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        if context.player:
            await context.player.set_autoplay(toggle)
        else:
            config.auto_play = toggle
            await config.save()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Auto-Play set to {auto}.").format(auto=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="dc")
    async def command_playerset_server_dc(self, context: PyLavContext) -> None:
        """Set whether the bot should disconnect from the voice voice channel."""

    @command_playerset_server.command(name="empty")
    async def command_playerset_server_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=60) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice voice channel when the queue is empty.
            - `<duration>`: How longer after the queue is empty should the player be disconnected. Default is 60
            seconds.
            Accepts: seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be
            given in seconds)
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        db_value = await self.lavalink.player_manager.global_config.fetch_empty_queue_dc()
        global_state, global_timer = db_value.enabled, db_value.time
        if global_state is True:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_(
                        "Disconnect when the queue finished is globally enable "
                        "and players will be disconnected after {delta}."
                    ).format(delta=humanize_timedelta(timedelta=datetime.timedelta(seconds=global_timer))),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        config.empty_queue_dc["enabled"] = toggle
        config.empty_queue_dc["time"] = after.total_seconds() if after else 60
        await config.save()
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}.").format(duration=timedelta_str)
        else:
            extras = ""
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Disconnect from voice channel when queue is empty set to {empty}{extras}.").format(
                    empty=_("Enabled") if toggle else _("Disabled"), extras=extras
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="alone")
    async def command_playerset_server_dc_alone(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=60) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice voice channel when alone.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice voice channel when it detects that it is
            alone.
            - `<duration>`: How longer after detecting should the player be disconnected Default is 60 seconds.
            Accepts: seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be
            given in seconds)
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        db_value = await self.lavalink.player_manager.global_config.fetch_alone_dc()
        global_state, global_timer = db_value.enabled, db_value.time
        if global_state is True:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_(
                        "Disconnect when alone is globally enable and players will be disconnected after {delta}."
                    ).format(delta=humanize_timedelta(timedelta=datetime.timedelta(seconds=global_timer))),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        config.alone_dc["enabled"] = toggle
        config.alone_dc["time"] = after.total_seconds() if after else 60
        await config.save()
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}.").format(duration=timedelta_str)
        else:
            extras = ""

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Disconnect from voice channel when alone set to {empty}{extras}.").format(
                    empty=_("Enabled") if toggle else _("Disabled"), extras=extras
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="playlist")
    async def command_playerset_server_playlist(self, context: PyLavContext, *, playlist: PlaylistConverter) -> None:
        """Sets the Auto-Play playlist."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        playlists: list[PlaylistModel] = playlist  # type: ignore
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if context.player:
            await context.player.set_autoplay_playlist(playlist)
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
            config.auto_play_playlist_id = playlist.id
            await config.save()

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Auto-Play playlist set to {playlist}.").format(playlist=bold(playlist.name)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="lock")
    async def command_playerset_server_lock(self, context: PyLavContext):
        """Set the channel locks."""

    @command_playerset_server_lock.command(name="commands")
    async def command_playerset_server_lock_commands(
        self, context: PyLavContext, *, channel: Union[discord.TextChannel, discord.Thread, discord.VoiceChannel] = None
    ):
        """Set the channel lock for commands."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not (
            channel
            and (permission := channel.permissions_for(context.me))
            and permission.send_messages
            and permission.embed_links
            and permission.read_message_history
        ):
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "I don't have permission to send message or send embed links or read messages in {channel}."
                    ).format(channel=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        config.text_channel_id = channel.id if channel else None
        if context.player:
            context.player.text_channel = channel
        await config.save()
        if channel:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I will only listen to commands in {channel}.").format(channel=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("I will listen to commands in all channels I can see."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server_lock.command(name="voice", aliases=["vc"])
    async def command_playerset_server_lock_vc(self, context: PyLavContext, *, channel: discord.VoiceChannel = None):
        """Set the channel lock for voice channels."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not (
            channel and (permission := channel.permissions_for(context.me)) and permission.connect and permission.speak
        ):
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("I don't have permission to connect or speak in {channel}.").format(
                        channel=channel.mention
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        config.forced_channel_id = channel.id if channel else None
        if context.player:
            context.player.forced_vc = channel
            if channel and context.player.channel.id != channel.id:
                await context.player.move_to(channel=channel, requester=context.author)
        await config.save()
        if channel:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I will only be allowed to join {channel}.").format(channel=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.lavalink.construct_embed(description=_("I'm free to join any VC."), messageable=context),
            ephemeral=True,
        )
