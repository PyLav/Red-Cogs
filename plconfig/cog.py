from __future__ import annotations

from pathlib import Path

import aiopath
import discord
from discord import SelectOption
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, box, inline
from tabulate import tabulate

from pylav.constants.builtin_nodes import PYLAV_BUNDLED_NODES_SETTINGS
from pylav.core.client import Client
from pylav.core.context import PyLavContext
from pylav.extension.red.ui.menus.player import StatsMenu
from pylav.extension.red.ui.sources.player import PlayersSource
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

from plconfig.view import InfoView

LOGGER = getLogger("PyLav.cog.Configurator")

_ = Translator("PyLavConfigurator", Path(__file__))


@cog_i18n(_)
class PyLavConfigurator(DISCORD_COG_TYPE_MIXIN):
    """Configure PyLav library settings"""

    lavalink: Client

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="plset", aliases=["plconfig"])
    async def command_plset(self, ctx: PyLavContext) -> None:
        """Change global settings for PyLav"""

    @command_plset.command(name="version")
    async def command_plset_version(self, context: PyLavContext) -> None:
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

    @command_plset.command(name="info")
    async def command_plset_info(self, context: PyLavContext) -> None:
        """Show the setting values"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        options = [
            SelectOption(
                label=shorten_string(max_length=100, string=_("PyLav Settings")),
                value="pylav_config",
                description=shorten_string(
                    max_length=100, string=_("Get information about the PyLav library settings.")
                ),
            ),
            SelectOption(
                label=shorten_string(max_length=100, string=_("Global Settings")),
                value="global_player_config",
                description=shorten_string(
                    max_length=100, string=_("Get information about bot owner configured settings for the players.")
                ),
            ),
        ]
        if context.guild:
            options.extend(
                [
                    SelectOption(
                        label=shorten_string(max_length=100, string=_("Contextual Settings")),
                        value="context_player_config",
                        description=shorten_string(
                            max_length=100,
                            string=_(
                                "Get information about contextual settings for the player, "
                                "accounting for the global settings."
                            ),
                        ),
                    ),
                    SelectOption(
                        label=shorten_string(max_length=100, string=_("Server Settings")),
                        value="server_player_config",
                        description=shorten_string(
                            max_length=100,
                            string=_("Get information about the server configured settings for the player."),
                        ),
                    ),
                ]
            )

        options.append(
            SelectOption(
                label=shorten_string(max_length=100, string=_("Playlist Tasks")),
                value="playlist_tasks",
                description=shorten_string(
                    max_length=100, string=_("Get information about the playlist auto update schedule.")
                ),
            )
        )

        if await self.bot.is_owner(context.author):
            options.extend(
                [
                    SelectOption(
                        label=shorten_string(max_length=100, string=_("PyLav Paths")),
                        value="pylav_paths",
                        description=shorten_string(max_length=100, string=_("Get information about PyLav paths")),
                    ),
                ]
            )
            if not self.pylav.managed_node_controller.disabled:
                options.append(
                    SelectOption(
                        label=shorten_string(max_length=100, string=_("Managed Node Settings")),
                        value="managed_node_config",
                        description=shorten_string(
                            max_length=100, string=_("Get information about the Managed PyLav Lavalink node")
                        ),
                    ),
                )

        await InfoView(cog=self, context=context, options=options).start()

    @command_plset.command(name="dj")
    @commands.guild_only()
    async def command_plset_dj(self, context: PyLavContext, *, role_or_member: discord.Role | discord.Member):
        """Checks if a user or role is considered a disc jockey"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if isinstance(role_or_member, discord.Role):
            config = self.bot.pylav.player_config_manager.get_config(context.guild.id)
            dj_roles = await config.fetch_dj_roles()
            dj_roles = dj_roles.union(await config.fetch_dj_users())
            is_dj = role_or_member.id in dj_roles if dj_roles else True
            message = (
                _("{role_name_variable_do_not_translate} is a disc jockey role.").format(
                    role_name_variable_do_not_translate=role_or_member.mention
                )
                if is_dj
                else _("{role_name_variable_do_not_translate} is not a disc jockey role.").format(
                    role_name_variable_do_not_translate=role_or_member.mention
                )
            )
        else:
            is_dj = await self.bot.pylav.is_dj(user=role_or_member, guild=context.guild, bot=self.bot)
            message = (
                _("{user_name_variable_do_not_translate} is a disc jockey.").format(
                    user_name_variable_do_not_translate=role_or_member.mention
                )
                if is_dj
                else _("{user_name_variable_do_not_translate} is not a disc jockey.").format(
                    user_name_variable_do_not_translate=role_or_member.mention
                )
            )
        await context.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.command(name="tracks")
    @commands.is_owner()
    async def command_plset_tracks(self, context: PyLavContext, create: bool, *, folder: str) -> None:
        """Set the local tracks folder for PyLav.

        Changes will be applied after I restart.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        path = aiopath.AsyncPath(folder)
        if await path.is_file():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("{folder_path_variable_do_not_translate} is not a folder.").format(
                        folder_path_variable_do_not_translate=inline(
                            f"{await discord.utils.maybe_coroutine(path.absolute)}"
                        ),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if create:
            await path.mkdir(parents=True, exist_ok=True)
        elif not await path.exists():
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "{folder_path_variable_do_not_translate} does not exist, rerun the command with the create argument set to {command_variable_do_not_translate} to create this folder automatically."
                    ).format(
                        command_variable_do_not_translate="`1`",
                        folder_path_variable_do_not_translate=inline(
                            f"`{await discord.utils.maybe_coroutine(path.absolute)}`"
                        ),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        await self.pylav.update_localtracks_folder(folder=path)
        await context.send(
            embed=await context.pylav.construct_embed(
                description=_(
                    "PyLav local tracks folder has been set to {folder_path_variable_do_not_translate}."
                ).format(
                    folder_path_variable_do_not_translate=inline(
                        f"`{await discord.utils.maybe_coroutine(path.absolute)}`"
                    ),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.group(name="node")
    @commands.is_owner()
    async def command_plset_node(self, context: PyLavContext) -> None:
        """Change the managed node configuration"""

    @command_plset_node.command(name="toggle")
    async def command_plset_node_toggle(self, context: PyLavContext) -> None:
        """Toggle the managed node on/off.

        Changes will be applied after I restart.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.pylav.lib_db_manager.get_config()
        current = await global_config.fetch_enable_managed_node()
        await global_config.update_enable_managed_node(not current)

        if not current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned on my managed Lavalink node."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned off my managed Lavalink node."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node.command(name="updates")
    async def command_plset_node_updates(self, context: PyLavContext) -> None:
        """Toggle the managed node auto updates on/off.

        Changes will be applied after I restart.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.pylav.lib_db_manager.get_config()
        current = await global_config.fetch_auto_update_managed_nodes()
        await global_config.update_auto_update_managed_nodes(not current)

        if not current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned on the self-update functionality of my managed node."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned off the self-update functionality of my managed node."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node.group(name="external")
    async def command_plset_node_external(self, context: PyLavContext) -> None:
        """Change the bundled external nodes state"""

    @command_plset_node_external.command(name="pylav")
    async def command_plset_node_external_pylav(self, context: PyLavContext) -> None:
        """Toggle the managed external draper.wtf nodes on/off"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.pylav.lib_db_manager.get_config()
        current_state = await global_config.fetch_use_bundled_pylav_external()
        await global_config.update_use_bundled_pylav_external(not current_state)

        if not current_state:
            # node_config = self.pylav.node_db_manager.get_node_config(
            #     PYLAV_BUNDLED_NODES_SETTINGS["ll-gb.draper.wtf"]["unique_identifier"]
            # )
            # await self.pylav.add_node(**(await node_config.get_connection_args()))
            node_config = self.pylav.node_db_manager.get_node_config(
                PYLAV_BUNDLED_NODES_SETTINGS["ll-us-ny.draper.wtf"]["unique_identifier"]
            )
            await self.pylav.add_node(**(await node_config.get_connection_args()))
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned on the PyLav external Lavalink nodes."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            # await self.pylav.remove_node(PYLAV_BUNDLED_NODES_SETTINGS["ll-gb.draper.wtf"]["unique_identifier"])
            await self.pylav.remove_node(PYLAV_BUNDLED_NODES_SETTINGS["ll-us-ny.draper.wtf"]["unique_identifier"])
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned off the PyLav external Lavalink nodes."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node_external.command(name="lavalink")
    async def command_plset_node_lavalink(self, context: PyLavContext) -> None:
        """Toggle the managed external lava.link node on/off"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.pylav.lib_db_manager.get_config()
        current_state = await global_config.fetch_use_bundled_lava_link_external()
        await global_config.update_use_bundled_lava_link_external(False)
        if current_state:
            await self.pylav.remove_node(1001)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I have turned on the lava.link external Lavalink node."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("The PyLav managed lava.link external Lavalink node has been permanently removed."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset.command(name="spotifyapi")
    @commands.is_owner()
    async def command_plset_spotifyapi(self, context: PyLavContext) -> None:
        """Instructions on how to set the Spotify API Tokens"""
        message = _(
            "1. Go to Spotify developers and log in with your Spotify account.\n"
            "{spotify_url_variable_do_not_translate}\n"
            '2. Click on "Create An App".\n'
            "3. Fill out the form provided with your application name, etc.\n"
            '4. When asked if you\'re developing commercial integration select "No".\n'
            "5. Accept the terms and conditions.\n"
            "6. Execute the following command replacing "
            "{argument_1_variable_do_not_translate} with your client identifier "
            "and {argument_2_variable_do_not_translate} with your client secret:\n"
            "  `{command_name_variable_do_not_translate}`"
        ).format(
            spotify_url_variable_do_not_translate="(https://developer.spotify.com/dashboard/applications)",
            argument_1_variable_do_not_translate="<client_id_value>",
            argument_2_variable_do_not_translate="<client_secret_value>",
            command_name_variable_do_not_translate=f"`{context.clean_prefix}set api spotify client_id <client_id_value> client_secret <client_secret_value>`",
        )
        await context.send(
            embed=await context.pylav.construct_embed(
                description=message,
                messageable=context,
            )
        )

    @command_plset.command(name="stats")
    @commands.is_owner()
    async def command_plset_stats(self, context: PyLavContext, *, server: discord.Guild = None) -> None:
        """Manage active players"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if server and (self.pylav.player_manager.get(server.id) is None):
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "I am not currently playing anything in {server_name_variable_do_not_translate}."
                    ).format(server_name_variable_do_not_translate=bold(server.name)),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        elif not self.pylav.player_manager.connected_players:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("I am not connected to any voice channel at the moment."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        await StatsMenu(
            cog=self,
            bot=self.bot,
            source=PlayersSource(cog=self, specified_guild=server.id if server else None),
            original_author=context.author,
        ).start(ctx=context)

    @command_plset.command(name="activity")
    @commands.is_owner()
    async def command_plset_activity(self, context: PyLavContext) -> None:
        """Toggle whether or not I should update my Discord activity when playing tracks."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.pylav.lib_db_manager.get_config()
        current = await global_config.fetch_update_bot_activity()
        await global_config.update_update_bot_activity(not current)
        if not current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("From now on, I will update my activity to reflect the tracks I am playing."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await self.bot.change_presence(activity=None)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "From now on, I will no longer update my activity to reflect the tracks I am playing."
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
