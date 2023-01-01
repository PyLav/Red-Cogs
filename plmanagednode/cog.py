from __future__ import annotations

import contextlib
import re
from pathlib import Path

import discord
import humanize
import ujson
from deepdiff import DeepDiff
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n, get_babel_locale
from redbot.core.utils.chat_formatting import bold, box, humanize_list, inline
from tabulate import tabulate

from pylav.constants.node import NODE_DEFAULT_SETTINGS
from pylav.core.client import Client
from pylav.core.context import PyLavContext
from pylav.extension.bundled_node import LAVALINK_DOWNLOAD_DIR
from pylav.extension.bundled_node.utils import get_jar_ram_actual, get_max_allocation_size
from pylav.helpers.format.ascii import EightBitANSI
from pylav.logging import getLogger
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

from plmanagednode.view import ConfigureGoogleAccountView, ConfigureHTTPProxyView, ConfigureIPRotationView

LOGGER = getLogger("PyLav.cog.ManagedNode")

_ = Translator("PyLavManagedNode", Path(__file__))


@cog_i18n(_)
class PyLavManagedNode(DISCORD_COG_TYPE_MIXIN):
    """Configure the managed Lavalink node used by PyLav"""

    __version__ = "1.0.0"
    lavalink: Client

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="plmanaged")
    @commands.is_owner()
    async def command_plmanaged(self, context: PyLavContext):
        """Configure the managed Lavalink node used by PyLav"""

    @command_plmanaged.command(name="version")
    async def command_plmanaged_version(self, context: PyLavContext) -> None:
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

    @command_plmanaged.command(name="update")
    async def command_plmanaged_update(self, context: PyLavContext, update: int = 0) -> None:
        """Update the managed Lavalink node"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        self.pylav.managed_node_controller._up_to_date = False
        upstream_data = await self.pylav.managed_node_controller.get_ci_latest_info()
        number = upstream_data["number"]
        # noinspection PyProtectedMember
        if number == await self.pylav._config.fetch_download_id():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The managed Lavalink node is already up to date."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if update == 0:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Your node is out of date, to update please run `{prefix}{command} 1`.").format(
                        prefix=context.clean_prefix,
                        command=self.command_plmanaged_update.qualified_name,
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        self.pylav.managed_node_controller._up_to_date = False
        # noinspection PyProtectedMember
        await self.pylav.managed_node_controller._download_jar(forced=True)

        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("The managed Lavalink node has been updated to version {version}.").format(
                    version=number,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged.command(name="toggle")
    async def command_plmanaged_toggle(self, context: PyLavContext) -> None:
        """Toggle the managed node on/off.

        Changes will be applied after restarting [botname].
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.pylav.lib_db_manager.get_config()
        current = await global_config.fetch_enable_managed_node()
        await global_config.update_enable_managed_node(not current)
        if current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("PyLav's managed node has been enabled.").format(prefix=context.clean_prefix),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("PyLav's managed node has been disabled.").format(prefix=context.clean_prefix),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged.command(name="updates")
    async def ccommand_plmanaged_updates(self, context: PyLavContext) -> None:
        """Toggle the managed node auto updates on/off.

        Changes will be applied after restarting [botname].
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.pylav.lib_db_manager.get_config()
        current = await global_config.fetch_auto_update_managed_nodes()
        await global_config.update_auto_update_managed_nodes(not current)

        if current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("PyLav's managed node auto updates have been enabled" "").format(
                        prefix=context.clean_prefix
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("PyLav's managed node auto updates have been disabled" "").format(
                        prefix=context.clean_prefix
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged.command(name="heapsize", aliases=["hs", "ram", "memory"])
    async def command_plmanaged_heapsize(self, context: PyLavContext, size: str):
        """Set the managed Lavalink node maximum heap-size.

        By default, this value is 2G of available RAM in the host machine represented by (65-1023M|1+G) (256M,
        256G for example)

        This value only represents the maximum amount of RAM allowed to be used at any given point, and does not mean
        that the managed Lavalink node will always use this amount of RAM.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        async def validate_input(arg: str):
            locale = f"{get_babel_locale()}"
            with contextlib.suppress(Exception):
                humanize.i18n.activate(locale)
            executable = await self.pylav.lib_db_manager.get_config().fetch_java_path()
            total_ram, is_64bit = get_max_allocation_size(executable)
            __, __, min_allocation_size, max_allocation_size = get_jar_ram_actual(executable)
            match = re.match(r"^(\d+)([MG])$", arg, flags=re.IGNORECASE)
            if not match:
                await context.send(
                    embed=await context.pylav.construct_embed(
                        description=_("Heap-size must be a valid measure of size, e.g. 256M, 256G"),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return 0
            input_in_bytes = int(match[1]) * 1024 ** (2 if match[2].lower() == "m" else 3)
            if input_in_bytes < min_allocation_size:
                await context.send(
                    embed=await context.pylav.construct_embed(
                        description=_(
                            "Heap-size must be at least 64M, however it is recommended to have it set to at least 1G"
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return 0
            elif input_in_bytes > max_allocation_size:
                if is_64bit:
                    await context.send(
                        embed=await context.pylav.construct_embed(
                            description=_(
                                "Heap-size must be less than your system RAM, "
                                "You currently have {ram_in_bytes} of RAM available"
                            ).format(ram_in_bytes=inline(humanize.naturalsize(total_ram))),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )

                else:
                    await context.send(
                        embed=await context.pylav.construct_embed(
                            description=_("Heap-size must be less than {limit} due to your system limitations").format(
                                limit=inline(humanize.naturalsize(total_ram))
                            )
                        ),
                        ephemeral=True,
                    )
                return 0
            return 1

        if not (await validate_input(size)):
            humanize.i18n.deactivate()
            return
        humanize.i18n.deactivate()
        size = size.upper()
        global_config = self.pylav.lib_db_manager.get_config()
        extras = await global_config.fetch_extras()
        extras["max_ram"] = size
        await global_config.update_extras(extras)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's heap-size set to {bytes}.").format(
                    bytes=inline(size),
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged.group(name="config")
    async def command_plmanaged_config(self, context: PyLavContext):
        """Change the managed node start up configs"""

    @command_plmanaged_config.command(name="host")
    async def command_plmanaged_config_host(self, context: PyLavContext, host: str):
        """Set the managed node host"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        data["server"]["host"] = host
        await config.update_yaml(data)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's host set to {host}.").format(
                    host=inline(host),
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.command(name="port")
    async def command_plmanaged_config_port(self, context: PyLavContext, port: int):
        """`Dangerous command` Set the managed Lavalink node's connection port.

        This port is the port the managed Lavalink node binds to, you should only change this if there is a
        conflict with the default port because you already have an application using port 2154 on this device.

        The value by default is `2154`.
        """
        if port < 1024 or port > 49151:
            return await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The port must be between 1024 and 49151"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        data["server"]["port"] = port
        await config.update_yaml(data)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's port set to {port}.").format(port=port, prefix=context.clean_prefix),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.group(name="plugins")
    async def command_plmanaged_config_plugins(self, context: PyLavContext):
        """Change the managed node plugins"""

    @command_plmanaged_config_plugins.command(name="disable")
    async def command_plmanaged_config_plugins_disable(
        self, context: PyLavContext, *, plugin: str
    ):  # sourcery skip: low-code-quality
        """Disabled one of the available plugins"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        plugin_str = plugin.lower()
        plugins = [
            "lavasrc-plugin",
            "skybot-lavalink-plugin",
            "sponsorblock-plugin",
            "lavalink-filter-plugin",
            "lava-xm-plugin",
        ]
        if plugin_str not in plugins:
            return await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The plugin must be one of the following: {plugins}").format(
                        plugins=inline(humanize_list(plugins))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        new_plugins = []
        plugin_files = []
        folder = LAVALINK_DOWNLOAD_DIR / "plugins"
        for plugin in data["lavalink"]["plugins"].copy():
            if plugin["dependency"].startswith("com.github.TopiSenpai.LavaSrc:lavasrc-plugin:"):
                if plugin_str != "lavasrc-plugin":
                    new_plugins.append(plugin)
                else:
                    filename = "lavasrc-plugin-"
                    plugin_files.extend(
                        [
                            x
                            async for x in folder.iterdir()
                            if x.name.startswith(filename) and x.suffix == ".jar" and x.is_file()
                        ]
                    )
            elif plugin["dependency"].startswith("com.dunctebot:skybot-lavalink-plugin:"):
                if plugin_str != "skybot-lavalink-plugin":
                    new_plugins.append(plugin)
                else:
                    filename = "skybot-lavalink-plugin-"
                    plugin_files.extend(
                        [
                            x
                            async for x in folder.iterdir()
                            if x.name.startswith(filename) and x.suffix == ".jar" and x.is_file()
                        ]
                    )
            elif plugin["dependency"].startswith("com.github.topisenpai:sponsorblock-plugin:"):
                if plugin_str != "sponsorblock-plugin":
                    new_plugins.append(plugin)
                else:
                    filename = "sponsorblock-plugin-"
                    plugin_files.extend(
                        [
                            x
                            async for x in folder.iterdir()
                            if x.name.startswith(filename) and x.suffix == ".jar" and x.is_file()
                        ]
                    )
            elif plugin["dependency"].startswith("com.github.esmBot:lava-xm-plugin:"):
                if plugin_str != "lava-xm-plugin":
                    new_plugins.append(plugin)
                else:
                    filename = "lava-xm-plugin-"
                    plugin_files.extend(
                        [
                            x
                            async for x in folder.iterdir()
                            if x.name.startswith(filename) and x.suffix == ".jar" and x.is_file()
                        ]
                    )
            elif plugin["dependency"].startswith("me.rohank05:lavalink-filter-plugin:"):
                if plugin_str != "lavalink-filter-plugin":
                    new_plugins.append(plugin)
                else:
                    filename = "lavalink-filter-plugin-"
                    plugin_files.extend(
                        [
                            x
                            async for x in folder.iterdir()
                            if x.name.startswith(filename) and x.suffix == ".jar" and x.is_file()
                        ]
                    )

        for file in plugin_files:
            try:
                await file.unlink()
            except Exception as exc:
                LOGGER.error("Failed to delete file %s", file, exc_info=exc)

        data["lavalink"]["plugins"] = new_plugins
        await config.update_yaml(data)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's plugin {plugin} disabled.").format(
                    plugin=inline(plugin_str),
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config_plugins.command(name="enable")
    async def command_plmanaged_config_plugins_enable(self, context: PyLavContext, *, plugin: str):
        """Enable one of the available plugins"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        plugin_str = plugin.lower()
        plugins = [
            "lavasrc-plugin",
            "skybot-lavalink-plugin",
            "sponsorblock-plugin",
            "lavalink-filter-plugin",
            "lava-xm-plugin",
        ]
        if plugin_str not in plugins:
            return await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The plugin must be one of the following: {plugins}").format(
                        plugins=inline(humanize_list(plugins))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        new_plugins = data["lavalink"]["plugins"].copy()

        for plugin in NODE_DEFAULT_SETTINGS["lavalink"]["plugins"]:
            if plugin["dependency"].startswith("com.github.TopiSenpai.LavaSrc:lavasrc-plugin:"):
                if plugin_str == "lavasrc-plugin":
                    new_plugins.append(plugin)
            elif plugin["dependency"].startswith("com.dunctebot:skybot-lavalink-plugin:"):
                if plugin_str == "skybot-lavalink-plugin":
                    new_plugins.append(plugin)
            elif plugin["dependency"].startswith("com.github.topisenpai:sponsorblock-plugin:"):
                if plugin_str == "sponsorblock-plugin":
                    new_plugins.append(plugin)
            elif plugin["dependency"].startswith("com.github.esmBot:lava-xm-plugin:"):
                if plugin_str == "lavalink-filter-plugin":
                    new_plugins.append(plugin)
            elif plugin["dependency"].startswith("me.rohank05:lavalink-filter-plugin:"):
                if plugin_str == "lava-xm-plugin":
                    new_plugins.append(plugin)

        data["lavalink"]["plugins"] = new_plugins
        await config.update_yaml(data)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's plugin {plugin} enabled.").format(
                    plugin=inline(plugin_str),
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config_plugins.command(name="update")
    async def command_plmanaged_config_plugins_update(self, context: PyLavContext):  # sourcery skip: low-code-quality
        """Update the managed node plugins"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        new_plugin_data = []
        _temp = set()
        for plugin in data["lavalink"]["plugins"].copy():
            dependency = ":".join(plugin["dependency"].split(":")[:-1])
            if dependency in _temp:
                continue
            _temp.add(dependency)
            if plugin["dependency"].startswith("com.github.TopiSenpai.LavaSrc:lavasrc-plugin:"):
                org = "TopiSenpai"
                repo = "LavaSrc"
                repository = "https://jitpack.io"
                dependency += ":"
            elif plugin["dependency"].startswith("com.dunctebot:skybot-lavalink-plugin:"):
                org = "DuncteBot"
                repo = "skybot-lavalink-plugin"
                repository = "https://m2.duncte123.dev/releases"
                dependency += ":"
            elif plugin["dependency"].startswith("com.github.topisenpai:sponsorblock-plugin:"):
                org = "Topis-Lavalink-Plugins"
                repo = "Sponsorblock-Plugin"
                repository = "https://jitpack.io"
                dependency += ":"
            elif plugin["dependency"].startswith("com.github.esmBot:lava-xm-plugin:"):
                org = "esmBot"
                repo = "lava-xm-plugin"
                repository = "https://jitpack.io"
                dependency += ":"
            elif plugin["dependency"].startswith("me.rohank05:lavalink-filter-plugin:"):
                org = "rohank05"
                repo = "lavalink-filter-plugin"
                repository = "https://jitpack.io"
                dependency += ":"
            else:
                continue
            release_data = await (
                await self.pylav.cached_session.get(
                    f"https://api.github.com/repos/{org}/{repo}/releases/latest",
                )
            ).json(loads=ujson.loads)
            name = release_data["tag_name"]
            new_plugin_data.append(
                {
                    "dependency": dependency + name,
                    "repository": repository,
                }
            )

        if diff := DeepDiff(
            data["lavalink"]["plugins"], new_plugin_data, ignore_order=True, max_passes=3, cache_size=10000
        ):
            data["lavalink"]["plugins"] = new_plugin_data
            update_string = ""
            if "values_changed" in diff:
                values_changed = diff["values_changed"]
                for key, root_value in values_changed.items():
                    if "'dependency'" not in key:
                        LOGGER.warning("Ignoring key %s  during plugin update - %s", key, root_value)
                        continue
                    old_value = None
                    new_value = None
                    for sub_key, value in root_value.items():
                        if sub_key == "old_value":
                            old_value = value
                        elif sub_key == "new_value":
                            new_value = value
                    if all([old_value, new_value]):
                        update_string += _("{name} was updated from {old_value} to {new_value}\n").format(
                            old_value=old_value.split(":")[-1],
                            new_value=bold(new_value.split(":")[-1]),
                            name=bold(old_value.split(":")[-2]),
                        )
            await config.update_yaml(data)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Managed node's plugins updated.\n\n{updates}").format(
                        updates=update_string,
                        prefix=context.clean_prefix,
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Managed node's plugins already up to date"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged_config.command(name="source")
    async def command_plmanaged_config_source(self, context: PyLavContext, source: str, state: bool):
        """Toggle the managed node sources"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        source = source.lower().strip()
        valid_sources = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["sources"].copy()
        valid_sources |= NODE_DEFAULT_SETTINGS["plugins"]["lavasrc"]["sources"]
        valid_sources |= NODE_DEFAULT_SETTINGS["plugins"]["dunctebot"]["sources"]
        if source not in valid_sources:
            return await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Invalid source, {valid_list} are valid sources").format(
                        valid_list=humanize_list(sorted(list(map(inline, valid_sources.keys())), key=str.lower))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        if source in data["lavalink"]["server"]["sources"]:
            data["lavalink"]["server"]["sources"][source] = state
        elif source in data["plugins"]["lavasrc"]["sources"]:
            data["plugins"]["lavasrc"]["sources"][source] = state
        elif source in data["plugins"]["dunctebot"]["sources"]:
            data["plugins"]["dunctebot"]["sources"][source] = state
        await config.update_yaml(data)
        state = _("enabled") if state else _("disabled")
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's {source} source set to {state}.").format(
                    source=inline(source),
                    state=state,
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.command(name="filter")
    async def command_plmanaged_config_filter(self, context: PyLavContext, filter_name: str, state: bool):
        """Toggle the managed node filters"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        valid_filters = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["filters"].copy()
        if filter_name not in valid_filters:
            return await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Invalid source, {valid_list} are valid filters").format(
                        valid_list=humanize_list(sorted(list(map(inline, valid_filters.keys())), key=str.lower))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        data["lavalink"]["server"]["filters"][filter_name] = state
        await config.update_yaml(data)
        state = _("enabled") if state else _("disabled")
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("Managed node's {source} filter set to {state}.").format(
                    source=inline(filter_name),
                    state=state,
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.command(name="server")
    async def command_plmanaged_config_server(self, context: PyLavContext, setting: str, value: str):
        """Configure multiple settings for the managed node.

        Run `[p]plmanaged config server <setting> info` to show info about the settings and what they do.

        **Setting names**:
        `bufferDurationMs` : Integer i.e 400 (Default 400) - Set to 0 to disable JDA-NAS
        `frameBufferDurationMs` : Integer i.e 1000 (Default 1000)
        `trackStuckThresholdMs` : Integer i.e 1000 (Default 1000)
        `youtubePlaylistLoadLimit` : Integer i.e 1000 (Default 1000)
        `opusEncodingQuality` : Integer i.e 10 (Default 10)
        `resamplingQuality` : String i.e LOW (Default HIGH)
        `useSeekGhosting` : Boolean i.e True (Default True)
        `playerUpdateInterval` : Integer i.e 30 (Default 30)
        `youtubeSearchEnabled` : Boolean i.e True (Default True)
        `soundcloudSearchEnabled` : Boolean i.e True (Default True)
        """

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        user_input = setting.lower()
        value = value.lower()
        setting_case_map = {
            "bufferdurationms": "bufferDurationMs",
            "framebufferdurationms": "frameBufferDurationMs",
            "trackstuckthresholdms": "trackStuckThresholdMs",
            "youtubeplaylistloadlimit": "youtubePlaylistLoadLimit",
            "opusencodingquality": "opusEncodingQuality",
            "resamplingquality": "resamplingQuality",
            "useseekghosting": "useSeekGhosting",
            "playerupdateinterval": "playerUpdateInterval",
            "youtubesearchenabled": "youtubeSearchEnabled",
            "soundcloudsearchenabled": "soundcloudSearchEnabled",
        }
        setting = setting_case_map.get(user_input)
        if setting is None:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("{Setting} is not a valid Setting; Options are:\n\n{setting_list}").format(
                        setting=user_input, setting_list=humanize_list(list(setting_case_map.values()))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if value.lower() == "info":
            setting_description_map = {
                "bufferDurationMs": _(
                    "The duration of the NAS buffer in milliseconds. "
                    "Higher values fare better against longer GC pauses but will increase RAM usage. "
                    "Minimum of 40ms, lower values may introduce pauses and stutters. "
                    "Set to 0 to disable JDA-NAS. Accepted values: Range: 0 - 2,000"
                ),
                "frameBufferDurationMs": _(
                    "How many milliseconds of audio to keep buffered, Higher values increase RAM usage. "
                    "Accepted values: Range: 1,000 - 10,000"
                ),
                "trackStuckThresholdMs": _(
                    "The threshold in milliseconds for how long a track can be stuck. "
                    "A track is stuck if does not return any audio data. Accepted values: Range: 5,000 - 20,000"
                ),
                "youtubePlaylistLoadLimit": _(
                    "Number of pages to return for a YouTube Playlist - Each page contains 100 songs. "
                    "Accepted values: Range: 5 - 100"
                ),
                "opusEncodingQuality": _(
                    "Opus encoder quality. "
                    "Valid values range from 0 to 10, where 10 is best quality but is the most expensive on the CPU"
                ),
                "resamplingQuality": _(
                    "Quality of resampling operations. "
                    "Valid values are LOW, MEDIUM and HIGH, where HIGH uses the most CPU"
                ),
                "useSeekGhosting": _(
                    "Seek ghosting is the effect where whilst a seek is in progress, "
                    "the audio buffer is read from until empty, or until seek is ready. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`"
                ),
                "playerUpdateInterval": _(
                    "How frequently in seconds to send player updates to clients, "
                    "affects the current position accuracy. Accepted values: Range: 1 - 86400"
                ),
                "youtubeSearchEnabled": _(
                    "Enable or disable YouTube searches within the node, "
                    "this will affect AppleMusic, Spotify and any functionality dependant on YouTube. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`"
                ),
                "soundcloudSearchEnabled": _(
                    "Enable or disable SoundCloud searches within the node, "
                    "this will affect any functionality dependant on SoundCloud. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`"
                ),
            }

            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("{Setting} info.\n\n{info}").format(
                        setting=setting, info=setting_description_map.get(setting)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        setting_values_map = {
            "bufferDurationMs": (40, 2000),
            "frameBufferDurationMs": (1000, 10000),
            "trackStuckThresholdMs": (5000, 20000),
            "youtubePlaylistLoadLimit": (5, 100),
            "opusEncodingQuality": (0, 10),
            "resamplingQuality": ("low", "medium", "high"),
            "useSeekGhosting": ("0", "1", "true", "false", "t", "f"),
            "playerUpdateInterval": (1, 84600),
            "youtubeSearchEnabled": ("0", "1", "true", "false", "t", "f"),
            "soundcloudSearchEnabled": ("0", "1", "true", "false", "t", "f"),
        }
        possible_values = setting_values_map.get(setting)

        if isinstance(possible_values[0], int):
            value = int(value)
            if value not in range(possible_values[0], possible_values[0] + 1):
                await context.send(
                    embed=await context.pylav.construct_embed(
                        description=_("{Setting} valid inputs are:\n\nRange between: {start} - {end}").format(
                            setting=setting, start=possible_values[0], end=possible_values[1]
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        elif value not in possible_values:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("{Setting} valid inputs are:\n\n{setting_list}").format(
                        setting=setting, setting_list=humanize_list(possible_values)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        elif possible_values == ("0", "1", "true", "false", "t", "f"):
            value = value in ("0", "1", "true")
        elif possible_values == ("low", "medium", "high"):
            value = value.upper()
        # noinspection PyProtectedMember
        config = self.pylav._node_config_manager.bundled_node_config()
        data = await config.fetch_yaml()
        data["lavalink"]["server"][setting] = value
        await config.update_yaml(data)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_("{Setting} set to {value}.").format(
                    setting=setting,
                    value=value,
                    prefix=context.clean_prefix,
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.command(name="iprotation", aliases=["ir"])
    async def command_plmanaged_config_iprotation(self, context: PyLavContext, *, reset: bool = False):
        """Configure Lavalink IP Rotation for rate limits.

        Run `[p]plmanaged config iprotation 1` to remove the ip rotation
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not reset:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "Click the button below to configure the IP rotation for your node.\n"
                        "More info at: <https://github.com/freyacodes/Lavalink/blob/dev/ROUTEPLANNERS.md> and "
                        "<https://blog.arbjerg.dev/2020/3/tunnelbroker-with-lavalink>"
                    ),
                    messageable=context,
                ),
                view=ConfigureIPRotationView(self.bot, cog=self, prefix=context.clean_prefix),
                ephemeral=True,
            )
        else:
            # noinspection PyProtectedMember
            config = self.pylav._node_config_manager.bundled_node_config()
            data = await config.fetch_yaml()
            data["lavalink"]["server"]["ratelimit"] = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["ratelimit"]
            await config.update_yaml(data)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Removing the IP rotation from your node.").format(prefix=context.clean_prefix),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged_config.command(name="googleaccount", aliases=["ga"])
    async def command_plmanaged_config_googleaccount(self, context: PyLavContext, *, reset: bool = False):
        """Link a Google account to Lavalink to bypass YouTube's age restriction

        Run `[p]plmanaged config googleaccount 1` to remove the linked account.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not reset:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "Click the button below to link a Google account to your node, "
                        "if you have 2FA setup on this account you will need an app password instead"
                        "\nMore info at: <https://support.google.com/accounts/answer/185833>"
                    ),
                    messageable=context,
                ),
                view=ConfigureGoogleAccountView(self.bot, cog=self, prefix=context.clean_prefix),
                ephemeral=True,
            )
        else:
            # noinspection PyProtectedMember
            config = self.pylav._node_config_manager.bundled_node_config()
            data = await config.fetch_yaml()
            data["lavalink"]["server"]["youtubeConfig"] = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["youtubeConfig"]
            await config.update_yaml(data)
            await self.bot.remove_shared_api_tokens("google", "email", "password")
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Unlinking Google account from your node.").format(prefix=context.clean_prefix),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged_config.command(name="httpproxy", aliases=["hp"])
    async def command_plmanaged_config_httpproxy(self, context: PyLavContext, *, reset: bool = False):
        """Configure a HTTP proxy for Lavalink

        Run `[p]plmanaged config httpproxy 1` to remove the proxy.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not reset:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Click the button below to configure a HTTP proxy for your node"),
                    messageable=context,
                ),
                view=ConfigureHTTPProxyView(self.bot, cog=self, prefix=context.clean_prefix),
                ephemeral=True,
            )
        else:
            # noinspection PyProtectedMember
            config = self.pylav._node_config_manager.bundled_node_config()
            data = await config.fetch_yaml()
            data["lavalink"]["server"]["httpConfig"] = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["httpConfig"]
            await config.update_yaml(data)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Unlinking HTTP proxy from your node.").format(prefix=context.clean_prefix),
                    messageable=context,
                ),
                ephemeral=True,
            )
