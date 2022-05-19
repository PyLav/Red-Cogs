from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import discord
import ujson
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, humanize_list, inline
from tabulate import tabulate

import pylavcogs_shared
from pylav.converters.nodes import NodeConverter
from pylav.types import BotT
from pylav.utils import PyLavContext
from pylavcogs_shared.ui.menus.generic import PaginatingMenu
from pylavcogs_shared.ui.menus.nodes import AddNodeFlow, NodeManagerMenu
from pylavcogs_shared.ui.prompts.nodes import maybe_prompt_for_node
from pylavcogs_shared.ui.sources.nodes import NodeListSource, NodeManageSource

LOGGER = getLogger("red.3pt.PyLavNodes")

_ = Translator("PyLavNodes", Path(__file__))


@cog_i18n(_)
class PyLavNodes(commands.Cog):
    """Manage the nodes used by PyLav."""

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.is_owner()
    @commands.group(name="plnode")
    async def command_plnode(self, context: PyLavContext) -> None:
        """Configure PyLav Nodes."""

    @command_plnode.command(name="version")
    async def command_plnode_version(self, context: PyLavContext) -> None:
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

    @command_plnode.command(name="add", aliases=["create", "new"])
    async def command_plnode_add(self, context: PyLavContext) -> None:
        """Add a node PyLav."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        menu = AddNodeFlow(
            cog=self,
            original_author=context.author,
        )
        title = _("Let's add a node to PyLav!")
        info_description = _(
            "(**1**){space} - Apply changes and add the node to PyLav.\n"
            "(**2**){space} - Cancel any changes made and close the menu.\n"
            "(**3**){space} - Toggle between search-only and search and playback modes.\n"
            "(**4**){space} - Toggle between SSL on and off.\n"
            "(**5**){space} - Add a name to the node.\n"
            "(**6**){space} - Add the host address of the node.\n"
            "(**7**){space} - Add the port the node uses.\n"
            "(**8**){space} - Set the password for the node.\n"
            "(**9**){space} - Set the connection timeout.\n"
            "(**10**) - Select which sources to disable for this node (Multiple can be selected).\n"
            "If you interact with a button multiple times,  "
            "only the last interaction will take effect.\n\n\n"
        ).format(
            space="\N{EN SPACE}",
        )
        await menu.start(context, description=info_description, title=title)
        with contextlib.suppress(asyncio.TimeoutError):
            await menu.wait_until_complete()
        if menu.cancelled:
            return
        if not all([menu.host, menu.password, menu.unique_identifier, menu.port, menu.name, menu.resume_timeout]):
            return
        node = await self.lavalink.add_node(
            host=menu.host,
            password=menu.password,
            unique_identifier=menu.unique_identifier,
            port=menu.port,
            name=menu.name,
            resume_timeout=menu.resume_timeout,
            resume_key=f"{menu.name}-{menu.unique_identifier}",
            ssl=menu.ssl,
            reconnect_attempts=-1,
            search_only=menu.search_only,
            managed=False,
            disabled_sources=list(menu.disabled_sources_selector.values),
        )
        try:
            async with context.typing():
                if node:
                    with contextlib.suppress(asyncio.TimeoutError):
                        await node.wait_until_ready(timeout=120)
                        await node.update_features()
                        await node.update_disabled_sources(set(menu.disabled_sources_selector.values))
                disabled_capabilities = set(menu.disabled_sources_selector.values).union(
                    await node.get_unsupported_features()
                )
                embed = await self.lavalink.construct_embed(
                    description=(
                        "Added node {name} with the following settings:\n"
                        "Host: {host}\n"
                        "Port: {port}\n"
                        "Password: {password}\n"
                        "Resume Timeout: {resume_timeout}\n"
                        "Search Only: {search_only}\n"
                        "SSL: {ssl}\n"
                        "Disabled Sources: {disabled_sources}\n"
                    ).format(
                        name=inline(menu.name),
                        host=menu.host,
                        port=menu.port,
                        password=menu.password,
                        resume_timeout=menu.resume_timeout,
                        search_only=menu.search_only,
                        ssl=menu.ssl,
                        disabled_sources=humanize_list(list(disabled_capabilities)),
                    ),
                    messageable=context.channel,
                )
                if menu.last_interaction:
                    await menu.last_interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await context.author.send(
                        embed=embed,
                    )
        except Exception:
            if menu.last_interaction:
                await menu.last_interaction.followup.send(
                    embed=await self.lavalink.construct_embed(
                        description="Unable to add this node.", messageable=context.channel
                    ),
                    ephemeral=True,
                )
            else:
                await context.author.send(
                    embed=await self.lavalink.construct_embed(
                        description="Unable to add this node.", messageable=context.channel
                    ),
                )

    @command_plnode.command(name="remove", aliases=["delete", "del", "rm"])
    async def command_plnode_remove(self, context: PyLavContext, *, nodes: NodeConverter):
        """Remove a node from PyLav instance."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        node = await maybe_prompt_for_node(cog=self, nodes=nodes, context=context)
        if not node:
            return
        if node.managed:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("{name} is managed by PyLav and cannot be removed.").format(name=node.name),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return
        await self.lavalink.remove_node(node.id)
        node_data = node.to_dict()
        for k in ["id", "resume_key", "resume_timeout", "managed", "reconnect_attempts", "extras"]:
            node_data.pop(k, None)
        if yaml := node_data.pop("yaml", None):
            node_data["server"] = yaml["server"]
            node_data["server"].update(yaml["lavalink"]["server"])
        await context.author.send(
            embed=await self.lavalink.construct_embed(
                description=_("Removed node {name}.\n\n{data}").format(
                    name=node.name, data=box(lang="json", text=ujson.dumps(node_data, indent=2, sort_keys=True))
                ),
                messageable=context.channel,
            )
        )
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_(
                    "Removed node {name}, a DM was sent to you with the node details in case you wish to re-add it."
                ).format(name=node.name),
                messageable=context.channel,
            ),
            ephemeral=True,
        )

    @command_plnode.command(name="manage")
    async def command_plnode_manage(self, context: PyLavContext):
        """Manage all nodes in PyLav instance."""
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
        title = _("Let's manage some nodes!")
        info_description = _(
            "(**1**){space} - Cancel any changes made and close the menu.\n"
            "(**6**){space} - Show sources enabled for this node.\n"
            "(**7**){space} - Apply changes and add the node to PyLav.\n"
            "(**8**){space} - Toggle between search-only and search and playback modes.\n"
            "(**9**){space} - Toggle between SSL on and off.\n"
            "(**10**) - Add a name to the node.\n"
            "(**11**) - Add the host address of the node.\n"
            "(**12**) - Add the port the node uses.\n"
            "(**13**) - Set the password for the node.\n"
            "(**14**) - Set the connection timeout.\n"
            "(**15**) - Remove this node.\n"
            "(**16**) - Select which sources to disable for this node (Multiple can be selected).\n"
            "If you interact with a button multiple times,  "
            "only the last interaction will take effect.\n\n\n"
        ).format(
            space="\N{EN SPACE}",
        )
        await menu.start(context, description=info_description, title=title)
        with contextlib.suppress(asyncio.TimeoutError):
            await menu.wait_until_complete()
        if menu.cancelled:
            return
        node = menu.source.target
        if not node:
            return
        if node.managed:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("{name} is managed by PyLav and cannot be modified with this command.").format(
                        name=node.name
                    ),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return
        if menu.delete:
            await self.lavalink.remove_node(node.identifier)
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Removed node {name}.").format(name=node.name),
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
            node.config.search_only = menu.search_only
        if menu.ssl is not None:
            node.config.ssl = menu.ssl
        if menu.name:
            node.config.name = menu.name
        if menu.host:
            node.config.host = menu.host
        if menu.port:
            node.config.port = menu.port
        if menu.password:
            node.config.password = menu.password
        if menu.timeout:
            node.config.timeout = menu.timeout
        if menu.disabled_sources_selector:
            await node.config.add_bulk_source_to_exclusion_list(*disabled_capabilities)
        else:
            await node.config.save()
        await self.lavalink.remove_node(node.identifier)
        await self.lavalink.add_node(**(node.config.get_connection_args()))
        embed = await self.lavalink.construct_embed(
            description=(
                "Changed node {name} to the following settings:\n"
                "Host: {host}\n"
                "Port: {port}\n"
                "Password: {password}\n"
                "Resume Timeout: {resume_timeout}\n"
                "Search Only: {search_only}\n"
                "SSL: {ssl}\n"
                "Disabled Sources: {disabled_sources}\n"
            ).format(
                name=inline(menu.name),
                host=menu.host,
                port=menu.port,
                password=menu.password,
                resume_timeout=menu.resume_timeout,
                search_only=menu.search_only,
                ssl=menu.ssl,
                disabled_sources=humanize_list(list(disabled_capabilities)),
            ),
            messageable=context.channel,
        )
        await context.author.send(
            embed=embed,
        )

    @command_plnode.command(name="list")
    async def command_plnode_list(self, context: PyLavContext):
        """List all nodes used by PyLav."""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if not self.lavalink.node_manager.nodes:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("No Nodes added to PyLav."), messageable=context
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=NodeListSource(cog=self, pages=self.lavalink.node_manager.nodes),
            delete_after_timeout=True,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)
