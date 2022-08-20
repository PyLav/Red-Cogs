from __future__ import annotations

import re
import shutil
from pathlib import Path

import asyncstdlib
import discord
import humanize
import ujson
from asyncspotify import ClientCredentialsFlow
from deepdiff import DeepDiff
from discord.utils import maybe_coroutine
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, box, humanize_list, inline
from tabulate import tabulate

import pylavcogs_shared
from pylav import Client
from pylav.managed_node import get_max_allocation_size
from pylav.sql.models import LibConfigModel
from pylav.types import BotT, CogT
from pylav.utils import PyLavContext
from pylav.utils.built_in_node import NODE_DEFAULT_SETTINGS
from pylav.vendored import aiopath

LOGGER = getLogger("red.3pt.PyLavManagedNode")

_ = Translator("PyLavManagedNode", Path(__file__))


@cog_i18n(_)
class PyLavManagedNode(commands.Cog):
    """Configure the managed Lavalink node used by PyLav."""

    __version__ = "0.0.0.1a"
    lavalink: Client

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="plmanaged")
    @commands.is_owner()
    async def command_plmanaged(self, ctx: PyLavContext):
        """Configure the managed Lavalink node used by PyLav."""

    @command_plmanaged.command(name="version")
    async def command_plmanaged_version(self, context: PyLavContext) -> None:
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

    @command_plmanaged.command(name="restart", disabled=True, hidden=True)
    async def command_plmanaged_restart(self, context: PyLavContext) -> None:
        """Restart the managed Lavalink node."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not self.lavalink.enable_managed_node:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_(
                        "The managed node is not enabled, run `[p]{command}` to first enable the managed node."
                    ).format(command=self.command_plmanaged_toggle.qualified_name),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        for node in self.lavalink.node_manager.managed_nodes:
            await node.close()

        if hasattr(self.bot, "get_shared_api_token"):
            spotify = await self.bot.get_shared_api_tokens("spotify")
            client_id = spotify.get("client_id")
            client_secret = spotify.get("client_secret")
        else:
            client_id = None
            client_secret = None
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        if not await asyncstdlib.all([client_id, client_secret]):
            spotify_data = data.yaml["plugins"]["topissourcemanagers"]["spotify"]
            client_id = spotify_data["clientId"]
            client_secret = spotify_data["clientSecret"]
        elif await asyncstdlib.all([client_id, client_secret]):
            if (
                data.yaml["plugins"]["topissourcemanagers"]["spotify"]["clientId"] != client_id
                or data.yaml["plugins"]["topissourcemanagers"]["spotify"]["clientSecret"] != client_secret
            ):
                data.yaml["plugins"]["topissourcemanagers"]["spotify"]["clientId"] = client_id
                data.yaml["plugins"]["topissourcemanagers"]["spotify"]["clientSecret"] = client_secret
            await data.save()
        self.lavalink._spotify_client_id = client_id
        self.lavalink._spotify_client_secret = client_secret
        self.lavalink._spotify_auth = ClientCredentialsFlow(
            client_id=self.lavalink._spotify_client_id, client_secret=self.lavalink._spotify_client_secret
        )

        config_data = await self.lavalink._lib_config_manager.get_config(
            config_folder=self.lavalink._config_folder,
            java_path="java",
            enable_managed_node=True,
            auto_update_managed_nodes=True,
            localtrack_folder=self.lavalink._config_folder / "music",
        )
        self.lavalink.auto_update_managed_nodes = config_data.auto_update_managed_nodes
        self.lavalink.enable_managed_node = config_data.enable_managed_node
        self.lavalink.managed_node_controller._auto_update = self.lavalink.auto_update_managed_nodes
        self.lavalink.managed_node_controller._java_path = config_data.java_path

        await self.lavalink.managed_node_controller.restart()
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_("Restarted the managed Lavalink node."),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged.command(name="java")
    async def command_plmanaged_java(self, context: PyLavContext, *, java: str) -> None:
        """Set the java executable for PyLav.

        Default is "java"
        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        from stat import S_IXGRP, S_IXOTH, S_IXUSR

        java = shutil.which(java)
        path = aiopath.AsyncPath(java)
        if not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{java} does not exist, "
                        "run the command again with "
                        "the java argument "
                        "set to the correct "
                        "path."
                    ).format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return
        elif not await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{java} is not an executable file.").format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return
        stats = await path.stat()
        if not stats.st_mode & (S_IXUSR | S_IXGRP | S_IXOTH):
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{java} is not an executable, "
                        "run the command again with "
                        "the java argument "
                        "set to the correct path."
                    ).format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return

        global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
        await global_config.set_java_path(str(await maybe_coroutine(path.absolute)))
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_(
                    "PyLav's java executable has been set to {java}." "\n\nRestart the bot for it to take effect."
                ).format(
                    java=inline(f"{java}"),
                    messageable=context,
                )
            ),
            ephemeral=True,
        )

    @command_plmanaged.command(name="toggle")
    async def command_plmanaged_toggle(self, context: PyLavContext) -> None:
        """Toggle the managed node on/off.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
        await global_config.set_enable_managed_node(not global_config.enable_managed_node)

        if global_config.enable_managed_node:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node has been enabled.\n\nRestart the bot for it to take effect."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node has been disabled.\n\nRestart the bot for it to take effect."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged.command(name="updates")
    async def ccommand_plmanaged_updates(self, context: PyLavContext) -> None:
        """Toggle the managed node auto updates on/off.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
        await global_config.set_auto_update_managed_nodes(not global_config.auto_update_managed_nodes)

        if global_config.auto_update_managed_nodes:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "PyLav's managed node auto updates have been enabled."
                        "\n\nRestart the bot for it to take effect."
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "PyLav's managed node auto updates have been disabled."
                        "\n\nRestart the bot for it to take effect."
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged.command(name="heapsize", aliases=["hs", "ram", "memory"])
    async def command_plmanaged_heapsize(self, context: PyLavContext, size: str):
        """Set the managed Lavalink node maximum heap-size.

        By default, this value is 50% of available RAM in the host machine represented by [1-1024][M|G] (256M,
        256G for example)

        This value only represents the maximum amount of RAM allowed to be used at any given point, and does not mean
        that the managed Lavalink node will always use this amount of RAM.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        async def validate_input(cog: CogT, arg: str):
            match = re.match(r"^(\d+)([MG])$", arg, flags=re.IGNORECASE)
            if not match:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("Heap-size must be a valid measure of size, e.g. 256M, 256G"),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return 0
            input_in_bytes = int(match[1]) * 1024 ** (2 if match[2].lower() == "m" else 3)
            if input_in_bytes < 64 * 1024**2:
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_(
                            "Heap-size must be at least 64M, however it is recommended to have it set to at least 1G."
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return 0
            elif input_in_bytes > (meta := get_max_allocation_size(cog.managed_node_controller._java_exc))[0]:
                if meta[1]:
                    await context.send(
                        embed=await context.lavalink.construct_embed(
                            description=_(
                                "Heap-size must be less than your system RAM, "
                                "You currently have {ram_in_bytes} of RAM available."
                            ).format(ram_in_bytes=inline(humanize.naturalsize(meta[0]))),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )

                else:
                    await context.send(
                        embed=await context.lavalink.construct_embed(
                            description=_("Heap-size must be less than {limit} due to your system limitations.").format(
                                limit=inline(humanize.naturalsize(meta[0]))
                            )
                        ),
                        ephemeral=True,
                    )
                return 0
            return 1

        if not (await validate_input(self, size)):
            return
        size = size.upper()
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        data.extras["max_ram"] = size
        await data.save()
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_(
                    "Managed node's heap-size set to {bytes}.\n\nRestart the bot for it to take effect."
                ).format(bytes=inline(size)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged.group(name="config")
    async def command_plmanaged_config(self, context: PyLavContext):
        """Change the managed node start up configs."""

    @command_plmanaged_config.command(name="host")
    async def command_plmanaged_config_host(self, context: PyLavContext, host: str):
        """Set the managed node host."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        data.yaml["server"]["host"] = host
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Managed node's host set to {host}.\n\nRestart the bot for it to take effect.").format(
                    host=inline(host)
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
                embed=await context.lavalink.construct_embed(
                    description=_("The port must be between 1024 and 49151."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        data.yaml["server"]["port"] = port
        await data.save()
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("Managed node's port set to {port}.\n\nRestart the bot for it to take effect.").format(
                    port=port
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.group(name="plugins")
    async def command_plmanaged_config_plugins(self, context: PyLavContext):
        """Change the managed node plugins."""

    @command_plmanaged_config_plugins.command(name="update")
    async def command_plmanaged_config_plugins_update(self, context: PyLavContext):
        """Update the managed node plugins."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        new_plugin_data = []
        for plugin in data.yaml["lavalink"]["plugins"].copy():
            if plugin["dependency"].startswith("com.github.Topis-Lavalink-Plugins:Topis-Source-Managers-Plugin:"):
                org = "Topis-Lavalink-Plugins"
                repo = "Topis-Source-Managers-Plugin"
                repository = "https://jitpack.io"
            elif plugin["dependency"].startswith("com.dunctebot:skybot-lavalink-plugin:"):
                org = "DuncteBot"
                repo = "skybot-lavalink-plugin"
                repository = "https://m2.duncte123.dev/releases"
            elif plugin["dependency"].startswith("com.github.topisenpai:sponsorblock-plugin:"):
                org = "Topis-Lavalink-Plugins"
                repo = "Sponsorblock-Plugin"
                repository = "https://jitpack.io"
            else:
                continue
            release_data = await (
                await self.lavalink.cached_session.get(
                    f"https://api.github.com/repos/{org}/{repo}/releases/latest",
                )
            ).json(loads=ujson.loads)
            name = release_data["tag_name"]
            new_plugin_data.append(
                {
                    "dependency": ":".join(plugin["dependency"].split(":")[:-1] + [name]),
                    "repository": repository,
                }
            )

        if diff := DeepDiff(data.yaml["lavalink"]["plugins"], new_plugin_data, ignore_order=True):
            data.yaml["lavalink"]["plugins"] = new_plugin_data
            update_string = ""
            if "values_changed" in diff:
                values_changed = diff["values_changed"]
                for __, root_value in values_changed.items():
                    old_value = None
                    new_value = None
                    for key, value in root_value.items():
                        if key == "old_value":
                            old_value = value["dependency"]
                        elif key == "new_value":
                            new_value = value["dependency"]
                    if all([old_value, new_value]):
                        update_string += _("{name} was updated from {old_value} to {new_value}\n").format(
                            old_value=old_value.split(":")[-1],
                            new_value=bold(new_value.split(":")[-1]),
                            name=bold(old_value.split(":")[-2]),
                        )
            await data.save()
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "Managed node's plugins updated.\n\n" "{updates}\n\nRestart the bot for it to take effect."
                    ).format(updates=update_string),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Managed node's plugins already up to date."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plmanaged_config.command(name="source")
    async def command_plmanaged_config_source(self, context: PyLavContext, source: str, state: bool):
        """Toggle the managed node sources."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        source = source.lower().strip()
        valid_sources = NODE_DEFAULT_SETTINGS["lavalink"]["server"]["sources"]

        valid_sources |= NODE_DEFAULT_SETTINGS["plugins"]["topissourcemanagers"]["sources"]
        valid_sources |= NODE_DEFAULT_SETTINGS["plugins"]["dunctebot"]["sources"]
        if source not in valid_sources:
            return await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("Invalid source, {valid_list} are valid sources.").format(
                        valid_list=humanize_list(sorted(list(map(inline, valid_sources.keys())), key=str.lower))
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        if source in data.yaml["lavalink"]["server"]["sources"]:
            data.yaml["lavalink"]["server"]["sources"][source] = state
        elif source in data.yaml["plugins"]["topissourcemanagers"]["sources"]:
            data.yaml["plugins"]["topissourcemanagers"]["sources"][source] = state
        elif source in data.yaml["plugins"]["dunctebot"]["sources"]:
            data.yaml["plugins"]["dunctebot"]["sources"][source] = state
        await data.save()
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_(
                    "Managed node's source set to {source}.\n\nRestart the bot for it to take effect."
                ).format(source=inline(source)),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plmanaged_config.command(name="server")
    async def command_plmanaged_config_server(self, context: PyLavContext, setting: str, value: str):
        """Configure multiple settings for the managed node.

        Run `[p]plmanaged config server <setting> info` to show info about the settings and what they do.

        **Setting names**:
        `bufferDurationMs` : Integer i.e 400 (Default 400)
        `frameBufferDurationMs` : Integer i.e 1000 (Default 1000)
        `trackStuckThresholdMs` : Integer i.e 1000 (Default 1000)
        `youtubePlaylistLoadLimit` : Integer i.e 1000 (Default 1000)
        `opusEncodingQuality` : Integer i.e 10 (Default 10)
        `resamplingQuality` : String i.e LOW (Default LOW)
        `useSeekGhosting` : Boolean i.e True (Default True)
        `playerUpdateInterval` : Integer i.e 1 (Default 1)
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
                embed=await context.lavalink.construct_embed(
                    description=_("{Setting} is not a valid Setting; Options are: \n\n{setting_list}.").format(
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
                    "Higher values fare better against longer GC pauses. "
                    "Minimum of 40ms, lower values may introduce pauses. Accepted values: Range: 40 - 2,000."
                ),
                "frameBufferDurationMs": _(
                    "How many milliseconds of audio to keep buffered. Accepted values: Range: 1,000 - 10,000."
                ),
                "trackStuckThresholdMs": _(
                    "The threshold in milliseconds for how long a track can be stuck. "
                    "A track is stuck if does not return any audio data. Accepted values: Range: 5,000 - 20,000."
                ),
                "youtubePlaylistLoadLimit": _(
                    "Number of pages to return for a YouTube Playlist - Each page contains 100 songs. "
                    "Accepted values: Range: 5 - 100."
                ),
                "opusEncodingQuality": _(
                    "Opus encoder quality. "
                    "Valid values range from 0 to 10, where 10 is best quality but is the most expensive on the CPU."
                ),
                "resamplingQuality": _(
                    "Quality of resampling operations. "
                    "Valid values are LOW, MEDIUM and HIGH, where HIGH uses the most CPU."
                ),
                "useSeekGhosting": _(
                    "Seek ghosting is the effect where whilst a seek is in progress, "
                    "the audio buffer is read from until empty, or until seek is ready. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`."
                ),
                "playerUpdateInterval": _(
                    "How frequently in seconds to send player updates to clients, "
                    "affects the current position accuracy. Accepted values: Range: 1 - 10."
                ),
                "youtubeSearchEnabled": _(
                    "Enable or disable YouTube searches within the node, "
                    "this will affect AppleMusic, Spotify and any functionality dependant on YouTube. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`."
                ),
                "soundcloudSearchEnabled": _(
                    "Enable or disable SoundCloud searches within the node, "
                    "this will affect any functionality dependant on SoundCloud. "
                    "Accepted values for True: `True`, `t`, `1`, Accepted values for False: `False`, `f`, `0`."
                ),
            }

            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{Setting} info.\n\n{info}.").format(
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
            "playerUpdateInterval": (1, 10),
            "youtubeSearchEnabled": ("0", "1", "true", "false", "t", "f"),
            "soundcloudSearchEnabled": ("0", "1", "true", "false", "t", "f"),
        }
        possible_values = setting_values_map.get(setting)

        if isinstance(possible_values[0], int):
            value = int(value)
            if value not in range(possible_values[0], possible_values[0] + 1):
                await context.send(
                    embed=await context.lavalink.construct_embed(
                        description=_("{Setting} valid inputs are:\n\nRange between: {start} - {end}.").format(
                            setting=setting, start=possible_values[0], end=possible_values[1]
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        elif value not in possible_values:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{Setting} valid inputs are:\n\n{setting_list}.").format(
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
        data = await self.lavalink._node_config_manager.get_bundled_node_config()
        data.yaml["lavalink"]["server"][setting] = value
        await data.save()

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("{Setting} set to {value}.\n\nRestart the bot for it to take effect.").format(
                    setting=setting, value=value
                ),
                messageable=context,
            ),
            ephemeral=True,
        )
