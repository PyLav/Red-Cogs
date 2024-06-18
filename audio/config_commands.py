from __future__ import annotations

import datetime
import heapq
import typing

import discord
from redbot.core import commands
from redbot.core.commands import TimedeltaConverter
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, box, humanize_list, humanize_number, humanize_timedelta
from tabulate import tabulate

from pylav.core.context import PyLavContext
from pylav.extension.red.ui.prompts.playlists import maybe_prompt_for_playlist
from pylav.extension.red.utils.decorators import invoker_is_dj, requires_player
from pylav.helpers.discord.converters.playlists import PlaylistConverter
from pylav.helpers.format.ascii import EightBitANSI
from pylav.logging import getLogger
from pylav.storage.models.player.config import PlayerConfig
from pylav.storage.models.playlist import Playlist
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Player.commands.config")

_ = Translator("PyLavPlayer", __file__)


@cog_i18n(_)
class ConfigCommands(DISCORD_COG_TYPE_MIXIN):
    @commands.group(name="playerset")
    async def command_playerset(self, context: PyLavContext) -> None:
        """Player settings commands"""

    @command_playerset.command(name="down")
    @commands.cooldown(1, 600, commands.BucketType.guild)
    @requires_player()
    @invoker_is_dj()
    async def command_playerset_down(self, context: PyLavContext) -> None:
        """Notifies PyLav that a Player is having issues.

        If enough (50% or more of currently playing players) report issues, PyLav will automatically
        switch to a different node or restart the current node where possible.
        """
        if context.player.voted():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("This server already voted recently. Please, try again in 10 minutes."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        context.player.vote_node_down()
        await context.player.change_to_best_node(forced=True, skip_position_fetch=True)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Thank you for your report."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset.command(name="up")
    @requires_player()
    @invoker_is_dj()
    async def command_playerset_up(self, context: PyLavContext) -> None:
        """Removes a vote for a Player being down.

        If enough (50% or more of currently active players) report issues, PyLav will automatically
        switch to a different node or restart the current node where possible.

        This command is only valid if your server previously voted for a node to be down and is now back up.
        """
        if not context.player.voted():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("There are no active votes for the current audio node."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        context.player.unvote_node_down()
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("I have removed your report."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset.command(name="version")
    async def command_playerset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and PyLav"""
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
                            EightBitANSI.paint_yellow(_("Library / Cog"), bold=True, underline=True),
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

    @commands.is_owner()
    @command_playerset.group(name="global", aliases=["owner"])
    async def command_playerset_global(self, context: PyLavContext) -> None:
        """Bot-wide settings."""

    @command_playerset_global.command(name="vol", aliases=["volume"])
    async def command_playerset_global_volume(self, context: PyLavContext, volume: int) -> None:
        """Set the maximum volume a server can set"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if volume > 1000:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("You have to specify a volume less than or equal to 1,000%."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume <= 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The maximum volume must be greater than 0%."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await self.pylav.player_manager.global_config.update_max_volume(volume)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "The maximum volume I will allow anyone in any server is now set to {volume_variable_do_not_translate}%"
                ).format(volume_variable_do_not_translate=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="deafen", aliases=["deaf"])
    async def command_playerset_global_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should deafen myself when playing."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_self_deaf(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("From now on, I will deafen myself when joining a voice channel.")
                    if toggle
                    else _("From now on, I will no longer deafen myself when joining a voice channel.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="autoshuffle")
    async def command_playerset_global_autoshuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the server is allowed to enable auto shuffle."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_auto_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("From now on, I will auto shuffle my track queue when new songs are added.")
                    if toggle
                    else _("From now on, I will no longer auto shuffle my track queue when new songs are added.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="shuffle")
    async def command_playerset_global_shuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should allow users to shuffle the queue"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("From now on, I will allow users to shuffle the queue.")
                    if toggle
                    else _("From now on, I will no longer allow users to shuffle the queue.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="auto")
    async def command_playerset_global_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should automatically play songs when the queue is empty."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_auto_play(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _(
                        "From now on, I will automatically play songs from the specified playlist when the queue is empty."
                    )
                    if toggle
                    else _(
                        "From now on, I will no longer automatically play songs from the specified playlist when the queue is empty."
                    )
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.group(name="dc")
    async def command_playerset_global_dc(self, context: PyLavContext) -> None:
        """Set whether I should disconnect from the voice channel."""

    @command_playerset_global_dc.command(name="empty")
    async def command_playerset_global_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether I should disconnect from the voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: Whether I should disconnect from the voice channel when the queue is empty.
            - `<duration>`: How long after the queue is empty should the player be disconnected? The default is 60 seconds.
            Accepts second, minutes, hours, days and weeks (if no unit is specified, the duration is assumed to be given in seconds)
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_empty_queue_dc(
            {
                "enabled": toggle,
                "time": after.total_seconds() if after else 60,
            }
        )
        if toggle:
            if after:
                message = _(
                    "I will disconnect from the voice channel when the queue is empty after {time_to_dc_variable_do_not_translate}."
                ).format(time_to_dc_variable_do_not_translate=humanize_timedelta(timedelta=after))
            else:
                message = _("I will disconnect from the voice channel when the queue is empty after 60 seconds.")
        else:
            message = _("I will no longer disconnect from the voice channel when the queue is empty.")
        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
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
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether I should disconnect from the voice channel when alone.

        Arguments:
            - `<toggle>`: Whether I should disconnect from the voice channel when I detect that I am alone in a voice channel.
            - `<duration>`: How longer after detecting should the player be disconnected? The default is 60 seconds.
            Accepts second, minutes, hours, days and weeks.
            If no unit is specified, the duration is assumed to be given in seconds.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.pylav.player_manager.global_config.update_alone_dc(
            {
                "enabled": toggle,
                "time": after.total_seconds() if after else 60,
            }
        )

        if toggle:
            if after:
                message = _(
                    "I will disconnect from the voice channel when alone after {time_to_dc_variable_do_not_translate}."
                ).format(time_to_dc_variable_do_not_translate=humanize_timedelta(timedelta=after))
            else:
                message = _("I will disconnect from the voice channel when alone after 60 seconds.")
        else:
            message = _("I will no longer disconnect from the voice channel when alone.")

        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @command_playerset.group(name="server", aliases=["guild"])
    async def command_playerset_server(self, context: PyLavContext) -> None:
        """Server-specific settings."""

    @command_playerset_server.group(name="dj")
    async def command_playerset_server_dj(self, context: PyLavContext) -> None:
        """Add, remove or show the disc jockey roles and users for this server."""

    @command_playerset_server_dj.command(name="add")
    async def command_playerset_server_dj_add(
        self, context: PyLavContext, roles_or_users: commands.Greedy[discord.Role | discord.Member]
    ) -> None:
        """Add disc jockey roles or users to this server."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not roles_or_users:
            return await context.send_help()

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        if len(roles_or_users) == 1:
            role_or_user = roles_or_users[0]
            if isinstance(role_or_user, discord.Role):
                message = _("I have added {role_list_variable_do_not_translate} to the disc jockey roles.").format(
                    role_list_variable_do_not_translate=role_or_user.mention
                )
                await config.add_to_dj_roles(role_or_user)
            else:
                message = _("I have added {user_list_variable_do_not_translate} to the disc jockey users.").format(
                    user_list_variable_do_not_translate=role_or_user.mention
                )
                await config.bulk_add_dj_users(role_or_user)
        else:
            roles = {r for r in roles_or_users if isinstance(r, discord.Role)}
            users = {u for u in roles_or_users if isinstance(u, discord.Member)}
            message = None
            if roles and users:
                message = _(
                    "I have added {role_list_variable_do_not_translate} to the disc jockey roles and {user_list_variable_do_not_translate} to the disc jockey users."
                ).format(
                    role_list_variable_do_not_translate=humanize_list([r.mention for r in roles]),
                    user_list_variable_do_not_translate=humanize_list([u.mention for u in users]),
                )

            if roles:
                if not message:
                    message = _("I have added {role_list_variable_do_not_translate} to the disc jockey roles.").format(
                        role_list_variable_do_not_translate=humanize_list([r.mention for r in roles])
                    )
                await config.bulk_add_dj_roles(*roles)
            if users:
                if not message:
                    message = _("I have added {user_list_variable_do_not_translate} to the disc jockey users.").format(
                        user_list_variable_do_not_translate=humanize_list([u.mention for u in users])
                    )
                await config.bulk_add_dj_users(*users)

        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server_dj.command(name="remove")
    async def command_playerset_server_dj_remove(
        self, context: PyLavContext, roles_or_users: commands.Greedy[discord.Role | discord.Member | int]
    ) -> None:
        """Remove disc jockey roles or users in this server."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not roles_or_users:
            return await context.send_help()

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        if len(roles_or_users) == 1:
            message = await self._precess_remove_single_dj_role_or_user(config, roles_or_users)
        else:
            message = await self._process_remove_multiple_dj_roles_or_users(config, roles_or_users)

        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @staticmethod
    async def _process_remove_multiple_dj_roles_or_users(
        config: PlayerConfig, roles_or_users: list[discord.Role | discord.Member | int]
    ) -> str:
        roles = {r for r in roles_or_users if isinstance(r, discord.Role)}
        users = {u for u in roles_or_users if isinstance(u, discord.Member)}
        ints = {i for i in roles_or_users if isinstance(i, int)}
        message = None
        if roles and users and ints:
            message = _(
                "I have removed {role_list_variable_do_not_translate} from the disc jockey roles and {user_list_variable_do_not_translate} from the disc jockey users, as well as {number_list_variable_do_not_translate} from the disc jockey roles and users."
            ).format(
                role_list_variable_do_not_translate=humanize_list([r.mention for r in roles]),
                user_list_variable_do_not_translate=humanize_list([u.mention for u in users]),
                number_list_variable_do_not_translate=humanize_list([str(i) for i in ints]),
            )
        elif roles and users:
            message = _(
                "I have removed {role_list_variable_do_not_translate} from the disc jockey roles and {user_list_variable_do_not_translate} from the disc jockey users."
            ).format(
                role_list_variable_do_not_translate=humanize_list([r.mention for r in roles]),
                user_list_variable_do_not_translate=humanize_list([u.mention for u in users]),
            )
        if roles:
            if not message:
                message = _("I have removed {role_list_variable_do_not_translate} from the disc jockey roles.").format(
                    role_list_variable_do_not_translate=humanize_list([r.mention for r in roles])
                )
            await config.bulk_remove_dj_roles(*roles)
        if users:
            if not message:
                message = _("I have removed {user_list_variable_do_not_translate} from the disc jockey users.").format(
                    user_list_variable_do_not_translate=humanize_list([u.mention for u in users])
                )
            await config.bulk_remove_dj_users(*users)
        if ints:
            if not message:
                message = _(
                    "I have removed {user_or_role_id_list_variable_do_not_translate} from the disc jockey roles and users."
                ).format(user_or_role_id_list_variable_do_not_translate=humanize_list([str(u) for u in users]))
            await config.bulk_remove_dj_users(*[discord.Object(id=i) for i in ints])
            await config.bulk_remove_dj_roles(*[discord.Object(id=i) for i in ints])
        return message

    @staticmethod
    async def _precess_remove_single_dj_role_or_user(
        config: PlayerConfig, roles_or_users: list[discord.Role | discord.Member | int]
    ):
        role_or_user = roles_or_users[0]
        if isinstance(role_or_user, int):
            await config.remove_from_dj_roles(typing.cast(discord.Role, discord.Object(id=role_or_user)))
            await config.remove_from_dj_users(typing.cast(discord.Member, discord.Object(id=role_or_user)))
            message = _(
                "I have Removed `{user_or_role_id_variable_do_not_translate}` from the disc jockey roles and users."
            ).format(user_or_role_id_variable_do_not_translate=role_or_user)
        elif isinstance(role_or_user, discord.Role):
            message = _("I have removed {role_name_variable_do_not_translate} from the disc jockey roles.").format(
                role_name_variable_do_not_translate=role_or_user.mention
            )
            await config.remove_from_dj_roles(role_or_user)
        else:
            message = _("I have removed {user_name_variable_do_not_translate} from the disc jockey users.").format(
                user_name_variable_do_not_translate=role_or_user.mention
            )
            await config.remove_from_dj_users(role_or_user)
        return message

    @command_playerset_server_dj.command(name="list")
    async def command_playerset_server_dj_list(self, context: PyLavContext) -> None:
        """List the disc jockey roles and users for this server."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        def role_sorter(role: discord.Role | int) -> float:
            return float("-inf") if isinstance(role, int) else role.position

        def user_sorter(user: discord.Member | int) -> float:
            return float("-inf") if isinstance(user, int) else user.top_role.position

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        dj_roles = {
            (role_object if (role_object := context.guild.get_role(role)) else role)
            for role in await config.fetch_dj_roles()
        }
        dj_roles = heapq.nlargest(len(dj_roles), iter(dj_roles), key=role_sorter)
        dj_roles_chunks = [dj_roles[i : i + 3] for i in range(0, len(dj_roles), 3)]
        dj_roles_string_list = [
            " || ".join(
                [
                    EightBitANSI.colorize(
                        discord.utils.escape_markdown(str(role)), color=EightBitANSI.closest_color(*role.color.to_rgb())
                    )
                    for role in chunk
                ]
            )
            for chunk in dj_roles_chunks
        ]
        dj_user = {
            (member_object if (member_object := context.guild.get_member(member)) else member)
            for member in await config.fetch_dj_users()
        }
        dj_user = heapq.nlargest(len(dj_user), iter(dj_user), key=user_sorter)
        dj_user_chunks = [dj_user[i : i + 3] for i in range(0, len(dj_user), 3)]
        dj_user_string_list = [
            " || ".join(
                [
                    EightBitANSI.colorize(
                        discord.utils.escape_markdown(str(user)), color=EightBitANSI.closest_color(*user.color.to_rgb())
                    )
                    for user in chunk
                ]
            )
            for chunk in dj_user_chunks
        ]

        if not dj_roles and not dj_user:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("There are no disc jockey roles or disc jockey users set in this server."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        string = ""

        pages = []
        if dj_roles_string_list:
            string += EightBitANSI.paint_yellow(_("Disc Jockey Roles"), bold=True, underline=True)
            for line in dj_roles_string_list:
                if len(string) + len(line) > 3000:
                    pages.append(string)
                    string = ""
                    string += EightBitANSI.paint_yellow(_("Disc Jockey Roles"), bold=True, underline=True)
                string += f"\n{line}"

        if dj_user_string_list:
            if string:
                string += "\n\n"
            string += EightBitANSI.paint_yellow(_("Disc Jockey Users"), bold=True, underline=True)
            for line in dj_user_string_list:
                if len(string) + len(line) > 3000:
                    pages.append(string)
                    string = ""
                    string += EightBitANSI.paint_yellow(_("Disc Jockey Users"), bold=True, underline=True)
                string += f"\n{line}"
        if string:
            pages.append(string)
        await context.send_interactive(messages=pages, box_lang="ansi", embed=True)  # type: ignore

    @command_playerset_server_dj.command(name="clear")
    async def command_playerset_server_dj_clear(self, context: PyLavContext) -> None:
        """Clear the disc jockey roles and users for this server."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        await config.dj_roles_reset()
        await config.dj_users_reset()

        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("I have removed all disc jockey roles and users from this server."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="vol", aliases=["volume"])
    async def command_playerset_server_volume(self, context: PyLavContext, volume: int) -> None:
        """Set the maximum volume a user can set."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if volume > 1000:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The maximum volume must be less than 1,000%."), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume <= 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The maximum volume must be greater than 0%."), messageable=context
                ),
                ephemeral=True,
            )
            return

        if volume > await self.pylav.player_manager.global_config.fetch_max_volume():
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "My owner has told me that server-specific volume must be between 0% and {volume_variable_do_not_translate}%."
                    ).format(
                        volume_variable_do_not_translate=humanize_number(
                            await self.pylav.player_manager.global_config.fetch_max_volume()
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
        max_volume = await self.pylav.player_config_manager.get_max_volume(context.guild.id)
        if volume > max_volume:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "The maximum volume must be between 0% and {volume_variable_do_not_translate}%."
                    ).format(volume_variable_do_not_translate=humanize_number(max_volume)),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        await config.update_max_volume(volume)
        if context.player and context.player.volume > volume:
            await context.player.set_volume(volume, requester=context.author)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "The maximum volume users can set in this server is now {volume_variable_do_not_translate}%."
                ).format(volume_variable_do_not_translate=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="deafen", aliases=["deaf"])
    async def command_playerset_server_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should deafen myself when playing."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.pylav.player_manager.global_config.fetch_self_deaf() is True:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("My owner has requested that I always deafen myself when joining a voice channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
        if context.player and context.me.voice.self_deaf != toggle:
            await context.player.self_deafen(toggle)
        else:
            await config.update_self_deaf(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("I will deafen myself when joining voice channels on this server.")
                    if toggle
                    else _("I will no longer deafen myself when joining voice channels on this server.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="autoshuffle")
    async def command_playerset_server_autoshuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should shuffle the queue after adding every new song."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if await self.pylav.player_manager.global_config.fetch_auto_shuffle() is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("My owner has turned off the auto shuffle capability for all servers."),
                    messageable=context,
                ),
                ephemeral=True,
            )

            return
        if context.player:
            await context.player.set_auto_shuffle(toggle)
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            await config.update_auto_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("Auto shuffle turned on for this server.")
                    if toggle
                    else _("Auto shuffle turned off for this server.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="shuffle")
    async def command_playerset_server_shuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether I should allow users to shuffle the queue"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if (await self.pylav.player_manager.global_config.fetch_shuffle()) is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("My owner has turned off the shuffle capability for all servers."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            await context.player.set_shuffle(toggle)
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            await config.update_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("Shuffling turned on for this server.") if toggle else _("Shuffling turned off for this server.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="auto")
    async def command_playerset_server_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should automatically play songs when the queue is empty."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.pylav.player_manager.global_config.fetch_auto_play() is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("My owner has turned off the autoplay capability for all servers."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
        if context.player:
            await context.player.set_autoplay(toggle)
        else:
            await config.update_auto_play(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=(
                    _("From now on, I will automatically play songs when the queue is empty.")
                    if toggle
                    else _("From now on, I will no longer automatically play songs when the queue is empty.")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="dc")
    async def command_playerset_server_dc(self, context: PyLavContext) -> None:
        """Set whether the bot should disconnect from the voice channel"""

    @command_playerset_server_dc.command(name="empty")
    async def command_playerset_server_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether I should disconnect from the voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: I should disconnect from the voice channel when the queue is empty.
            - `<duration>`: How long after the queue is empty should I disconnect?
            The Default is 60 seconds.
            Accept seconds, minutes, hours, days, and weeks.
            If no unit is specified, the duration is assumed to be seconds.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        db_value = await self.pylav.player_manager.global_config.fetch_empty_queue_dc()
        global_state, global_timer = db_value.enabled, db_value.time
        if global_state is True:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "My owner has told me to disconnect from the voice channel when the queue is empty after {time_to_dc_variable_do_not_translate}."
                    ).format(
                        time_to_dc_variable_do_not_translate=humanize_timedelta(
                            timedelta=datetime.timedelta(seconds=global_timer)
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
        await config.update_empty_queue_dc(
            {
                "enabled": toggle,
                "time": after.total_seconds() if after else 60,
            }
        )
        if toggle:
            if after:
                message = _(
                    "I will disconnect from the voice channel when the queue is empty after {time_to_dc_variable_do_not_translate}."
                ).format(time_to_dc_variable_do_not_translate=humanize_timedelta(timedelta=after))
            else:
                message = _("I will disconnect from the voice channel when the queue is empty after 60 seconds.")
        else:
            message = _("I will no longer disconnect from the voice channel when the queue is empty.")

        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server_dc.command(name="alone")
    async def command_playerset_server_dc_alone(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether I should disconnect from the voice channel when alone.

        Arguments:
            - `<toggle>`: I should disconnect from the voice channel when it detects that it is
            alone.
            - `<duration>`: How longer after detecting should I disconnect?
            The Default is 60 seconds.
            Accept seconds, minutes, hours, days, and weeks.
            If no unit is specified, the duration is assumed to be seconds.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        db_value = await self.pylav.player_manager.global_config.fetch_alone_dc()
        global_state, global_timer = db_value.enabled, db_value.time
        if global_state is True:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "My owner has told me to disconnect from the voice channel when alone after {time_to_dc_variable_do_not_translate}."
                    ).format(
                        time_to_dc_variable_do_not_translate=humanize_timedelta(
                            timedelta=datetime.timedelta(seconds=global_timer)
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player:
            config = context.player.config
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)

        await config.update_alone_dc(
            {
                "enabled": toggle,
                "time": after.total_seconds() if after else 60,
            }
        )
        if toggle:
            if after:
                message = _(
                    "I will disconnect from the voice channel when alone after {time_to_dc_variable_do_not_translate}."
                ).format(time_to_dc_variable_do_not_translate=humanize_timedelta(timedelta=after))
            else:
                message = _("I will disconnect from the voice channel when alone after 60 seconds.")
        else:
            message = _("I will no longer disconnect from the voice channel when alone.")

        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="playlist")
    async def command_playerset_server_playlist(self, context: PyLavContext, *, playlist: PlaylistConverter) -> None:
        """Specify a playlist to be used for autoplay."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        playlists: list[Playlist] = playlist
        playlist = await maybe_prompt_for_playlist(cog=self, playlists=playlists, context=context)
        if not playlist:
            return
        if context.player:
            await context.player.set_autoplay_playlist(playlist)
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            await config.update_auto_play_playlist_id(playlist.id)

        await context.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "From now on, I will use {playlist_name_variable_do_not_translate} to select songs for autoplay."
                ).format(playlist_name_variable_do_not_translate=bold(await playlist.fetch_name())),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="lock")
    async def command_playerset_server_lock(self, context: PyLavContext):
        """Restrict which channels where I can be used."""

    @command_playerset_server_lock.command(name="commands")
    async def command_playerset_server_lock_commands(
        self, context: PyLavContext, *, channel: discord.TextChannel | discord.Thread | discord.VoiceChannel = None
    ):
        """Restrict me only to accept PyLav commands executed from the specified channel."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if channel is not None and not (
            (permission := channel.permissions_for(context.me))
            and permission.send_messages
            and permission.embed_links
            and permission.read_message_history
        ):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "I do not have permission to send messages or send embed links or read messages in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if context.player and channel is not None:
            await context.player.set_text_channel(channel)
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            await config.update_text_channel_id(channel.id if channel else 0)
        if channel:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "I will only accept PyLav commands executed from {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("I will accept PyLav commands executed in all channels I can see in the server."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server_lock.command(name="voice", aliases=["vc"])
    async def command_playerset_server_lock_vc(self, context: PyLavContext, *, channel: discord.VoiceChannel = None):
        """Restrict me only to join the specified voice channel."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if channel is not None and not (
            (permission := channel.permissions_for(context.me)) and permission.connect and permission.speak
        ):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "I do not have permission to connect or speak in {channel_name_variable_do_not_translate}."
                    ).format(channel_name_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player and channel is not None:
            if context.player.channel.id != channel.id:
                await context.player.move_to(channel=channel, requester=context.author)
            await context.player.set_forced_vc(channel)
        else:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            await config.update_forced_channel_id(channel.id if channel else 0)
        if channel:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("I will only be allowed to join {channel_name_variable_do_not_translate}.").format(
                        channel_name_variable_do_not_translate=channel.mention
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("I am allowed to join any voice channel in the server."), messageable=context
            ),
            ephemeral=True,
        )
