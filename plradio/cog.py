from __future__ import annotations

from pathlib import Path

from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from pylav.client import Client
from pylav.converters.radio import (
    CodecConverter,
    CountryCodeConverter,
    CountryConverter,
    LanguageConverter,
    StateConverter,
    StationConverter,
    TagConverter,
)
from pylav.query import Query
from pylav.radio.objects import Station
from pylav.red_utils.ui.prompts.generic import maybe_prompt_for_entry
from pylav.red_utils.utils import rgetattr
from pylav.types import BotT, InteractionT

LOGGER = getLogger("PyLav.cog.Radio")


_ = Translator("PyLavRadio", Path(__file__))


@cog_i18n(_)
class PyLavRadio(commands.Cog):
    lavalink: Client

    __version__ = "1.0.0.0rc1"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @app_commands.command(
        name="radio", description=_("Enqueue a radio station. Use the arguments to filter for a possible station")
    )
    @app_commands.describe(
        stations=_("The radio station to enqueue"),
        language=_("The language code to filter stations by"),
        countrycode=_("The country code to filter stations and countries by"),
        country=_("The country filter to filter stations and states by"),
        state=_("The state filter to filter stations by"),
        codec=_("The codec filter to filter stations by"),
        tag1=_("The tag filter to filter stations by"),
        tag2=_("The tag filter to filter stations by"),
        tag3=_("The tag filter to filter stations by"),
        tag4=_("The tag filter to filter stations by"),
        tag5=_("The tag filter to filter stations by"),
    )
    @app_commands.guild_only()
    async def slash_radio(
        self,
        interaction: InteractionT,
        stations: StationConverter,
        language: LanguageConverter = None,
        countrycode: CountryCodeConverter = None,
        country: CountryConverter = None,
        state: StateConverter = None,
        codec: CodecConverter = None,
        tag1: TagConverter = None,
        tag2: TagConverter = None,
        tag3: TagConverter = None,
        tag4: TagConverter = None,
        tag5: TagConverter = None,
    ):
        """Enqueue a radio station"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        if not stations:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("The Radio Browser functionality is currently unavailable"), messageable=context
                ),
                ephemeral=True,
            )
            return

        station: Station = await maybe_prompt_for_entry(
            cog=self,
            context=context,
            entries=stations,  # type: ignore
            message_str=_("Multiple stations matched, pick the one which you meant"),
            selector_text=_("Pick a station"),
        )
        send = context.send
        author = context.author
        player = self.lavalink.get_player(context.guild.id)
        if player is None:
            config = self.lavalink.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.lavalink.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect"), messageable=context
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await send(
                    embed=await self.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}").format(
                            channel=channel.mention
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.lavalink.connect_player(channel=channel, requester=author)

        total_tracks_enqueue = 0
        url = station.url_resolved or station.url
        query = await Query.from_string(url)
        successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
            query, requester=author, player=player, bypass_cache=True, partial=False
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
                embed=await self.lavalink.construct_embed(
                    description="{translation} **[{station_name}]({station_url})**".format(
                        station_name=station.name, station_url=url, translation=_("Enqueued")
                    ),
                    thumbnail=single_track.thumbnail,
                    messageable=context,
                ),
                ephemeral=True,
            )
            await station.click()
        else:
            await send(
                embed=await self.lavalink.construct_embed(
                    description="**[{station_name}]({station_url})**".format(
                        station_name=station.name, station_url=url, translation=_("Unable to play")
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
