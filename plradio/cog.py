from __future__ import annotations

import typing
from pathlib import Path

from discord import app_commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.core.client import Client
from pylav.extension.radio.objects import Station
from pylav.extension.red.ui.prompts.generic import maybe_prompt_for_entry
from pylav.extension.red.utils import rgetattr
from pylav.helpers.discord.converters.radio import (
    CodecConverter,
    CountryCodeConverter,
    CountryConverter,
    LanguageConverter,
    StateConverter,
    StationConverter,
    TagConverter,
)
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_BOT_TYPE, DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

LOGGER = getLogger("PyLav.cog.Radio")


_ = Translator("PyLavRadio", Path(__file__))


@cog_i18n(_)
class PyLavRadio(DISCORD_COG_TYPE_MIXIN):
    lavalink: Client

    __version__ = "1.0.0"

    def __init__(self, bot: DISCORD_BOT_TYPE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @app_commands.command(
        name="radio",
        description=shorten_string(
            max_length=100, string=_("Enqueue a radio station. Use the arguments to filter for a possible station")
        ),
    )
    @app_commands.describe(
        stations=shorten_string(max_length=100, string=_("The radio station to enqueue")),
        language=shorten_string(max_length=100, string=_("The language code to filter stations by")),
        countrycode=shorten_string(max_length=100, string=_("The country code to filter stations and countries by")),
        country=shorten_string(max_length=100, string=_("The country filter to filter stations and states by")),
        state=shorten_string(max_length=100, string=_("The state filter to filter stations by")),
        codec=shorten_string(max_length=100, string=_("The codec filter to filter stations by")),
        tag1=shorten_string(max_length=100, string=_("The tag filter to filter stations by")),
        tag2=shorten_string(max_length=100, string=_("The tag filter to filter stations by")),
        tag3=shorten_string(max_length=100, string=_("The tag filter to filter stations by")),
        tag4=shorten_string(max_length=100, string=_("The tag filter to filter stations by")),
        tag5=shorten_string(max_length=100, string=_("The tag filter to filter stations by")),
    )
    @app_commands.guild_only()
    async def slash_radio(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        stations: StationConverter,
        language: LanguageConverter = None,  # noqa
        countrycode: CountryCodeConverter = None,  # noqa
        country: CountryConverter = None,  # noqa
        state: StateConverter = None,  # noqa
        codec: CodecConverter = None,  # noqa
        tag1: TagConverter = None,  # noqa
        tag2: TagConverter = None,  # noqa
        tag3: TagConverter = None,  # noqa
        tag4: TagConverter = None,  # noqa
        tag5: TagConverter = None,  # noqa
    ):  # sourcery skip: low-code-quality
        """Enqueue a radio station"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not stations:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("The Radio Browser functionality is currently unavailable."), messageable=context
                ),
                ephemeral=True,
            )
            return
        stations = typing.cast(list[Station], stations)
        station = await maybe_prompt_for_entry(
            cog=self,
            context=context,
            entries=stations,
            message_str=_("Multiple stations matched, pick the one which you meant"),
            selector_text=shorten_string(max_length=100, string=_("Pick a station")),
        )
        send = context.send
        author = context.author
        player = self.pylav.get_player(context.guild.id)
        if player is None:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel, so I can connect to it."),
                            messageable=context,
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_variable_do_not_translate}."
                        ).format(channel_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=author)

        total_tracks_enqueue = 0
        url = station.url_resolved or station.url
        query = await Query.from_string(url)
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            query, requester=author, player=player, bypass_cache=True
        )
        single_track = successful[0] if successful else None
        total_tracks_enqueue += count
        failed_queries = []
        failed_queries.extend(failed)
        if total_tracks_enqueue:
            await player.add(requester=author.id, track=successful[0])
        if not player.is_playing and not player.queue.empty():
            await player.next(requester=author)

        if total_tracks_enqueue == 1:
            await send(
                embed=await self.pylav.construct_embed(
                    description="{translation} **[{station_name}]({station_url})**".format(
                        station_name=station.name, station_url=url, translation=_("Enqueued")
                    ),
                    thumbnail=await single_track.artworkUrl(),
                    messageable=context,
                ),
                ephemeral=True,
            )
            await station.click()
        else:
            await send(
                embed=await self.pylav.construct_embed(
                    description="{translation} **[{station_name}]({station_url})**".format(
                        station_name=station.name, station_url=url, translation=_("Unable to play")
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
