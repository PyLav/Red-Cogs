import hashlib
from abc import ABC
from pathlib import Path
from typing import Literal

from discord import app_commands
from discord.app_commands import Choice
from expiringdict import ExpiringDict
from redbot.core.i18n import Translator

from pylav import getLogger
from pylav.query import SEARCH_REGEX, Query
from pylav.red_utils.utils.decorators import invoker_is_dj
from pylav.tracks import Track
from pylav.types import InteractionT, PyLavCogMixin

LOGGER = getLogger("PyLav.cog.Player.commands.slashes")
_ = Translator("PyLavPlayer", Path(__file__))


class SlashCommands(PyLavCogMixin, ABC):
    _track_cache: ExpiringDict

    @app_commands.command(name="search", description=_("Search for a track, then play the selected response"))
    @app_commands.describe(source=_("Where to search in"), query=_("The query to search for search query"))
    @app_commands.guild_only()
    @invoker_is_dj(slash=True)
    async def slash_search(
        self,
        interaction: InteractionT,
        query: str,
        source: Literal["Deezer", "YouTube Music", "Spotify", "Apple Music", "SoundCloud", "YouTube", "Yandex Music"] = None,
    ):
        """Search for a track then play the selected response"""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if query == "FqgqQW21tQ@#1g2fasf2":
            return await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("You haven't selected something to play"),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        _track = self._track_cache.get(query)
        track = query if _track is None else await _track.query_identifier()
        await self.command_play.callback(self, interaction, query=track)

    @slash_search.autocomplete("query")
    async def slash_search_autocomplete_query(self, interaction: InteractionT, current: str):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        data = interaction.data
        prefix_mapping = {
            "YouTube Music": "ytmsearch:",
            "Spotify": "spsearch:",
            "Apple Music": "amsearch:",
            "Deezer": "dzsearch:",
            "SoundCloud": "scsearch:",
            "YouTube": "ytsearch:",
            "Yandex Music": "ymsearch:",
        }

        feature_mapping = {
            "ytmsearch:": "youtube",
            "spsearch:": "spotify",
            "amsearch:": "applemusic",
            "scsearch:": "soundcloud",
            "ytsearch:": "youtube",
            "dzsearch:": "deezer",
            "ymsearch:": "yandexmusic",
        }
        inv_map = {v: k for k, v in prefix_mapping.items()}
        if options := data.get("options", []):
            value_list = [v for v in options if v.get("name") == "source"]
            if value_list and (value := value_list[0].get("value")):
                prefix = prefix_mapping.get(value, "dzsearch:")
            else:
                prefix = "dzsearch:"
        else:
            prefix = "dzsearch:"
        match = SEARCH_REGEX.match(current)
        service = match.group("search_source") if match else None
        if not service:
            current = prefix + current
        feature = feature_mapping.get(prefix, "deezer")
        if not (match := SEARCH_REGEX.match(current)) or not match.group("search_query"):
            return [
                Choice(
                    name=_("Searching {service}").format(service=inv_map.get(prefix, "Deezer")),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        response = await interaction.client.lavalink.get_tracks(
            await Query.from_string(current),
            fullsearch=True,
            player=interaction.client.lavalink.get_player(interaction.guild.id),
        )
        if not response:
            return [
                Choice(
                    name=_("No results found on {service}").format(service=inv_map.get(prefix, "Deezer")),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        tracks = response.tracks[:25]
        if not tracks:
            return [
                Choice(
                    name=_("No results found on {service}").format(service=inv_map.get(prefix, "Deezer")),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        choices = []
        node = await interaction.client.lavalink.get_my_node()
        if node is None:
            node = interaction.client.lavalink.node_manager.find_best_node(feature=feature)

        for track in tracks:
            track = Track(
                node=node, data=track, query=await Query.from_base64(track.encoded), requester=interaction.user.id
            )
            track_id = hashlib.md5(track.encoded.encode()).hexdigest()
            self._track_cache[track_id] = track
            choices.append(
                Choice(
                    name=await track.get_track_display_name(max_length=95, unformatted=True, with_url=False),
                    value=track_id,
                )
            )
        return choices

    @slash_search.error
    async def slash_search_error(self, interaction: InteractionT, error: Exception):
        pass
