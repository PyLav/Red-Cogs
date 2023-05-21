from __future__ import annotations

import contextlib
from pathlib import Path

import discord
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

from pylav._internals.functions import get_true_path
from pylav.constants.config import IN_CONTAINER
from pylav.core.context import PyLavContext
from pylav.extension.bundled_node import LAVALINK_DOWNLOAD_DIR
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.type_hints.bot import DISCORD_COG_TYPE, DISCORD_INTERACTION_TYPE

_ = Translator("PyLavConfigurator", Path(__file__))


class EmbedGenerator:
    def __init__(self, cog: DISCORD_COG_TYPE, context: PyLavContext):
        self.cog = cog
        self.context = context

    async def generate_pylav_config_embed(self) -> discord.Embed:
        enabled = EightBitANSI.paint_green(_("Enabled"), bold=True, italic=True)
        disabled = EightBitANSI.paint_red(_("Disabled"), bold=True, italic=True)
        pylav_config = await self.cog.pylav.lib_db_manager.get_config().fetch_all()
        data = [
            (
                EightBitANSI.paint_white(_("Use Managed Node")),
                enabled if pylav_config["enable_managed_node"] and not IN_CONTAINER else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Auto Update\nManaged Node")),
                enabled if pylav_config["auto_update_managed_nodes"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Change Bot activity")),
                enabled if pylav_config["update_bot_activity"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Use Bundled\nPyLav Nodes")),
                enabled if pylav_config["use_bundled_pylav_external"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Use Bundled\nlava.link Nodes")),
                disabled,
            ),
        ]
        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("PyLav Settings"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Value"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_global_player_config_embed(self) -> discord.Embed:
        enabled = EightBitANSI.paint_green(_("Enabled"), bold=True, italic=True)
        disabled = EightBitANSI.paint_red(_("Disabled"), bold=True, italic=True)
        global_config = await self.cog.pylav.player_config_manager.get_global_config().fetch_all()

        (EightBitANSI.paint_white(_("Volume")), EightBitANSI.paint_cyan(global_config["volume"]))

        auto_empty_dc_message = disabled
        if global_config["empty_queue_dc"].enabled:
            match global_config["empty_queue_dc"].time:
                case 0:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_empty_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=global_config["empty_queue_dc"].time,
                    )
            auto_empty_dc_message = EightBitANSI.paint_green(auto_empty_dc_message)

        auto_alone_dc_message = disabled
        if global_config["alone_dc"].enabled:
            match global_config["alone_dc"].time:
                case 0:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=global_config["alone_dc"].time,
                    )
            auto_alone_dc_message = EightBitANSI.paint_green(auto_alone_dc_message)

        auto_alone_pause_message = disabled
        if global_config["alone_pause"].enabled:
            match global_config["alone_pause"].time:
                case 0:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_pause_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=global_config["alone_pause"].time,
                    )
            auto_alone_pause_message = EightBitANSI.paint_green(auto_alone_pause_message)

        data = [
            (EightBitANSI.paint_white(_("Maximum Volume")), EightBitANSI.paint_cyan(global_config["max_volume"])),
            (
                EightBitANSI.paint_white(_("AutoPlay")),
                enabled if global_config["auto_play"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Shuffling")),
                enabled if global_config["shuffle"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Auto Shuffle")),
                enabled if global_config["auto_shuffle"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Auto Deafen")),
                enabled if global_config["self_deaf"] else disabled,
            ),
            (EightBitANSI.paint_white(_("Auto Disconnect")), auto_empty_dc_message),
            (EightBitANSI.paint_white(_("Auto Alone Pause")), auto_alone_pause_message),
            (EightBitANSI.paint_white(_("Auto Alone Disconnect")), auto_alone_dc_message),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Global Settings"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Value"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_context_player_config_embed(self) -> discord.Embed:
        if not self.context.guild:
            return await self.cog.pylav.construct_embed(
                messageable=self.context,
                description=_("You need to be on a server to show this page."),
            )

        enabled = EightBitANSI.paint_green(_("Enabled"), bold=True, italic=True)
        disabled = EightBitANSI.paint_red(_("Disabled"), bold=True, italic=True)

        ac_max_volume = await self.cog.pylav.player_config_manager.get_max_volume(self.context.guild.id)
        ac_volume = await self.cog.pylav.player_config_manager.get_volume(self.context.guild.id)
        ac_alone_dc = await self.cog.pylav.player_config_manager.get_alone_dc(self.context.guild.id)
        ac_alone_pause = await self.cog.pylav.player_config_manager.get_alone_pause(self.context.guild.id)
        ac_empty_queue_dc = await self.cog.pylav.player_config_manager.get_empty_queue_dc(self.context.guild.id)
        ac_shuffle = await self.cog.pylav.player_config_manager.get_shuffle(self.context.guild.id)
        ac_auto_shuffle = await self.cog.pylav.player_config_manager.get_auto_shuffle(self.context.guild.id)
        ac_self_deaf = await self.cog.pylav.player_config_manager.get_self_deaf(self.context.guild.id)
        ac_auto_play = await self.cog.pylav.player_config_manager.get_auto_play(self.context.guild.id)

        auto_empty_dc_message = disabled
        if ac_empty_queue_dc.enabled:
            match ac_alone_pause.time:
                case 0:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_empty_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=ac_empty_queue_dc.time,
                    )
            auto_empty_dc_message = EightBitANSI.paint_green(auto_empty_dc_message)

        auto_alone_dc_message = disabled
        if ac_alone_dc.enabled:
            match ac_alone_pause.time:
                case 0:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=ac_alone_dc.time,
                    )
            auto_alone_dc_message = EightBitANSI.paint_green(auto_alone_dc_message)

        auto_alone_pause_message = disabled
        if ac_alone_pause.enabled:
            match ac_alone_pause.time:
                case 0:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_pause_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=ac_alone_pause.time,
                    )
            auto_alone_pause_message = EightBitANSI.paint_green(auto_alone_pause_message)

        data = [
            (EightBitANSI.paint_white(_("Volume")), EightBitANSI.paint_cyan(ac_volume)),
            (EightBitANSI.paint_white(_("Maximum Volume")), EightBitANSI.paint_cyan(ac_max_volume)),
            (
                EightBitANSI.paint_white(_("AutoPlay")),
                EightBitANSI.paint_green(enabled) if ac_auto_play else EightBitANSI.paint_red(disabled),
            ),
            (EightBitANSI.paint_white(_("Shuffling")), enabled if ac_shuffle else disabled),
            (EightBitANSI.paint_white(_("Auto Shuffle")), enabled if ac_auto_shuffle else disabled),
            (EightBitANSI.paint_white(_("Auto Deafen")), enabled if ac_self_deaf else disabled),
            (EightBitANSI.paint_white(_("Auto Empty Disconnect")), auto_empty_dc_message),
            (EightBitANSI.paint_white(_("Auto Alone Pause")), auto_alone_pause_message),
            (EightBitANSI.paint_white(_("Auto Alone Disconnect")), auto_alone_dc_message),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Context Player Settings"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Value"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_server_player_config_embed(self) -> discord.Embed:  # sourcery skip: low-code-quality
        if not self.context.guild:
            return await self.cog.pylav.construct_embed(
                messageable=self.context,
                description=_("You need to be in a server to be able to show this page."),
            )

        enabled = EightBitANSI.paint_green(_("Enabled"), bold=True, italic=True)
        disabled = EightBitANSI.paint_red(_("Disabled"), bold=True, italic=True)

        config = await self.cog.pylav.player_config_manager.get_config(self.context.guild.id).fetch_all()

        dj_user_str = (
            "\n".join(
                [
                    EightBitANSI.colorize(
                        discord.utils.escape_markdown(str(member_obj)),
                        color=EightBitANSI.closest_color(*member_obj.color.to_rgb()),
                    )
                    if (member_obj := self.context.guild.get_member(user))
                    else EightBitANSI.paint_green(user)
                    for user in config["dj_users"]
                ]
            )
            if len(config["dj_users"]) <= 5
            else _("Too many entries to show ({number_of_users_variable_do_not_translate})").format(
                number_of_users_variable_do_not_translate=len(config["dj_users"])
            )
        )

        dj_role_str = (
            "\n".join(
                [
                    EightBitANSI.colorize(
                        discord.utils.escape_markdown(str(role_obj)),
                        color=EightBitANSI.closest_color(*role_obj.color.to_rgb()),
                    )
                    if (role_obj := self.context.guild.get_role(role))
                    else EightBitANSI.paint_green(role)
                    for role in config["dj_roles"]
                ]
            )
            if len(config["dj_roles"]) <= 5
            else _("Too many entries to show ({number_of_roles_variable_do_not_translate})").format(
                number_of_roles_variable_do_not_translate=len(config["dj_roles"])
            )
        )
        if len(config["dj_users"]) == 0:
            dj_user_str = EightBitANSI.paint_red(_("None"))
        else:
            dj_user_str = EightBitANSI.paint_green(dj_user_str)

        if len(config["dj_roles"]) == 0:
            dj_role_str = EightBitANSI.paint_red(_("None"))
        else:
            dj_role_str = EightBitANSI.paint_green(dj_role_str)

        auto_empty_dc_message = disabled
        if config["empty_queue_dc"].enabled:
            match config["empty_queue_dc"].time:
                case 0:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_empty_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_empty_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=config["empty_queue_dc"].time,
                    )
            auto_empty_dc_message = EightBitANSI.paint_green(auto_empty_dc_message)

        auto_alone_dc_message = disabled
        if config["alone_dc"].enabled:
            match config["alone_dc"].time:
                case 0:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_dc_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_dc_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=config["alone_dc"].time,
                    )
            auto_alone_dc_message = EightBitANSI.paint_green(auto_alone_dc_message)

        auto_alone_pause_message = disabled
        if config["alone_pause"].enabled:
            match config["alone_pause"].time:
                case 0:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n0 seconds").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case 1:
                    auto_alone_pause_message = _("{enabled_variable_do_not_translate}\n1 second").format(
                        enabled_variable_do_not_translate=enabled,
                    )
                case __:
                    auto_alone_pause_message = _(
                        "{enabled_variable_do_not_translate}\n{setting_timer_variable_do_not_translate} seconds"
                    ).format(
                        enabled_variable_do_not_translate=enabled,
                        setting_timer_variable_do_not_translate=config["alone_pause"].time,
                    )
            auto_alone_pause_message = EightBitANSI.paint_green(auto_alone_pause_message)

        data = [
            (EightBitANSI.paint_white(_("Volume")), EightBitANSI.paint_cyan(config["volume"])),
            (EightBitANSI.paint_white(_("Maximum Volume")), EightBitANSI.paint_cyan(config["max_volume"])),
            (
                EightBitANSI.paint_white(_("AutoPlay")),
                enabled if config["auto_play"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("AutoPlay Playlist")),
                EightBitANSI.paint_green(config["auto_play_playlist_id"]) if config["auto_play"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Loop track")),
                enabled if config["repeat_current"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Loop Queue")),
                enabled if config["repeat_queue"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Shuffling")),
                enabled if config["shuffle"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Auto Shuffle")),
                enabled if config["auto_shuffle"] else disabled,
            ),
            (
                EightBitANSI.paint_white(_("Auto Deafen")),
                enabled if config["self_deaf"] else disabled,
            ),
            (EightBitANSI.paint_white(_("Auto Empty Disconnect")), auto_empty_dc_message),
            (EightBitANSI.paint_white(_("Auto Alone Pause")), auto_alone_pause_message),
            (EightBitANSI.paint_white(_("Auto Alone Disconnect")), auto_alone_dc_message),
            (
                EightBitANSI.paint_white(_("Forced Voice Channel")),
                EightBitANSI.paint_green(config["forced_channel_id"])
                if config["forced_channel_id"] != 0
                else EightBitANSI.paint_red(_("None")),
            ),
            (
                EightBitANSI.paint_white(_("Forced Command Channel")),
                EightBitANSI.paint_green(config["text_channel_id"])
                if config["text_channel_id"] != 0
                else EightBitANSI.paint_red(_("None")),
            ),
            (
                EightBitANSI.paint_white(_("Forced Notification Channel")),
                EightBitANSI.paint_green(config["notify_channel_id"])
                if config["notify_channel_id"] != 0
                else EightBitANSI.paint_red(_("None")),
            ),
            (EightBitANSI.paint_white(_("Disc Jockey Users")), dj_user_str),
            (EightBitANSI.paint_white(_("Disc Jockey Roles")), dj_role_str),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Server Player Settings"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Value"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_playlist_tasks_embed(self) -> discord.Embed:
        pylav_config = await self.cog.pylav.lib_db_manager.get_config().fetch_all()

        data = [
            (
                EightBitANSI.paint_white(_("Next Bundled\nPlaylist Update")),
                EightBitANSI.paint_blue(
                    pylav_config["next_execution_update_bundled_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC")
                ),
            ),
            (
                EightBitANSI.paint_white(_("Next Bundled External\nPlaylist Update")),
                EightBitANSI.paint_blue(
                    pylav_config["next_execution_update_bundled_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC")
                ),
            ),
            (
                EightBitANSI.paint_white(_("Next External\nPlaylist Update")),
                EightBitANSI.paint_blue(
                    pylav_config["next_execution_update_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC")
                ),
            ),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Playlist Tasks"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Date and Time (UTC)"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_pylav_paths_embed(self) -> discord.Embed:
        if not await self.cog.bot.is_owner(self.context.author):
            return await self.cog.pylav.construct_embed(
                messageable=self.context,
                description=_("Due to sensitive information, I can only show the contents of this page to my owner."),
            )

        pylav_config = await self.cog.pylav.lib_db_manager.get_config().fetch_all()

        data = [
            (EightBitANSI.paint_white(_("Settings Folder")), EightBitANSI.paint_magenta(pylav_config["config_folder"])),
            (
                EightBitANSI.paint_white(_("Local Tracks")),
                EightBitANSI.paint_magenta(pylav_config["localtrack_folder"]),
            ),
            (EightBitANSI.paint_white(_("Lavalink Folder")), (EightBitANSI.paint_magenta(LAVALINK_DOWNLOAD_DIR))),
            (
                EightBitANSI.paint_white(_("Java Executable")),
                (
                    EightBitANSI.paint_magenta(jpath)
                    if (jpath := get_true_path(pylav_config["java_path"]))
                    else EightBitANSI.paint_red(_("Not Found"))
                ),
            ),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Paths"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Path"), underline=True, bold=True),
                    ),
                    tablefmt="plain",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def generate_managed_node_config_embed(self) -> discord.Embed:
        enabled = EightBitANSI.paint_green(_("Enabled"), bold=True, italic=True)
        disabled = EightBitANSI.paint_red(_("Disabled"), bold=True, italic=True)
        # noinspection PyProtectedMember
        build_date, build_time = self.cog.pylav.managed_node_controller._buildtime.split(" ", 1)
        build_data = build_date.split("/")
        build_date = f"{build_data[2]}/{build_data[1]}/{build_data[0]}\n{build_time}"
        # noinspection PyProtectedMember
        data = [
            (
                EightBitANSI.paint_white(_("Java")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._jvm),
            ),
            (
                EightBitANSI.paint_white(_("Lavaplayer")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._lavaplayer),
            ),
            (
                EightBitANSI.paint_white(_("Lavalink Branch")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._lavalink_branch),
            ),
            (
                EightBitANSI.paint_white(_("Lavalink Version")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._version),
            ),
            (
                EightBitANSI.paint_white(_("Lavalink Build")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._lavalink_build),
            ),
            (EightBitANSI.paint_white(_("Build Time")), EightBitANSI.paint_blue(build_date)),
            (
                EightBitANSI.paint_white(_("Commit")),
                EightBitANSI.paint_blue(self.cog.pylav.managed_node_controller._commit),
            ),
            (
                EightBitANSI.paint_white(_("Auto Update")),
                enabled if await self.cog.pylav.managed_node_controller.should_auto_update() else disabled,
            ),
        ]

        return await self.cog.pylav.construct_embed(
            description=box(
                tabulate(
                    data,
                    headers=(
                        EightBitANSI.paint_yellow(_("Managed Node Settings"), underline=True, bold=True),
                        EightBitANSI.paint_yellow(_("Value"), underline=True, bold=True),
                    ),
                    tablefmt="fancy_grid",
                ),
                lang="ansi",
            ),
            messageable=self.context,
        )

    async def get_embed(self, key: str) -> discord.Embed:
        if key == "pylav_config":
            return await self.generate_pylav_config_embed()
        elif key == "global_player_config":
            return await self.generate_global_player_config_embed()
        elif key == "context_player_config":
            return await self.generate_context_player_config_embed()
        elif key == "server_player_config":
            return await self.generate_server_player_config_embed()
        elif key == "playlist_tasks":
            return await self.generate_playlist_tasks_embed()
        elif key == "pylav_paths":
            return await self.generate_pylav_paths_embed()
        elif key == "managed_node_config":
            return await self.generate_managed_node_config_embed()
        else:
            return await self.cog.pylav.construct_embed(
                messageable=self.context,
                description=_("Select an option from the dropdown menu below."),
            )


class InfoSelector(discord.ui.Select):
    def __init__(
        self,
        cog: DISCORD_COG_TYPE,
        context: PyLavContext,
        options: list[discord.SelectOption],
    ):
        super().__init__(
            min_values=1,
            max_values=1,
            options=options,
            placeholder=shorten_string(max_length=100, string=_("Pick an option to view")),
        )
        self.cog = cog
        self.embed_maker = EmbedGenerator(cog=cog, context=context)

    async def callback(self, interaction: DISCORD_INTERACTION_TYPE):
        await interaction.response.defer()
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.pylav.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
            return
        embed_key = self.values[0]
        embed = await self.embed_maker.get_embed(key=embed_key)
        await self.view.message.edit(embed=embed, view=self.view)


class InfoView(discord.ui.View):
    def __init__(self, cog: DISCORD_COG_TYPE, context: PyLavContext, options: list[discord.SelectOption]):
        super().__init__(timeout=180.0)
        self.delete_after_timeout = True
        self.message = None
        self.current_page = 0
        self._running = True
        self.bot = cog.bot
        self.cog = cog
        self.context = context
        self.author = context.author
        self.selector = InfoSelector(cog=cog, context=context, options=options)
        self.add_item(self.selector)

    async def interaction_check(self, interaction: DISCORD_INTERACTION_TYPE):
        """Just extends the default reaction_check to use owner_ids"""
        if (not await self.bot.allowed_by_whitelist_blacklist(interaction.user, guild=interaction.guild)) or (
            self.author and (interaction.user.id != self.author.id)
        ):
            await interaction.response.send_message(
                content=_("You are not authorized to interact with this."), ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self._running = False
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            if self.delete_after_timeout and not self.message.flags.ephemeral:
                await self.message.delete()
            else:
                await self.message.edit(view=None)

    async def send_initial_message(self):
        embed = await self.selector.embed_maker.get_embed(key="fallback")
        self.message = await self.context.send(embed=embed, view=self, ephemeral=True)
        return self.message

    async def prepare(self):
        return

    async def start(self):
        await self.send_initial_message()
