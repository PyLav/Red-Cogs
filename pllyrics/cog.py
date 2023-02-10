from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import discord
from redbot.core import Config, commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, pagify
from tabulate import tabulate

from pylav.core.context import PyLavContext
from pylav.events.track import TrackStartEvent
from pylav.exceptions.request import HTTPException
from pylav.extension.flowery.lyrics import Error
from pylav.extension.red.utils.decorators import requires_player
from pylav.helpers.format.ascii import EightBitANSI
from pylav.helpers.format.strings import format_time_dd_hh_mm_ss
from pylav.logging import getLogger
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Lyrics")

_ = Translator("PyLavLyrics", Path(__file__))


@cog_i18n(_)
class PyLavLyrics(DISCORD_COG_TYPE_MIXIN):
    """Lyrics commands for PyLav"""

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_guild(lyrics__timed=False, lyrics__full=False, lyrics__channel=None)
        self._track_cache: dict[int, str] = {}
        self._tasks: list[asyncio.Task] = []

    @commands.group(name="pllyrics")
    async def command_pllyrics(self, context: PyLavContext):
        """Lyrics commands for PyLav"""

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

    @commands.guildowner_or_permissions(manage_guild=True)
    @commands.guild_only()
    @command_pllyrics.group(name="set")
    async def command_pllyrics_set(self, context: PyLavContext):
        """Set the lyrics settings"""

    @command_pllyrics_set.command(name="timed")
    async def command_pllyrics_set_timed(self, context: PyLavContext):
        """Toggle timed lyrics"""

        current = await self._config.guild(context.guild).lyrics.timed()
        await self._config.guild(context.guild).lyrics.timed.set(not current)
        message = (
            _("I have now turned off timed lyrics in this server.")
            if current
            else _(
                "I have now turned on timed lyrics in this server. I will send the lyrics as the track progresses if I can find lyrics for the playing track."
            )
        )
        await context.send(
            embed=await context.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_pllyrics_set.command(name="full")
    async def command_pllyrics_set_full(self, context: PyLavContext):
        """Show full lyrics on track start timed lyrics"""

        current = await self._config.guild(context.guild).lyrics.timed()
        await self._config.guild(context.guild).lyrics.full.set(not current)

        message = (
            _("I have now turned off full lyrics in this server.")
            if current
            else _(
                "I have now turned on full lyrics on this server. I will send a message with the full lyrics at the start of a song if I can find lyrics for the playing track."
            )
        )
        await context.send(
            embed=await context.pylav.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_pllyrics_set.command(name="channel")
    async def command_pllyrics_set_channel(
        self, context: PyLavContext, channel: discord.TextChannel | discord.Thread | None = None
    ):
        """Set the lyrics channel"""
        if channel:
            await self._config.guild(context.guild).lyrics.channel.set(channel.id)
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_(
                        "I have set the channel I will use to send lyrics to {channel_variable_do_not_translate}."
                    ).format(channel_variable_do_not_translate=channel.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await self._config.guild(context.guild).lyrics.channel.clear()
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("From now on, I will not send lyrics to any channel."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_pllyrics.command(name="show")
    @requires_player()
    async def command_pllyrics_show(self, context: PyLavContext):
        """Show lyrics for current track if available"""

        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if not context.player.current:
            await context.send(
                embed=await context.pylav.construct_embed(
                    description=_("I am not currently playing anything on this server."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        await self._send_full_lyrics(
            track=context.player.current,
            guild=context.guild,
            send_error=True,
            channel_id=context.channel.id,
            manual=True,
        )

    async def cog_unload(self) -> None:
        for task in self._tasks:
            with contextlib.suppress(Exception):
                task.cancel()

    async def _send_full_lyrics(
        self, track: Track, channel_id: int, guild: discord.Guild, send_error: bool = False, manual: bool = False
    ) -> None:
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        player = self.pylav.player_manager.get(guild.id)
        if not player:
            return
        if not player.current:
            return
        if (
            guild.id not in self._track_cache
            or (self._track_cache[guild.id] and self._track_cache[guild.id] != track.encoded)
        ) and not manual:
            return
        try:
            exact, response = await track.fetch_lyrics()
        except HTTPException as e:
            if not send_error:
                return
            await channel.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "I have encountered an error while looking for the lyrics for this song: {error_variable_do_not_translate}."
                    ).format(error_variable_do_not_translate=e),
                    messageable=channel,
                ),
            )
            return
        if isinstance(response, Error):
            if not send_error:
                return
            await channel.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "The Flowery API, which I use to find lyrics, has returned an error while looking for the lyrics for this song {error_variable_do_not_translate}."
                    ).format(error_variable_do_not_translate=response.error),
                    messageable=channel,
                ),
            )
            return
        if not response or not response.lyrics:
            if not send_error:
                return
            await channel.send(
                embed=await self.pylav.construct_embed(
                    description=_("No lyrics found."),
                    messageable=channel,
                ),
            )
            return
        lyrics = response.lyrics.text
        show_author = await track.source() in {"deezer", "spotify", "applemusic"}
        if guild.id not in self._track_cache or (
            self._track_cache[guild.id] and self._track_cache[guild.id] != track.encoded
        ):
            return
        await self._send_lyrics_messages(channel, exact, lyrics, response, show_author, track, manual)

    @staticmethod
    def _get_translated_automated_message_contents(exact: bool, show_author: bool, part: int | None = None):
        if part:
            if exact:
                return (
                    _(
                        "Lyrics for {title_variable_do_not_translate} by {author_variable_do_not_translate} - Part {page_variable_do_not_translate}"
                    )
                    if show_author
                    else _("Lyrics for {title_variable_do_not_translate} - Part {page_variable_do_not_translate}")
                )
            else:
                return (
                    _(
                        "(Guess) Lyrics for {title_variable_do_not_translate} by {author_variable_do_not_translate} - Part {page_variable_do_not_translate}"
                    )
                    if show_author
                    else _(
                        "(Guess) Lyrics for {title_variable_do_not_translate} - Part {page_variable_do_not_translate}"
                    )
                )
        elif exact:
            return (
                _("Lyrics for {title_variable_do_not_translate} by {author_variable_do_not_translate}")
                if show_author
                else _("Lyrics for {title_variable_do_not_translate}")
            )
        else:
            return (
                _("(Guess) Lyrics for {title_variable_do_not_translate} by {author_variable_do_not_translate}")
                if show_author
                else _("(Guess) Lyrics for {title_variable_do_not_translate}")
            )

    @staticmethod
    def _get_translated_message_contents(exact: bool, show_author: bool, part: int | None = None) -> str:
        if part:
            if exact:
                return (
                    _(
                        "{title_variable_do_not_translate} by {author_variable_do_not_translate} - Part {page_variable_do_not_translate}"
                    )
                    if show_author
                    else _("{title_variable_do_not_translate} - Part {page_variable_do_not_translate}")
                )
            else:
                return (
                    _(
                        "(Guess) {title_variable_do_not_translate} by {author_variable_do_not_translate} - Part {page_variable_do_not_translate}"
                    )
                    if show_author
                    else _("(Guess) {title_variable_do_not_translate} - Part {page_variable_do_not_translate}")
                )
        elif exact:
            return (
                _("{title_variable_do_not_translate} by {author_variable_do_not_translate}")
                if show_author
                else _("{title_variable_do_not_translate}")
            )
        else:
            return (
                _("(Guess) {title_variable_do_not_translate} by {author_variable_do_not_translate}")
                if show_author
                else _("(Guess) {title_variable_do_not_translate}")
            )

    async def _send_lyrics_messages(self, channel, exact, lyrics, response, show_author, track, manual):
        if len(lyrics) > 3950:
            embed_list = []
            for i, page in enumerate(pagify(lyrics, delims=["\n"], page_length=3950), start=1):
                translated_message = (
                    self._get_translated_message_contents(exact, show_author, i)
                    if manual
                    else self._get_translated_automated_message_contents(exact, show_author, i)
                )
                embed_list.append(
                    await self.pylav.construct_embed(
                        title=translated_message.format(
                            title_variable_do_not_translate=await track.title(),
                            page_variable_do_not_translate=i,
                            author_variable_do_not_translate=await track.author(),
                        ),
                        url=await track.uri(),
                        description=page,
                        thumbnail=await track.artworkUrl(),
                        footer=_("Lyrics provided by {provider_variable_do_not_translate}.").format(
                            provider_variable_do_not_translate=response.provider
                        ),
                        messageable=channel,
                    )
                )
            await channel.send(embeds=embed_list)
        else:
            translated_message = (
                self._get_translated_message_contents(exact, show_author, None)
                if manual
                else self._get_translated_automated_message_contents(exact, show_author, None)
            )
            await channel.send(
                embed=await self.pylav.construct_embed(
                    title=translated_message.format(
                        title_variable_do_not_translate=await track.title(),
                        author_variable_do_not_translate=await track.author(),
                    ),
                    url=await track.uri(),
                    description=lyrics,
                    thumbnail=await track.artworkUrl(),
                    footer=_("Lyrics provided by {provider_variable_do_not_translate}").format(
                        provider_variable_do_not_translate=response.provider
                    ),
                    messageable=channel,
                )
            )

    async def _send_timed_lyrics(self, track: Track, channel_id: int, guild: discord.Guild) -> None:
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        player = self.pylav.player_manager.get(guild.id)
        if not player:
            return
        if not player.current:
            return
        if player.current.encoded != track.encoded:
            return
        try:
            exact, response = await track.fetch_lyrics()
        except HTTPException:
            return
        if isinstance(response, Error):
            return
        if not response or not response.lyrics:
            return
        show_author = await track.source() in {"deezer", "spotify", "applemusic"}
        lyric_lines = len(response.lyrics.lines)
        splitter = lyric_lines // 5
        for chunk in [response.lyrics.lines[i : i + splitter] for i in range(0, lyric_lines, splitter)]:
            if not player.current:
                return
            if player.current.encoded != track.encoded:
                return
            sleep_duration = 0
            message_content = ""
            start_point = chunk[0].start
            if start_point < (player.estimated_position - 5000):
                continue
            for lyric in chunk:
                message_content += f"{lyric.text}\n"
                sleep_duration += lyric.duration
            delta = sleep_duration
            if player.timescale.changed:
                sleep_duration = player.timescale.adjust_position(sleep_duration)

            translated_message = self._get_translated_automated_message_contents(exact, show_author, None)
            await channel.send(
                embed=await self.pylav.construct_embed(
                    title=translated_message.format(
                        title_variable_do_not_translate=await track.title(),
                        author_variable_do_not_translate=await track.author(),
                    ),
                    url=await track.uri(),
                    description=_(
                        "{lyrics_variable_do_not_translate}\n\nPosition: {duration_variable_do_not_translate} until {until_variable_do_not_translate}"
                    ).format(
                        lyrics_variable_do_not_translate=message_content,
                        duration_variable_do_not_translate=format_time_dd_hh_mm_ss(start_point)
                        if start_point
                        else _("Start"),
                        until_variable_do_not_translate=format_time_dd_hh_mm_ss(start_point + delta),
                    ),
                    footer=_("Lyrics provided by {provider_variable_do_not_translate}.").format(
                        provider_variable_do_not_translate=response.provider
                    ),
                    thumbnail=await track.artworkUrl(),
                    messageable=channel,
                )
            )
            await asyncio.sleep(sleep_duration // 1000)

    async def process_event(self, event: TrackStartEvent):
        guild = event.player.guild
        if await self.bot.cog_disabled_in_guild(self, guild):
            return
        player = event.player
        if player.current is None:
            return
        self._track_cache[guild.id] = event.track.encoded
        await self.pylav.set_context_locale(player.guild)
        lyrics_config = await self._config.guild(player.guild).lyrics()
        if not lyrics_config["channel"]:
            return
        if lyrics_config["full"]:
            self._tasks.append(
                asyncio.create_task(
                    self._send_full_lyrics(
                        track=player.current, guild=player.guild, channel_id=lyrics_config["channel"]
                    )
                )
            )
            return
        elif lyrics_config["timed"]:
            self._tasks.append(
                asyncio.create_task(
                    self._send_timed_lyrics(
                        track=player.current, guild=player.guild, channel_id=lyrics_config["channel"]
                    )
                )
            )
            return
        for task in self._tasks:
            if task.done():
                self._tasks.remove(task)

    @commands.Cog.listener()
    async def on_pylav_track_start_event(self, event: TrackStartEvent) -> None:
        await self.process_event(event)
