from __future__ import annotations

import datetime
import typing

import asyncstdlib
import discord
from asyncstdlib import heapq
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
        """Player configuration commands"""

    @command_playerset.command(name="down")
    @commands.cooldown(1, 600, commands.BucketType.guild)
    @requires_player()
    @invoker_is_dj()
    async def command_playerset_down(self, context: PyLavContext) -> None:
        """Notifies PyLav that a Player is having issues.

        If enough (50%+ of currently playing players) report issues, PyLav will automatically
        switch to a different node or restart the current node where possible.
        """
        if context.player.voted():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("This server already voted recently, please try again in 10 minutes"),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        context.player.vote_node_down()
        await context.player.change_to_best_node(forced=True, skip_position_fetch=True)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Thank you for your report"),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset.command(name="up")
    @requires_player()
    @invoker_is_dj()
    async def command_playerset_up(self, context: PyLavContext) -> None:
        """Removes a vote for a Player being down.

        If enough (50%+ of currently playing players) report issues, PyLav will automatically
        switch to a different node or restart the current node where possible.

        This command is only useful if you previously voted for a node to be down and it is now back up.
        """
        if not context.player.voted():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("There is no active votes for the current backend"),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        context.player.unvote_node_down()
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Removed your report"),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset.command(name="version")
    async def command_playerset_version(self, context: PyLavContext) -> None:
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

    @commands.is_owner()
    @command_playerset.group(name="global", aliases=["owner"])
    async def command_playerset_global(self, context: PyLavContext) -> None:
        """Global configuration options"""

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
                    description=_("Volume must be less than 1000"), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume < 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Volume must be greater than 0"), messageable=context
                ),
                ephemeral=True,
            )
            return
        await self.pylav.player_manager.global_config.update_max_volume(volume)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Max volume set to {volume}%").format(volume=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="deafen", aliases=["deaf"])
    async def command_playerset_global_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should deafen itself when playing"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_self_deaf(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Deafen set to {deafen}").format(deafen=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="autoshuffle")
    async def command_playerset_global_autoshuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the a server is allowed to enabled auto shuffle"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_auto_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Auto-Shuffle set to {shuffle}").format(
                    shuffle=_("Enabled") if toggle else _("Disabled")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="shuffle")
    async def command_playerset_global_shuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should allow users to shuffle the queue"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_shuffle(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Shuffle set to {shuffle}").format(shuffle=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.command(name="auto")
    async def command_playerset_global_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should automatically play songs when the queue is empty"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        await self.pylav.player_manager.global_config.update_auto_play(toggle)
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Auto-Play set to {auto}").format(auto=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_global.group(name="dc")
    async def command_playerset_global_dc(self, context: PyLavContext) -> None:
        """Set whether [botname] should disconnect from the voice channel"""

    @command_playerset_global_dc.command(name="empty")
    async def command_playerset_global_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether [botname] should disconnect from the voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: Whether [botname] should disconnect from the voice channel when the queue is empty.
            - `<duration>`: How longer after the queue is empty should the player be disconnected. Default is 60 seconds.
            Accepts second, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be given in seconds)
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
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}").format(duration=timedelta_str)
        else:
            extras = ""
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Disconnect from voice channel when queue is empty set to {empty}{extras}").format(
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
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether [botname] should disconnect from the voice channel when alone.

        Arguments:
            - `<toggle>`: Whether [botname] should disconnect from the voice channel when it detects that it is alone.
            - `<duration>`: How longer after detecting should the player be disconnected. Default is 60 seconds.
            Accepts second, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be given in seconds)
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
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}").format(duration=timedelta_str)
        else:
            extras = ""

        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Disconnect from voice channel when alone set to {empty}{extras}").format(
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
        """Server configuration options"""

    @command_playerset_server.group(name="dj")
    async def command_playerset_server_dj(self, context: PyLavContext) -> None:
        """Add, remove or show the DJ roles and users for the server"""

    @command_playerset_server_dj.command(name="add")
    async def command_playerset_server_dj_add(
        self, context: PyLavContext, roles_or_users: commands.Greedy[discord.Role | discord.Member]
    ) -> None:
        """Add DJ roles or users to this server"""
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
                message = _("Added {role} to the DJ roles").format(role=role_or_user.mention)
                await config.add_to_dj_roles(role_or_user)
            else:
                message = _("Added {user} to the DJ users").format(user=role_or_user.mention)
                await config.bulk_add_dj_users(role_or_user)
        else:
            roles = {r for r in roles_or_users if isinstance(r, discord.Role)}
            users = {u for u in roles_or_users if isinstance(u, discord.Member)}
            message = None
            if roles and users:
                message = _("Added {roles} to the DJ roles and {users} to the DJ users").format(
                    roles=humanize_list([r.mention for r in roles]),
                    users=humanize_list([u.mention for u in users]),
                )

            if roles:
                if not message:
                    message = _("Added {roles} to the DJ roles").format(roles=humanize_list([r.mention for r in roles]))
                await config.bulk_add_dj_roles(*roles)
            if users:
                if not message:
                    message = _("Added {users} to the DJ users").format(users=humanize_list([u.mention for u in users]))
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
        """Remove DJ roles or users in this the server"""
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
                "Removed {roles} from the DJ roles and {users} from the DJ users, as well as {ints} from both"
            ).format(
                roles=humanize_list([r.mention for r in roles]),
                users=humanize_list([u.mention for u in users]),
                ints=humanize_list([str(i) for i in ints]),
            )
        elif roles and users:
            message = _("Removed {roles} from the DJ roles and {users} from the DJ users").format(
                roles=humanize_list([r.mention for r in roles]), users=humanize_list([u.mention for u in users])
            )
        if roles:
            if not message:
                message = _("Removed {roles} from the DJ roles").format(roles=humanize_list([r.mention for r in roles]))
            await config.bulk_remove_dj_roles(*roles)
        if users:
            if not message:
                message = _("Removed {users} from the DJ users").format(users=humanize_list([u.mention for u in users]))
            await config.bulk_remove_dj_users(*users)
        if ints:
            if not message:
                message = _("Removed {ints} from the DJ roles and users").format(
                    ints=humanize_list([str(u) for u in users])
                )
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
            message = _("Removed `{id}` from the DJ roles and users").format(id=role_or_user)
        elif isinstance(role_or_user, discord.Role):
            message = _("Removed {role} from the DJ roles").format(role=role_or_user.mention)
            await config.remove_from_dj_roles(role_or_user)
        else:
            message = _("Removed {user} from the DJ users").format(user=role_or_user.mention)
            await config.remove_from_dj_users(role_or_user)
        return message

    @command_playerset_server_dj.command(name="list")
    async def command_playerset_server_dj_list(self, context: PyLavContext) -> None:
        """List the DJ roles and users for the server"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        async def role_sorter(role: discord.Role | int) -> float:
            return float("-inf") if isinstance(role, int) else role.position

        async def user_sorter(user: discord.Member | int) -> float:
            return float("-inf") if isinstance(user, int) else user.top_role.position

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        dj_roles = {
            (role_object if (role_object := context.guild.get_role(role)) else role)
            for role in await config.fetch_dj_roles()
        }
        dj_roles = await heapq.nlargest(asyncstdlib.iter(dj_roles), key=role_sorter, n=len(dj_roles))
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
        dj_user = await heapq.nlargest(asyncstdlib.iter(dj_user), key=user_sorter, n=len(dj_user))
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
                    description=_("There are no DJ roles or users set in {server}").format(server=context.guild.name),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        string = ""

        pages = []
        if dj_roles_string_list:
            string += EightBitANSI.paint_yellow(_("DJ Roles"), bold=True, underline=True)
            for line in dj_roles_string_list:
                if len(string) + len(line) > 3000:
                    pages.append(string)
                    string = ""
                    string += EightBitANSI.paint_yellow(_("DJ Roles"), bold=True, underline=True)
                string += f"\n{line}"

        if dj_user_string_list:
            if string:
                string += "\n\n"
            string += EightBitANSI.paint_yellow(_("DJ Users"), bold=True, underline=True)
            for line in dj_user_string_list:
                if len(string) + len(line) > 3000:
                    pages.append(string)
                    string = ""
                    string += EightBitANSI.paint_yellow(_("DJ Users"), bold=True, underline=True)
                string += f"\n{line}"
        if string:
            pages.append(string)
        await context.send_interactive(messages=pages, box_lang="ansi", embed=True)  # type: ignore

    @command_playerset_server_dj.command(name="clear")
    async def command_playerset_server_dj_clear(self, context: PyLavContext) -> None:
        """Clear the DJ roles and users for the server"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        config = self.pylav.player_config_manager.get_config(context.guild.id)
        await config.dj_roles_reset()
        await config.dj_users_reset()

        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Cleared the DJ roles and users for {server}").format(server=context.guild.name),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="vol", aliases=["volume"])
    async def command_playerset_server_volume(self, context: PyLavContext, volume: int) -> None:
        """Set the maximum volume a user can set"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if volume > 1000:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Volume must be less than 1000"), messageable=context
                ),
                ephemeral=True,
            )
            return
        elif volume < 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Volume must be greater than 0"), messageable=context
                ),
                ephemeral=True,
            )
            return

        if volume > await self.pylav.player_manager.global_config.fetch_max_volume():
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("Volume must be between 0 and {volume}%").format(
                        volume=humanize_number(await self.pylav.player_manager.global_config.fetch_max_volume())
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
                    description=_("Volume must be between 0 and {volume}%").format(volume=humanize_number(max_volume)),
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
                description=_("Max volume set to {volume}%").format(volume=humanize_number(volume)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="deafen", aliases=["deaf"])
    async def command_playerset_server_deafen(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should deafen itself when playing"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.pylav.player_manager.global_config.fetch_self_deaf() is True:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("My owner told me to always deafen myself"),
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
                description=_("Deafen set to {deafen}").format(deafen=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="autoshuffle")
    async def command_playerset_server_autoshuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should shuffle the queue after every new song added"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if await self.pylav.player_manager.global_config.fetch_auto_shuffle() is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("Auto-Shuffle is globally disabled"), messageable=context
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
                description=_("Auto-Shuffle set to {shuffle}").format(
                    shuffle=_("Enabled") if toggle else _("Disabled")
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="shuffle")
    async def command_playerset_server_shuffle(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether [botname] should allow users to shuffle the queue"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if (await self.pylav.player_manager.global_config.fetch_shuffle()) is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("Shuffle is globally disabled"),
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
                description=_("Shuffle set to {shuffle}").format(shuffle=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="auto")
    async def command_playerset_server_auto(self, context: PyLavContext, toggle: bool) -> None:
        """Set whether the bot should automatically play songs when the queue is empty"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if await self.pylav.player_manager.global_config.fetch_auto_play() is False:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("Auto-Play is globally disabled"),
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
                description=_("Auto-Play set to {auto}").format(auto=_("Enabled") if toggle else _("Disabled")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="dc")
    async def command_playerset_server_dc(self, context: PyLavContext) -> None:
        """Set whether the bot should disconnect from the voice channel"""

    @command_playerset_server.command(name="empty")
    async def command_playerset_server_dc_empty(
        self,
        context: PyLavContext,  # noqa
        toggle: bool,  # noqa
        *,
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice channel when the queue is empty.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice channel when the queue is empty.
            - `<duration>`: How longer after the queue is empty should the player be disconnected. Default is 60
            seconds.
            Accepts seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be
            given in seconds)
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
                        "Disconnect when the queue finished is globally enabled "
                        "and players will be disconnected after {delta}"
                    ).format(delta=humanize_timedelta(timedelta=datetime.timedelta(seconds=global_timer))),
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
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}").format(duration=timedelta_str)
        else:
            extras = ""
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Disconnect from voice channel when queue is empty set to {empty}{extras}").format(
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
        after: TimedeltaConverter(default_unit="seconds", minimum=datetime.timedelta(seconds=60)) = None,  # noqa
    ) -> None:
        """Set whether the bot should disconnect from the voice channel when alone.

        Arguments:
            - `<toggle>`: Whether the bot should disconnect from the voice channel when it detects that it is
            alone.
            - `<duration>`: How longer after detecting should the player be disconnected. Default is 60 seconds.
            Accepts seconds, minutes, hours, days, weeks (if no unit is specified, the duration is assumed to be
            given in seconds)
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
                        "Disconnect when alone is globally enabled and players will be disconnected after {delta}"
                    ).format(delta=humanize_timedelta(timedelta=datetime.timedelta(seconds=global_timer))),
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
        if after:
            timedelta_str = humanize_timedelta(timedelta=after)
            extras = _(" and players will be disconnected after {duration}").format(duration=timedelta_str)
        else:
            extras = ""

        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("Disconnect from voice channel when alone set to {empty}{extras}").format(
                    empty=_("Enabled") if toggle else _("Disabled"), extras=extras
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.command(name="playlist")
    async def command_playerset_server_playlist(self, context: PyLavContext, *, playlist: PlaylistConverter) -> None:
        """Sets the Auto-Play playlist"""
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
                description=_("Auto-Play playlist set to {playlist}").format(
                    playlist=bold(await playlist.fetch_name())
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server.group(name="lock")
    async def command_playerset_server_lock(self, context: PyLavContext):
        """Set the channel locks"""

    @command_playerset_server_lock.command(name="commands")
    async def command_playerset_server_lock_commands(
        self, context: PyLavContext, *, channel: discord.TextChannel | discord.Thread | discord.VoiceChannel = None
    ):
        """Set the channel lock for commands"""

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
                        "I don't have permission to send message or send embed links or read messages in {channel}"
                    ).format(channel=channel.mention),
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
                    description=_("I will only listen to commands in {channel}").format(channel=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_("I will listen to commands in all channels I can see"),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_playerset_server_lock.command(name="voice", aliases=["vc"])
    async def command_playerset_server_lock_vc(self, context: PyLavContext, *, channel: discord.VoiceChannel = None):
        """Set the channel lock for voice channels"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if channel is not None and not (
            (permission := channel.permissions_for(context.me)) and permission.connect and permission.speak
        ):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I don't have permission to connect or speak in {channel}").format(
                        channel=channel.mention
                    ),
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
                    description=_("I will only be allowed to join {channel}").format(channel=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await context.send(
            embed=await self.pylav.construct_embed(description=_("I'm free to join any VC"), messageable=context),
            ephemeral=True,
        )
