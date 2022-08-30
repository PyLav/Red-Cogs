from __future__ import annotations

from pathlib import Path

from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n

from pylav import Client, Query
from pylav.converters.radio import (
    CodecConverter,
    CountryCodeConverter,
    CountryConverter,
    LanguageConverter,
    StateConverter,
    StationConverter,
    TagConverter,
)
from pylav.radio.objects import Station
from pylav.types import BotT, InteractionT
from pylavcogs_shared.ui.prompts.generic import maybe_prompt_for_entry
from pylavcogs_shared.utils import rgetattr

LOGGER = getLogger("red.3pt.PyLavRadio")


T_ = Translator("PyLavRadio", Path(__file__))
_ = lambda s: s


@cog_i18n(T_)
class PyLavRadio(commands.Cog):
    lavalink: Client

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @app_commands.command(
        name="radio", description=_("Enqueue a radio station. Use the arguments to filter for possible station..")
    )
    @app_commands.guild_only()
    async def radio(
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
        """Enqueue a radio station."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        context = await self.bot.get_context(interaction)
        station: Station = await maybe_prompt_for_entry(
            cog=self,
            context=context,
            entries=stations,
            message_str=_("Multiple stations matched, pick the one which you meant."),
            selector_text=_("Pick a station"),
        )
        send = context.send
        author = context.author
        player = self.lavalink.get_player(context.guild.id)
        if player is None:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(config.forced_channel_id)) is None:
                channel = rgetattr(author, "voice.channel", None)
                if not channel:
                    await send(
                        embed=await self.lavalink.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect."), messageable=context
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await send(
                    embed=await self.lavalink.construct_embed(
                        description=_("I don't have permission to connect or speak in {channel}.").format(
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
        LOGGER.debug(f"Query: {query.requires_capability}")
        successful, count, failed = await self.lavalink.get_all_tracks_for_queries(
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
                embed=await self.lavalink.construct_embed(
                    description=_("Enqueued **[{station_name}]({station_url})**.").format(
                        station_name=station.name, station_url=url
                    ),
                    thumbnail=await single_track.thumbnail(),
                    messageable=context,
                ),
                ephemeral=True,
            )
            await station.click()
        else:
            await send(
                embed=await self.lavalink.construct_embed(
                    description=_("Unable to play **[{station_name}]({station_url})**.").format(
                        station_name=station.name, station_url=url
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )


_ = T_
