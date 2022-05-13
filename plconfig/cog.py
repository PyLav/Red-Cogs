from __future__ import annotations

import shutil
from pathlib import Path

import aiopath
import discord
from discord.utils import maybe_coroutine
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import inline

from pylav.localfiles import LocalFile
from pylav.sql.models import LibConfigModel
from pylav.types import BotT
from pylav.utils import PyLavContext

LOGGER = getLogger("red.3pt.PyLavConfigurator")

_ = Translator("PyLavConfigurator", Path(__file__))


@cog_i18n(_)
class PyLavConfigurator(commands.Cog):
    """Configure PyLav library settings."""

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.is_owner()
    @commands.group(name="plset", aliases=["plconfig"])
    async def command_plset(self, ctx: PyLavContext) -> None:
        """Change global settings for PyLav"""

    @command_plset.command(name="folder")
    async def command_plset_folder(self, context: PyLavContext, create: bool, *, folder: str) -> None:
        """Set the folder for PyLav's config files

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        path = aiopath.AsyncPath(folder)
        if await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{folder} is not a folder.").format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return

        if create:
            await path.mkdir(parents=True, exist_ok=True)
        elif not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{folder} does not exist, "
                        "run the command again with the create argument "
                        "set to 1 to automatically create this folder."
                    ).format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return

        global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
        await global_config.set_config_folder(str(await maybe_coroutine(path.absolute)))

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLav's config folder has been set to {folder}.").format(
                    folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    messageable=context,
                )
            ),
            ephemeral=True,
        )

    @command_plset.command(name="tracks")
    async def command_plset_tracks(self, context: PyLavContext, create: bool, *, folder: str) -> None:
        """Set the local tracks folder for PyLav.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        path = aiopath.AsyncPath(folder)
        if await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{folder} is not a folder.").format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return

        if create:
            await path.mkdir(parents=True, exist_ok=True)
        elif not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{folder} does not exist, "
                        "run the command again with "
                        "the create argument "
                        "set to 1 to automatically "
                        "create this folder."
                    ).format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                        messageable=context,
                    )
                ),
                ephemeral=True,
            )
            return

        global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
        await global_config.set_localtrack_folder(str(await maybe_coroutine(path.absolute)))

        await LocalFile.add_root_folder(path=path)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLav's local tracks folder has been set to {folder}.").format(
                    folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    messageable=context,
                )
            ),
            ephemeral=True,
        )

    @command_plset.command(name="java")
    async def command_plset_java(self, context: PyLavContext, *, java: str) -> None:
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
                        "set to the correct path."
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
                description=_("PyLav's java executable has been set to {java}.").format(
                    java=inline(f"{java}"),
                    messageable=context,
                )
            ),
            ephemeral=True,
        )

    @command_plset.group(name="node")
    async def command_plset_node(self, context: PyLavContext) -> None:
        """Change the managed node configuration."""

    @command_plset_node.command(name="toggle")
    async def command_plset_node_toggle(self, context: PyLavContext) -> None:
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
                    description=_("PyLav's managed node has been enabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node has been disabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node.command(name="updates")
    async def command_plset_node_updates(self, context: PyLavContext) -> None:
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
                    description=_("PyLav's managed node auto updates have been enabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node auto updates have been disabled."),
                    messageable=context,
                ),
                ephemeral=True,
            )
