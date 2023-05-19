from __future__ import annotations

import heapq
import os.path
import re
from functools import partial
from itertools import islice
from pathlib import Path

import discord
from discord import app_commands
from discord.app_commands import AppCommandError, Choice, CommandOnCooldown, Cooldown
from rapidfuzz import fuzz
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box
from tabulate import tabulate

from pylav.core.context import PyLavContext
from pylav.extension.red.utils import rgetattr
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

LOGGER = getLogger("PyLav.cog.LocalFiles")


_ = Translator("PyLavLocalFiles", Path(__file__))

REGEX_FILE_NAME = re.compile(r"[.\-_/\\ ]+")


async def cache_filled(interaction: DISCORD_INTERACTION_TYPE) -> bool:
    context = await interaction.client.get_context(interaction)
    cog: PyLavLocalFiles = context.bot.get_cog("PyLavLocalFiles")  # type: ignore
    if not cog:
        return False
    if not (cache := rgetattr(cog, "pylav.local_tracks_cache", None)):
        return False
    if not cache.is_ready:
        raise CommandOnCooldown(Cooldown(1, 1), 60)
    return cache.is_ready


@cog_i18n(_)
class PyLavLocalFiles(DISCORD_COG_TYPE_MIXIN):
    """Play local files and folders from the owner configured location"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def cog_check(self, ctx: PyLavContext):
        if not (cache := rgetattr(self, "pylav.local_tracks_cache", None)):
            return False
        return cache.is_ready

    @commands.group(name="pllocalset")
    async def command_pllocalset(self, ctx: PyLavContext):
        """Configure cog settings"""

    @command_pllocalset.command(name="version")
    async def command_pllocalset_version(self, context: PyLavContext) -> None:
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

    @command_pllocalset.command(name="update")
    @commands.is_owner()
    async def command_pllocalset_update(self, context: PyLavContext) -> None:
        """Update the track list for /local"""
        if isinstance(context, discord.Interaction):
            context = await self.cog.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        await self.pylav.local_tracks_cache.update()
        await context.send(
            embed=await self.pylav.construct_embed(
                description=shorten_string(
                    max_length=100,
                    string=_(
                        "I have updated my local track cache. There are now {number_variable_do_not_translate} tracks present."
                    ).format(number_variable_do_not_translate=len(self.pylav.local_tracks_cache.path_to_track)),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="local",
        description=shorten_string(max_length=100, string=_("Play a local file or folder, supports partial searching")),
        extras={"red_force_enable": True},
    )
    @app_commands.describe(
        entry=shorten_string(max_length=100, string=_("The local file or folder to play")),
        recursive=shorten_string(
            max_length=100, string=_("If entry is a folder, play everything inside of it recursively")
        ),
    )
    @app_commands.guild_only()
    @app_commands.check(cache_filled)
    async def slash_local(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        entry: str,
        recursive: bool | None = False,
    ):  # sourcery no-metrics
        """Play a local file or folder, supports partial searching"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        send = partial(interaction.followup.send, wait=True)
        author = interaction.user
        if entry not in self.pylav.local_tracks_cache.hexdigest_to_query:
            await send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "{user_input_query_variable_do_not_translate} is not a valid local file or folder."
                    ).format(user_input_query_variable_do_not_translate=entry),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
            return
        entry = self.pylav.local_tracks_cache.hexdigest_to_query[entry]
        entry._recursive = recursive
        player = self.pylav.get_player(interaction.guild.id)
        if player is None:
            config = self.pylav.player_config_manager.get_config(interaction.guild.id)
            if (channel := interaction.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel, so I can connect to it."),
                            messageable=interaction,
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(interaction.guild.me))
                and permission.connect
                and permission.speak
            ):
                await send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=author)

        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            entry,
            requester=author,
            player=player,
        )
        if count:
            if count == 1:
                await player.add(requester=author.id, track=successful[0])
            else:
                await player.bulk_add(requester=author.id, tracks_and_queries=successful)
        single_track = successful[0] if successful else None
        if not (player.is_active or player.queue.empty()):
            await player.next(requester=author)
        file = discord.utils.MISSING
        thumbnail = discord.utils.MISSING
        match count:
            case 0:
                description = _("No tracks were found for your query.")
            case 1:
                description = _("{track_name_variable_do_not_translate} enqueued.").format(
                    track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True)
                )
                file = await single_track.get_embedded_artwork()
                thumbnail = await single_track.artworkUrl() or discord.utils.MISSING
            case __:
                description = _("I have enqueued {track_count_variable_do_not_translate} tracks.").format(
                    track_count_variable_do_not_translate=count
                )
        await send(
            embed=await self.pylav.construct_embed(
                description=description,
                messageable=interaction,
                thumbnail=thumbnail,
            ),
            ephemeral=True,
            file=file,
        )

    @slash_local.autocomplete("entry")
    async def slash_local_autocomplete_entry(self, interaction: DISCORD_INTERACTION_TYPE, current: str):
        if not self.pylav.local_tracks_cache.hexdigest_to_query:
            return []

        if not current:
            extracted = list(islice(self.pylav.local_tracks_cache.hexdigest_to_query.items(), 25))
        else:
            current = re.sub(REGEX_FILE_NAME, r" ", current)

            def _filter_partial_ratio(x: tuple[str, Query]):
                # noinspection PyProtectedMember
                path = f"{x[1]._query}"
                # noinspection PyProtectedMember
                return (
                    fuzz.partial_ratio(re.sub(REGEX_FILE_NAME, r" ", path), current, score_cutoff=75),
                    10 if os.path.isdir(path) else 0,
                    [-ord(i) for i in path],
                )

            extracted = heapq.nlargest(
                25, self.pylav.local_tracks_cache.hexdigest_to_query.items(), key=_filter_partial_ratio
            )
        entries = []
        for md5, query in extracted:
            entries.append(
                Choice(
                    name=await query.query_to_string(
                        max_length=90, with_emoji=True, no_extension=True, add_ellipsis=True
                    ),
                    value=md5,
                )
            )
        return entries

    @slash_local.error
    async def slash_local_error(self, interaction: DISCORD_INTERACTION_TYPE, error: AppCommandError):
        if isinstance(error, CommandOnCooldown):
            cache = rgetattr(self.bot, "pylav.local_tracks_cache", None)
            if cache and not getattr(cache, "is_ready", False):
                await self.bot.tree._send_from_interaction(
                    interaction, _("The local track cache is currently being built, try again later.")
                )
                return
        await self.bot.tree.on_error(error, interaction)
