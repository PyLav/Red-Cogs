from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_list, inline
from tabulate import tabulate

from pylav.compat import json
from pylav.constants.builtin_nodes import BUNDLED_NODES_IDS_HOST_MAPPING
from pylav.core.context import PyLavContext
from pylav.extension.red.ui.menus.generic import PaginatingMenu
from pylav.extension.red.ui.menus.nodes import AddNodeFlow, NodeManagerMenu
from pylav.extension.red.ui.prompts.nodes import maybe_prompt_for_node
from pylav.extension.red.ui.sources.nodes import NodeListSource, NodeManageSource
from pylav.helpers.discord.converters.nodes import NodeConverter
from pylav.helpers.format.ascii import EightBitANSI
from pylav.logging import getLogger
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Nodes")

_ = Translator("PyLavNodes", Path(__file__))


@cog_i18n(_)
class PyLavNodes(DISCORD_COG_TYPE_MIXIN):
    """Manage the nodes used by PyLav"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.is_owner()
    @commands.group(name="plnode", aliases=["plnodes"])
    async def command_plnode(self, context: PyLavContext) -> None:
        """Configure PyLav Nodes"""

    @command_plnode.command(name="version")
    async def command_plnode_version(self, context: PyLavContext) -> None:
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

    @command_plnode.command(name="add", aliases=["create", "new"])
    async def command_plnode_add(self, context: PyLavContext) -> None:
        """Add a node to PyLav"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        menu = AddNodeFlow(
            cog=self,
            original_author=context.author,
        )
        title = _("Let us add a node to PyLav!")
        info_description = _(
            "(**1**){space_variable_do_not_translate} - Apply changes and add the node to PyLav.\n"
            "(**2**){space_variable_do_not_translate} - Cancel any changes made and close the menu.\n"
            "(**3**){space_variable_do_not_translate} - Toggle between search-only and search and playback modes.\n"
            "(**4**){space_variable_do_not_translate} - Toggle between SSL on and off.\n"
            "(**5**){space_variable_do_not_translate} - Add a name to the node.\n"
            "(**6**){space_variable_do_not_translate} - Add the host address of the node.\n"
            "(**7**){space_variable_do_not_translate} - Add the port the node uses.\n"
            "(**8**){space_variable_do_not_translate} - Set the password for the node.\n"
            "(**9**){space_variable_do_not_translate} - Set the connection timeout.\n"
            "(**10**) - Select which sources to disable for this node (Multiple can be selected).\n"
            "If you interact with a button multiple times, "
            "only the last interaction will take effect.\n\n\n"
        ).format(
            space_variable_do_not_translate="\N{EN SPACE}",
        )
        await menu.start(context, description=info_description, title=title)
        with contextlib.suppress(asyncio.TimeoutError):
            await menu.wait_until_complete()
        if menu.cancelled:
            return
        if not all([menu.host, menu.password, menu.unique_identifier, menu.port, menu.name, menu.resume_timeout]):
            return
        node = await self.pylav.add_node(
            host=menu.host,
            password=menu.password,
            unique_identifier=menu.unique_identifier,
            port=menu.port,
            name=menu.name,
            resume_timeout=menu.resume_timeout,
            ssl=menu.ssl,
            reconnect_attempts=-1,
            search_only=menu.search_only,
            managed=False,
            disabled_sources=list(menu.disabled_sources_selector.values),
        )
        try:
            if node:
                with contextlib.suppress(asyncio.TimeoutError):
                    await node.wait_until_ready(timeout=120)
                    await node.update_features()
                    await node.update_disabled_sources(set(menu.disabled_sources_selector.values))
            disabled_capabilities = set(menu.disabled_sources_selector.values).union(
                await node.get_unsupported_features()
            )
            embed = await self.pylav.construct_embed(
                description=_(
                    "I have added the {name_variable_do_not_translate} node with the following settings:\n"
                    "Host: {host_variable_do_not_translate}\n"
                    "Port: {port_variable_do_not_translate}\n"
                    "Password: {password_variable_do_not_translate}\n"
                    "Resume Timeout: {resume_timeout_variable_do_not_translate}\n"
                    "Search Only: {search_only_variable_do_not_translate}\n"
                    "SSL: {ssl_variable_do_not_translate}\n"
                    "Disabled Sources: {disabled_sources_variable_do_not_translate}\n"
                ).format(
                    name_variable_do_not_translate=inline(menu.name),
                    host_variable_do_not_translate=menu.host,
                    port_variable_do_not_translate=menu.port,
                    password_variable_do_not_translate=menu.password,
                    resume_timeout_variable_do_not_translate=menu.resume_timeout,
                    search_only_variable_do_not_translate=menu.search_only,
                    ssl_variable_do_not_translate=menu.ssl,
                    disabled_sources_variable_do_not_translate=humanize_list(list(disabled_capabilities)),
                ),
                messageable=context.channel,
            )
            if menu.last_interaction:
                await menu.last_interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await context.author.send(
                    embed=embed,
                )
        except Exception:  # noqa
            if menu.last_interaction:
                await menu.last_interaction.followup.send(
                    embed=await self.pylav.construct_embed(
                        description=_("I am unable to add this node"), messageable=context.channel
                    ),
                    ephemeral=True,
                )
            else:
                await context.author.send(
                    embed=await self.pylav.construct_embed(
                        description=_("I am unable to add this node"), messageable=context.channel
                    ),
                )

    @command_plnode.command(name="remove", aliases=["delete", "del", "rm"])
    async def command_plnode_remove(self, context: PyLavContext, *, nodes: NodeConverter):
        """Remove a node from a PyLav instance"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        node = await maybe_prompt_for_node(cog=self, nodes=nodes, context=context)
        if not node:
            return
        if node.identifier in BUNDLED_NODES_IDS_HOST_MAPPING:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("{name_variable_do_not_translate} is managed by PyLav and cannot be removed.").format(
                        name_variable_do_not_translatee=node.name
                    ),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return
        node_data = await node.config.fetch_all()
        await self.pylav.remove_node(node.identifier)
        for k in ["id", "resume_key", "resume_timeout", "managed", "reconnect_attempts", "extras"]:
            node_data.pop(k, None)
        if yaml := node_data.pop("yaml", None):
            node_data["server"] = yaml["server"]
            node_data["server"].update(yaml["lavalink"]["server"])
        await context.author.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "I have removed the {name_variable_do_not_translate} node.\n\n{data_variable_do_not_translate}"
                ).format(
                    name_variable_do_not_translate=node_data["name"],
                    data_variable_do_not_translate=box(
                        lang="json", text=json.dumps(node_data, indent=2, sort_keys=True)
                    ),
                ),
                messageable=context.channel,
            )
        )
        await context.send(
            embed=await self.pylav.construct_embed(
                description=_(
                    "I have removed the {name_variable_do_not_translate} node. A direct message was sent to you with the node details in case you wish to re-add it."
                ).format(name_variable_do_not_translate=node_data["name"]),
                messageable=context.channel,
            ),
            ephemeral=True,
        )

    @command_plnode.command(name="manage")
    async def command_plnode_manage(self, context: PyLavContext):
        """Manage all nodes in a PyLav instance"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        menu = NodeManagerMenu(
            cog=self,
            bot=self.bot,
            original_author=context.author,
            timeout=300,
            source=NodeManageSource(cog=self),
        )
        title = _("Let us manage some nodes!")
        info_description = _(
            "(**1**){space_variable_do_not_translate} - Cancel any changes made and close the menu.\n"
            "(**6**){space_variable_do_not_translate} - Show sources enabled for this node.\n"
            "(**7**){space_variable_do_not_translate} - Apply changes and add the node to PyLav.\n"
            "(**8**){space_variable_do_not_translate} - Toggle between search-only and search and playback modes.\n"
            "(**9**){space_variable_do_not_translate} - Toggle between SSL on and off.\n"
            "(**10**) - Add a name to the node.\n"
            "(**11**) - Add the host address of the node.\n"
            "(**12**) - Add the port the node uses.\n"
            "(**13**) - Set the password for the node.\n"
            "(**14**) - Set the connection timeout.\n"
            "(**15**) - Remove this node.\n"
            "(**16**) - Select which sources to disable for this node (Multiple can be selected).\n"
            "If you interact with a button multiple times, "
            "only the last interaction will take effect.\n\n\n"
        ).format(
            space_variable_do_not_translate="\N{EN SPACE}",
        )
        await menu.start(context, description=info_description, title=title)
        with contextlib.suppress(asyncio.TimeoutError):
            await menu.wait_until_complete()
        if menu.cancelled:
            return
        node = menu.source.target
        if not node:
            return
        if node.managed or node.identifier in BUNDLED_NODES_IDS_HOST_MAPPING or node.identifier == 31415:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "{name_variable_do_not_translate} is managed by PyLav, and I can not modify it."
                    ).format(name_variable_do_not_translate=node.name),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return
        if menu.delete:
            await self.pylav.remove_node(node.identifier)
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("I have removed the {name_variable_do_not_translate} node.").format(
                        name_variable_do_not_translate=node.name
                    ),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return

        with contextlib.suppress(asyncio.TimeoutError):
            await node.wait_until_ready(timeout=120)
            await node.update_features()
            await node.update_disabled_sources(set(menu.disabled_sources_selector.values))
        disabled_capabilities = set(menu.disabled_sources_selector.values).union(await node.get_unsupported_features())

        if menu.search_only is not None:
            await node.config.update_search_only(menu.search_only)
        if menu.ssl is not None:
            await node.config.update_ssl(menu.ssl)
        if menu.name:
            await node.config.update_name(menu.name)
        yaml_data = await node.config.fetch_yaml()
        if menu.host:
            yaml_data["server"]["host"] = menu.host
        if menu.port:
            yaml_data["server"]["port"] = menu.port
        if menu.password:
            yaml_data["lavalink"]["server"]["password"] = menu.password
        await node.config.update_yaml(yaml_data)

        if menu.timeout:
            await node.config.update_resume_timeout(int(menu.timeout))
        if menu.disabled_sources_selector:
            await node.config.bulk_add_to_disabled_sources(*disabled_capabilities)

        await self.pylav.remove_node(node.identifier)
        await self.pylav.add_node(**(await node.config.get_connection_args()))
        embed = await self.pylav.construct_embed(
            description=_(
                "I have changed the {name_variable_do_not_translate} node to the following settings:\n"
                "Host: {host_variable_do_not_translate}\n"
                "Port: {port_variable_do_not_translate}\n"
                "Password: {password_variable_do_not_translate}\n"
                "Resume Timeout: {resume_timeout_variable_do_not_translate}\n"
                "Search Only: {search_only_variable_do_not_translate}\n"
                "SSL: {ssl_variable_do_not_translate}\n"
                "Disabled Sources: {disabled_sources_variable_do_not_translate}\n"
            ).format(
                name_variable_do_not_translate=inline(menu.name),
                host_variable_do_not_translate=menu.host,
                port_variable_do_not_translate=menu.port,
                password_variable_do_not_translate=menu.password,
                resume_timeout_variable_do_not_translate=menu.resume_timeout,
                search_only_variable_do_not_translate=menu.search_only,
                ssl_variable_do_not_translate=menu.ssl,
                disabled_sources_variable_do_not_translate=humanize_list(list(disabled_capabilities)),
            ),
            messageable=context.channel,
        )
        await context.author.send(
            embed=embed,
        )

    @command_plnode.command(name="list")
    async def command_plnode_list(self, context: PyLavContext):
        """List all nodes used by PyLav"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not self.pylav.node_manager.nodes:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("No nodes were added to PyLav."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=NodeListSource(cog=self, pages=self.pylav.node_manager.nodes),
            delete_after_timeout=True,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)
