from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from discord import app_commands
from discord.app_commands import Choice
from discord.ext.commands import HybridCommand
from expiringdict import ExpiringDict
from redbot.core.i18n import Translator

from pylav.constants.config import DEFAULT_SEARCH_SOURCE
from pylav.constants.regex import SOURCE_INPUT_MATCH_SEARCH
from pylav.extension.red.utils.decorators import invoker_is_dj
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

LOGGER = getLogger("PyLav.cog.Player.commands.slashes")
_ = Translator("PyLavPlayer", Path(__file__))


class SlashCommands(DISCORD_COG_TYPE_MIXIN):
    command_play: HybridCommand
    _track_cache: ExpiringDict

    @app_commands.command(
        name="search",
        description=shorten_string(max_length=100, string=_("Search for a track, then play the selected response.")),
        extras={"red_force_enable": True},
    )
    @app_commands.describe(
        source=shorten_string(max_length=100, string=_("Where to search in")),
        query=shorten_string(max_length=100, string=_("The query to search for search query")),
    )
    @app_commands.guild_only()
    @invoker_is_dj(slash=True)
    async def slash_search(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        query: str,
        source: Literal[  # noqa
            "Deezer", "YouTube Music", "Spotify", "Apple Music", "SoundCloud", "YouTube", "Yandex Music"
        ] = None,
    ):
        """Search for a track then play the selected response."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if query == "FqgqQW21tQ@#1g2fasf2":
            return await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("You have not selected something to play."),
                    messageable=interaction,
                ),
                ephemeral=True,
            )
        _track = self._track_cache.get(query)
        track = query if _track is None else _track
        await self.command_play.callback(self, interaction, query=track)

    @slash_search.autocomplete("query")
    async def slash_search_autocomplete_query(
        self, interaction: DISCORD_INTERACTION_TYPE, current: str
    ):  # sourcery skip: low-code-quality
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
        fallback_search = f"{DEFAULT_SEARCH_SOURCE}:"
        fallback_source = next(k for k, v in prefix_mapping.items() if v == f"{DEFAULT_SEARCH_SOURCE}:")
        fallback_feature = feature_mapping[fallback_search]
        if options := data.get("options", []):
            value_list = [v for v in options if v.get("name") == "source"]
            if value_list and (value := value_list[0].get("value")):
                prefix = prefix_mapping.get(value, fallback_search)
            else:
                prefix = fallback_search
        else:
            prefix = fallback_search
        match = SOURCE_INPUT_MATCH_SEARCH.match(current)
        service = match.group("search_source") if match else None
        if not service:
            current = prefix + current
        feature = feature_mapping.get(prefix, fallback_feature)
        if not (match := SOURCE_INPUT_MATCH_SEARCH.match(current)) or not match.group("search_query"):
            return [
                Choice(
                    name=shorten_string(
                        max_length=100,
                        string=_("Searching {service_name_variable_do_not_translate}").format(
                            service_name_variable_do_not_translate=inv_map.get(prefix, fallback_source)
                        ),
                    ),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        original_query = await Query.from_string(current)
        response = await interaction.client.pylav.get_tracks(
            original_query,
            fullsearch=True,
            player=interaction.client.pylav.get_player(interaction.guild.id),
        )
        if not response:
            return [
                Choice(
                    name=shorten_string(
                        max_length=100,
                        string=_("No results found on {service_name_variable_do_not_translate}").format(
                            service_name_variable_do_not_translate=inv_map.get(prefix, fallback_source)
                        ),
                    ),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        tracks = response.tracks[:25]
        if not tracks:
            return [
                Choice(
                    name=shorten_string(
                        max_length=100,
                        string=_("No results found on {service_name_variable_do_not_translate}").format(
                            service_name_variable_do_not_translate=inv_map.get(prefix, fallback_source)
                        ),
                    ),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
        choices = []
        node = interaction.client.pylav.get_my_node()
        if node is None:
            node = await interaction.client.pylav.node_manager.find_best_node(feature=feature)

        for track in tracks:
            track = await Track.build_track(
                node=node, data=track, query=original_query, requester=interaction.user.id, player_instance=None
            )
            if track is None:
                continue
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
    async def slash_search_error(self, interaction: DISCORD_INTERACTION_TYPE, error: Exception):
        pass
