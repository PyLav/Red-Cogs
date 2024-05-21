from __future__ import annotations

from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, pagify
from tabulate import tabulate

from pylav.core.context import PyLavContext
from pylav.extension.red.ui.menus.generic import PaginatingMenu
from pylav.extension.red.ui.sources.lyrics import LyricsSource
from pylav.helpers.format.ascii import EightBitANSI
from pylav.logging import getLogger
from pylav.nodes.api.responses.plugins import LyricsObject
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.PyLavLyrics")

_ = Translator("PyLavUtils", Path(__file__))


@cog_i18n(_)
class PyLavLyrics(DISCORD_COG_TYPE_MIXIN):
    """Lyrics commands for PyLav"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="pllyrics")
    async def command_pllyrics(self, context: PyLavContext):
        """Lyric commands for PyLav"""

    @command_pllyrics.command(name="version")
    async def command_pllyrics_version(self, context: PyLavContext) -> None:
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

    @command_pllyrics.command(name="np")
    async def command_pllyrics_np(self, context: PyLavContext) -> None:
        """Show the lyrics for currently playing song"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player or not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."), messageable=context
                ),
                ephemeral=True,
            )
            return
        track = context.player.current
        if not (lyrics := await context.player.get_lyrics()):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Lyrics for {name_variable_do_not_translate} were not found.").format(
                        name_variable_do_not_translate=await context.player.current.get_track_display_name(
                            with_url=True
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=LyricsSource(self, track, list(pagify(lyrics))),
            delete_after_timeout=False,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)

    @command_pllyrics.command(name="track")
    async def command_pllyrics_track(self, context: PyLavContext, search_string: str) -> None:
        """Show the lyrics for the specified song"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        node = await context.pylav.node_manager.find_best_node(feature="lavalyrics")
        if not node:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Lyrics feature is not enabled on any node."), messageable=context
                ),
                ephemeral=True,
            )
            return
        query = await Query.from_string(search_string)
        response = await self.pylav.get_tracks(
            query,
        )
        match response.loadType:
            case "track":
                tracks = [response.data]
            case "search":
                tracks = response.data
            case "playlist":
                tracks = response.data.tracks
            case __:
                tracks = []
        if not tracks:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("I could not find any tracks matching {query_variable_do_not_translate}.").format(
                        query_variable_do_not_translate=search_string
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        ll_track = tracks[0]
        track = await Track.build_track(node, ll_track, query, None)
        song_b64 = ll_track.encoded
        lyrics = await node.fetch_lyrics(song_b64, True)

        if not isinstance(lyrics, LyricsObject):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Lyrics for {name_variable_do_not_translate} were not found.").format(
                        name_variable_do_not_translate=await context.player.current.get_track_display_name(
                            with_url=True
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=LyricsSource(self, track, list(pagify(lyrics.text))),
            delete_after_timeout=False,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)

    @command_pllyrics.command(name="b64")
    async def command_pllyrics_b64(self, context: PyLavContext, b64_string: str) -> None:
        """Show the lyrics for the specified song string"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        node = await context.pylav.node_manager.find_best_node(feature="lavalyrics")
        if not node:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Lyrics feature is not enabled on any node."), messageable=context
                ),
                ephemeral=True,
            )
            return
        track = await Track._from_base64_string(node, b64_string, None)

        if not track:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("I could not find any tracks matching {query_variable_do_not_translate}.").format(
                        query_variable_do_not_translate=b64_string
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        lyrics = await node.fetch_lyrics(b64_string, True)
        if not isinstance(lyrics, LyricsObject):
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("Lyrics for {name_variable_do_not_translate} were not found.").format(
                        name_variable_do_not_translate=await context.player.current.get_track_display_name(
                            with_url=True
                        )
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await PaginatingMenu(
            cog=self,
            bot=self.bot,
            source=LyricsSource(self, track, list(pagify(lyrics.text))),
            delete_after_timeout=False,
            timeout=120,
            original_author=context.interaction.user if context.interaction else context.author,
        ).start(context)
