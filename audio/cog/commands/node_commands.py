import asyncio
import contextlib
from abc import ABC
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import humanize_list, inline

from pylav.utils import PyLavContext

from audio.cog import MPMixin
from audio.cog.menus.menus import AddNodeFlow

_ = Translator("MediaPlayer", Path(__file__))


class NodeCommands(MPMixin, ABC):
    @commands.is_owner()
    @commands.group(name="nodeset")
    async def command_nodeset(self, context: PyLavContext) -> None:
        """Configure PyLav Nodes."""

    @command_nodeset.command(name="add")
    async def command_nodeset_add(self, context: PyLavContext) -> None:
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
            "only the last interaction will take effect, "
            "with the exception of the source selector.\n\n\n"
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
        await self.lavalink.add_node(
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
                disabled_sources=humanize_list(menu.disabled_sources_selector.values),
            ),
            messageable=context.channel,
        )
        if menu.last_interaction:
            await menu.last_interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await context.author.send(
                embed=embed,
            )
