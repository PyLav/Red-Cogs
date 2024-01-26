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
from pylav.extension.red.utils import rgetattr
from pylav.extension.red.utils.decorators import invoker_is_dj
from pylav.extension.red.utils.validators import valid_query_attachment
from pylav.helpers.format.strings import shorten_string
from pylav.logging import getLogger
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

from audio.shared import SharedMethods

LOGGER = getLogger("PyLav.cog.Player.commands.slashes")
_ = Translator("PyLavPlayer", Path(__file__))


class SlashCommands(DISCORD_COG_TYPE_MIXIN, SharedMethods):
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
        try:
            response = await interaction.client.pylav.search_query(
                original_query,
                fullsearch=True,
                player=interaction.client.pylav.get_player(interaction.guild.id),
            )
        except Exception as e:
            LOGGER.debug(f"Error searching for {original_query}", exc_info=e)
            return [
                Choice(
                    name=shorten_string(
                        max_length=100,
                        string=_("Error searching {service_name_variable_do_not_translate}").format(
                            service_name_variable_do_not_translate=inv_map.get(prefix, fallback_source)
                        ),
                    ),
                    value="FqgqQW21tQ@#1g2fasf2",
                )
            ]
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
        match response.loadType:
            case "track":
                tracks = [response.data]
            case "search":
                tracks = response.data
            case "playlist":
                tracks = response.data.tracks
            case __:
                tracks = []
        tracks = tracks[:25]
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
        player = interaction.client.pylav.get_player(interaction.guild.id)

        for track in tracks:
            track = await Track.build_track(
                node=node, data=track, query=original_query, requester=interaction.user.id, player_instance=player
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

    @app_commands.command(
        name="play",
        description=shorten_string(max_length=100, string=_("Enqueue the specified query to be played.")),
        extras={"red_force_enable": True},
    )
    @app_commands.describe(
        query=shorten_string(max_length=100, string=_("This argument is the query to play, a link or a search query."))
    )
    @app_commands.choices(
        enqueue_type=[
            app_commands.Choice(name=_("Play Now"), value="play_now"),
            app_commands.Choice(name=_("Play Next"), value="play_next"),
            app_commands.Choice(name=_("Add to Queue"), value="add_to_queue"),
        ]
    )
    @app_commands.guild_only()
    @invoker_is_dj(slash=True)
    async def slash_play(
        self,
        interaction: DISCORD_INTERACTION_TYPE,
        query: str = None,
        enqueue_type: app_commands.Choice[str] = "add_to_queue",
    ):  # sourcery skip: low-code-quality
        """Attempt to play the queries which you provide.

        Separate multiple queries with a new line (`shift + enter`).

        If you want to play a local track, you can specify the full path relative to the local tracks' folder.
        For example, if my local tracks folder is: `/home/draper/music`.

        I can play a single track with `track.mp3` or `/home/draper/music/track.mp3`.
        I can play everything inside a folder with a `sub-folder/folder`.
        I can play everything inside a folder and its sub-folders with the `all:` prefix, i.e. `all:sub-folder/folder`.

        You can search specific services by using the following prefixes*:
        `dzsearch:`  - Deezer
        `spsearch:`  - Spotify
        `amsearch:`  - Apple Music
        `ytmsearch:` - YouTube Music
        `ytsearch:`  - YouTube
        `scsearch:`  - SoundCloud
        `ymsearch:`  - Yandex Music

        You can trigger text-to-speech by using the following prefixes*:
        `speak:` - I will speak the query (limited to 200 characters)
        `tts://` - I will speak the query
        """
        context = await self.bot.get_context(interaction)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if query is None:
            if attachments := context.message.attachments:
                query = "\n".join(
                    attachment.url for attachment in attachments if valid_query_attachment(attachment.filename)
                )
        if not query:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("You need to give me a query to enqueue."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        player = self.pylav.get_player(context.guild.id)
        if player is None:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(context.author, "voice.channel", None)
                if not channel:
                    await context.send(
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
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_name_variable_do_not_translate}."
                        ).format(channel_name_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=context.author)
        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        total_tracks_enqueue = 0
        single_track = None
        if isinstance(enqueue_type, app_commands.Choice):
            enqueue_type = enqueue_type.value
        match enqueue_type:
            case "play_now":
                priority = -1
                index = 0
            case "play_next":
                priority = 1
                index = 0
            case __:
                priority = 100
                index = None
        LOGGER.info(f"Priority: {priority}, Index: {index}")
        if queries:
            single_track, total_tracks_enqueue = await self._process_play_queries(
                context, queries, player, single_track, total_tracks_enqueue, index
            )
        if (not (player.is_active or player.queue.empty())) or priority == -1:
            await player.next(requester=context.author)

        await self._process_play_message(context, single_track, total_tracks_enqueue, queries)
