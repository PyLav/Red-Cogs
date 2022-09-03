from __future__ import annotations

import contextlib
import shutil
from io import StringIO
from pathlib import Path

import discord
import rich
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

from pylav.types import CogT, InteractionT
from pylav.utils import PyLavContext

_ = Translator("PyLavConfigurator", Path(__file__))


class EmbedGenerator:
    def __init__(self, cog: CogT, context: PyLavContext):
        self.cog = cog
        self.context = context
        self.console = rich.console.Console(
            color_system="standard",
            emoji=True,
            file=StringIO(),
            force_terminal=True,
            force_interactive=False,
            highlight=True,
            markup=True,
            width=53,
        )

    async def generate_pylav_config_embed(self) -> discord.Embed:
        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        enabled = _("Enabled")
        disabled = _("Disabled")
        pylav_config = await self.cog.lavalink.lib_db_manager.get_config().fetch_all()
        table = rich.table.Table()
        table.add_column(_("PyLav Config"), justify="left")
        table.add_column(_("Value"), justify="left")
        table.add_row(
            _("Use Managed Node"),
            enabled if pylav_config["enable_managed_node"] else disabled,
            style="green" if pylav_config["enable_managed_node"] else "red",
        )
        table.add_row(
            _("Auto Update\nManaged Node"),
            enabled if pylav_config["auto_update_managed_nodes"] else disabled,
            style="green" if pylav_config["auto_update_managed_nodes"] else "red",
        )
        table.add_row(
            _("Change Bot activity"),
            enabled if pylav_config["update_bot_activity"] else disabled,
            style="green" if pylav_config["update_bot_activity"] else "red",
        )
        table.add_row(
            _("Use Bundled\nPyLav Nodes"),
            enabled if pylav_config["use_bundled_pylav_external"] else disabled,
            style="green" if pylav_config["use_bundled_pylav_external"] else "red",
        )
        table.add_row(
            _("Use Bundled\nlava.link Nodes"),
            enabled if pylav_config["use_bundled_lava_link_external"] else disabled,
            style="green" if pylav_config["use_bundled_lava_link_external"] else "red",
        )

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
        )

    async def generate_global_player_config_embed(self) -> discord.Embed:
        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        enabled = _("Enabled")
        disabled = _("Disabled")
        global_config = await self.cog.lavalink.player_config_manager.get_global_config().fetch_all()

        table = rich.table.Table()

        table.add_column(_("Global Player Config"), justify="left")
        table.add_column(_("Value"), justify="left")
        table.add_row(_("Volume"), str(global_config["volume"]), style="cyan")
        table.add_row(_("Maximum Volume"), str(global_config["max_volume"]), style="cyan")
        table.add_row(
            _("AutoPlay"),
            enabled if global_config["auto_play"] else disabled,
            style="green" if global_config["auto_play"] else "red",
        )
        table.add_row(
            _("Shuffling"),
            enabled if global_config["shuffle"] else disabled,
            style="green" if global_config["shuffle"] else "red",
        )
        table.add_row(
            _("Auto Shuffle"),
            enabled if global_config["auto_shuffle"] else disabled,
            style="green" if global_config["auto_shuffle"] else "red",
        )
        table.add_row(
            _("Auto Deafen"),
            enabled if global_config["self_deaf"] else disabled,
            style="green" if global_config["self_deaf"] else "red",
        )
        table.add_row(
            _("Auto Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=global_config["empty_queue_dc"].time)
            if global_config["empty_queue_dc"].enabled
            else disabled,
            style="green" if global_config["empty_queue_dc"].enabled else "red",
        )
        table.add_row(
            _("Auto Alone Pause"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=global_config["alone_pause"].time)
            if global_config["alone_pause"].enabled
            else disabled,
            style="green" if global_config["alone_pause"].enabled else "red",
        )
        table.add_row(
            _("Auto Alone Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=global_config["alone_dc"].time)
            if global_config["alone_dc"].enabled
            else disabled,
            style="green" if global_config["alone_dc"].enabled else "red",
        )

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
        )

    async def generate_context_player_config_embed(self) -> discord.Embed:
        if not self.context.guild:
            return await self.cog.lavalink.construct_embed(
                messageable=self.context,
                description=_("You need to be in a server to be able to show this page."),
            )
        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        enabled = _("Enabled")
        disabled = _("Disabled")

        ac_max_volume = await self.cog.lavalink.player_config_manager.get_max_volume(self.context.guild.id)
        ac_volume = await self.cog.lavalink.player_config_manager.get_volume(self.context.guild.id)
        ac_alone_dc = await self.cog.lavalink.player_config_manager.get_alone_dc(self.context.guild.id)
        ac_alone_pause = await self.cog.lavalink.player_config_manager.get_alone_pause(self.context.guild.id)
        ac_empty_queue_dc = await self.cog.lavalink.player_config_manager.get_empty_queue_dc(self.context.guild.id)
        ac_shuffle = await self.cog.lavalink.player_config_manager.get_shuffle(self.context.guild.id)
        ac_auto_shuffle = await self.cog.lavalink.player_config_manager.get_auto_shuffle(self.context.guild.id)
        ac_self_deaf = await self.cog.lavalink.player_config_manager.get_self_deaf(self.context.guild.id)
        ac_auto_play = await self.cog.lavalink.player_config_manager.get_auto_play(self.context.guild.id)

        table = rich.table.Table()

        table.add_column(_("Context Player Config"), justify="left")
        table.add_column(_("Value"), justify="left")
        table.add_row(_("Volume"), str(ac_volume), style="cyan")
        table.add_row(_("Maximum Volume"), str(ac_max_volume), style="cyan")
        table.add_row(_("AutoPlay"), enabled if ac_auto_play else disabled, style="green" if ac_auto_play else "red")
        table.add_row(_("Shuffling"), enabled if ac_shuffle else disabled, style="green" if ac_shuffle else "red")
        table.add_row(
            _("Auto Shuffle"), enabled if ac_auto_shuffle else disabled, style="green" if ac_auto_shuffle else "red"
        )
        table.add_row(_("Auto Deafen"), enabled if ac_self_deaf else disabled, style="green" if ac_self_deaf else "red")
        table.add_row(
            _("Auto Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=ac_empty_queue_dc.time)
            if ac_empty_queue_dc.enabled
            else disabled,
            style="green" if ac_empty_queue_dc.enabled else "red",
        )
        table.add_row(
            _("Auto Alone Pause"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=ac_alone_pause.time)
            if ac_alone_pause.enabled
            else disabled,
            style="green" if ac_alone_pause.enabled else "red",
        )
        table.add_row(
            _("Auto Alone Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=ac_alone_dc.time)
            if ac_alone_dc.enabled
            else disabled,
            style="green" if ac_alone_dc.enabled else "red",
        )

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
        )

    async def generate_server_player_config_embed(self) -> discord.Embed:
        if not self.context.guild:
            return await self.cog.lavalink.construct_embed(
                messageable=self.context,
                description=_("You need to be in a server to be able to show this page."),
            )

        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        enabled = _("Enabled")
        disabled = _("Disabled")

        config = await self.cog.lavalink.player_config_manager.get_config(self.context.guild.id).fetch_all()

        table = rich.table.Table()

        table.add_column(_("Server Player Config"), justify="left")
        table.add_column(_("Value"), justify="left")
        dj_user_str = (
            "\n".join(
                [
                    discord.utils.escape_markdown(str(self.context.guild.get_member(user) or user))
                    for user in config["dj_users"]
                ]
            )
            if len(config["dj_users"]) <= 5
            else _("Too many to show ({count})").format(count=len(config["dj_users"]))
        )
        dj_role_str = (
            "\n".join(
                [
                    discord.utils.escape_markdown(str(self.context.guild.get_role(role) or role))
                    for role in config["dj_roles"]
                ]
            )
            if len(config["dj_roles"]) <= 5
            else _("Too many to show ({count})").format(count=len(config["dj_roles"]))
        )
        table.add_row(_("Volume"), str(config["volume"]), style="cyan")
        table.add_row(_("Maximum Volume"), str(config["max_volume"]), style="cyan")
        table.add_row(
            _("AutoPlay"),
            enabled if config["auto_play"] else disabled,
            style="green" if config["auto_play"] else "red",
        )
        table.add_row(
            _("AutoPlay Playlist"),
            str(config["auto_play_playlist_id"]),
            style="green" if config["auto_play"] else "red",
        )
        table.add_row(
            _("Loop track"),
            enabled if config["repeat_current"] else disabled,
            style="green" if config["repeat_current"] else "red",
        )
        table.add_row(
            _("Loop Queue"),
            enabled if config["repeat_queue"] else disabled,
            style="green" if config["repeat_queue"] else "red",
        )
        table.add_row(
            _("Shuffling"),
            enabled if config["shuffle"] else disabled,
            style="green" if config["shuffle"] else "red",
        )
        table.add_row(
            _("Auto Shuffle"),
            enabled if config["auto_shuffle"] else disabled,
            style="green" if config["auto_shuffle"] else "red",
        )
        table.add_row(
            _("Auto Deafen"),
            enabled if config["self_deaf"] else disabled,
            style="green" if config["self_deaf"] else "red",
        )
        table.add_row(
            _("Auto Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["empty_queue_dc"].time)
            if config["empty_queue_dc"].enabled
            else disabled,
            style="green" if config["empty_queue_dc"].enabled else "red",
        )
        table.add_row(
            _("Auto Alone Pause"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["alone_pause"].time)
            if config["alone_pause"].enabled
            else disabled,
            style="green" if config["alone_pause"].enabled else "red",
        )
        table.add_row(
            _("Auto Alone Disconnect"),
            _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["alone_dc"].time)
            if config["alone_dc"].enabled
            else disabled,
            style="green" if config["alone_dc"].enabled else "red",
        )
        table.add_row(
            _("Forced Voice Channel"),
            str(config["forced_channel_id"]) if config["forced_channel_id"] != 0 else _("None"),
            style="green" if config["forced_channel_id"] != 0 else "red",
        )
        table.add_row(
            _("Forced Command Channel"),
            str(config["text_channel_id"]) if config["text_channel_id"] != 0 else _("None"),
            style="green" if config["text_channel_id"] != 0 else "red",
        )
        table.add_row(
            _("Forced Notification Channel"),
            str(config["notify_channel_id"]) if config["notify_channel_id"] != 0 else _("None"),
            style="green" if config["notify_channel_id"] != 0 else "red",
        )
        table.add_row(_("DJ Users"), dj_user_str, style="green" if config["dj_users"] else "red")
        table.add_row(_("DJ Roles"), dj_role_str, style="green" if config["dj_roles"] else "red")

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
        )

    async def generate_playlist_tasks_embed(self) -> discord.Embed:
        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        pylav_config = await self.cog.lavalink.lib_db_manager.get_config().fetch_all()

        table = rich.table.Table()

        table.add_column(_("Playlist Tasks"), justify="left")
        table.add_column(_("Date and Time (UTC)"), justify="left")
        table.add_row(
            _("Next Bundled\nPlaylist Update"),
            pylav_config["next_execution_update_bundled_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            style="blue",
        )
        table.add_row(
            _("Next Bundled External\nPlaylist Update"),
            pylav_config["next_execution_update_bundled_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            style="blue",
        )
        table.add_row(
            _("Next External\nPlaylist Update"),
            pylav_config["next_execution_update_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            style="blue",
        )

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
        )

    async def generate_pylav_paths_embed(self) -> discord.Embed:
        if not await self.cog.bot.is_owner(self.context.author):
            return await self.cog.lavalink.construct_embed(
                messageable=self.context,
                description=_("You need to be the bot owner to be able to show this page."),
            )

        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        pylav_config = await self.cog.lavalink.lib_db_manager.get_config().fetch_all()

        data = [
            (_("Config Folder"), "\u001b[35m" + pylav_config["config_folder"] + "\u001b[0m"),
            (_("Local Tracks"), "\u001b[35m" + pylav_config["localtrack_folder"] + "\u001b[0m"),
            (
                _("Java Executable"),
                (
                    "\u001b[35m" + jpath
                    if (jpath := shutil.which(pylav_config["java_path"]))
                    else "\u001b[31m" + _("Not Found") + "\u001b[0m"
                ),
            ),
        ]

        return await self.cog.lavalink.construct_embed(
            description=box(tabulate(data, headers=(_("Paths"), _("Path")), tablefmt="plain"), lang="ansi"),
            messageable=self.context,
        )

    async def generate_managed_node_config_embed(self) -> discord.Embed:

        self.console.clear()
        self.console.file.truncate(0)
        self.console.file.seek(0)

        enabled = _("Enabled")
        disabled = _("Disabled")

        table = rich.table.Table()
        build_date, build_time = self.cog.lavalink.managed_node_controller._buildtime.split(" ", 1)
        build_data = build_date.split("/")
        build_date = f"{build_data[2]}/{build_data[1]}/{build_data[0]}\n{build_time}"

        table.add_column(_("Managed Node Config"), justify="left", style="green")
        table.add_column(_("Value"), justify="left")
        table.add_row(_("Java"), self.cog.lavalink.managed_node_controller._jvm, style="blue")
        table.add_row(_("Lavaplayer"), self.cog.lavalink.managed_node_controller._lavaplayer, style="blue")
        table.add_row(_("Lavalink Branch"), self.cog.lavalink.managed_node_controller._lavalink_branch, style="blue")
        table.add_row(_("Lavalink Version"), self.cog.lavalink.managed_node_controller._version, style="blue")
        table.add_row(_("Lavalink Build"), str(self.cog.lavalink.managed_node_controller._lavalink_build), style="blue")
        table.add_row(_("Build Time"), build_date, style="blue")
        table.add_row(_("Commit"), self.cog.lavalink.managed_node_controller._commit, style="blue")
        table.add_row(
            _("Auto Update"),
            enabled if self.cog.lavalink.managed_node_controller._auto_update else disabled,
            style="green" if self.cog.lavalink.managed_node_controller._auto_update else "red",
        )

        self.console.print(table, overflow="fold", crop=True)
        description = self.console.file.getvalue()
        return await self.cog.lavalink.construct_embed(
            description=box(description, lang="ansi"), messageable=self.context
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
            return await self.cog.lavalink.construct_embed(
                messageable=self.context,
                description=_("Select an option from the dropdown menu below."),
            )


class InfoSelector(discord.ui.Select):
    def __init__(
        self,
        cog: CogT,
        context: PyLavContext,
        options: list[discord.SelectOption],
    ):

        super().__init__(min_values=1, max_values=1, options=options, placeholder=_("Pick an option to view"))
        self.cog = cog
        self.embed_maker = EmbedGenerator(cog=cog, context=context)

    async def callback(self, interaction: InteractionT):
        await interaction.response.defer()
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option")
                ),
                ephemeral=True,
            )
            return
        embed_key = self.values[0]
        embed = await self.embed_maker.get_embed(key=embed_key)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self.view)
        else:
            await interaction.edit_original_response(embed=embed, view=self.view)


class InfoView(discord.ui.View):
    def __init__(self, cog: CogT, context: PyLavContext, options: list[discord.SelectOption]):
        super().__init__(timeout=180.0)
        self.delete_after_timeout = True
        self.current_page = 0
        self._running = True
        self.bot = cog.bot
        self.cog = cog
        self.context = context
        self.author = context.author
        self.selector = InfoSelector(cog=cog, context=context, options=options)
        self.add_item(self.selector)

    async def interaction_check(self, interaction: InteractionT):
        """Just extends the default reaction_check to use owner_ids"""
        if (not await self.bot.allowed_by_whitelist_blacklist(interaction.user, guild=interaction.guild)) or (
            self.author and (interaction.user.id != self.author.id)
        ):
            await interaction.response.send_message(
                content=_("You are not authorized to interact with this"), ephemeral=True
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
