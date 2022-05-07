from __future__ import annotations

import asyncio
from pathlib import Path

import aiopath
from red_commons.logging import getLogger
from redbot.cogs.audio.apis.api_utils import PlaylistFetchResult
from redbot.cogs.audio.apis.playlist_wrapper import PlaylistWrapper
from redbot.cogs.audio.utils import (
    DEFAULT_LAVALINK_SETTINGS,
    DEFAULT_LAVALINK_YAML,
    PlaylistScope,
    change_dict_naming_convention,
)
from redbot.core import Config, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.dbtools import APSWConnectionWrapper

from pylav import Client
from pylav.sql.models import LibConfigModel
from pylav.types import BotT
from pylav.utils import AsyncIter, PyLavContext
from pylavcogs_shared.utils import recursive_merge

LOGGER = getLogger("red.3pt.PyLavMigrator")

_ = Translator("PyLavMigrator", Path(__file__))


@cog_i18n(_)
class PyLavMigrator(commands.Cog):
    lavalink: Client

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._init_task = None
        self.lavalink = Client(bot=self.bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))

    async def initialize(self) -> None:
        await self.lavalink.register(self)
        await self.lavalink.initialize()

    async def cog_unload(self) -> None:
        if self._init_task is not None:
            self._init_task.cancel()
        await self.bot.lavalink.unregister(cog=self)

    @commands.is_owner()
    @commands.command(name="pylavmigrate")
    async def pylavmigrate(self, context: PyLavContext, confirm: bool, /) -> None:
        """Migrate Audio settings to PyLav

        Please note that this will replace any config already in PyLav.

        If you are sure you want to proceed please run this command again with the confirm argument set to 1
        i.e `[p]pylavmigrate 1`
        """
        if not confirm:
            await context.send_help()
            return

        async with context.typing():
            audio_config = Config.get_conf(None, identifier=2711759130, cog_name="Audio")
            default_global = dict(
                use_external_lavalink=False,  # Supported in PyLav
                localpath=str(cog_data_path(raw_name="Audio")),  # Supported in PyLav
                java_exc_path="java",  # Supported in PyLav
                **DEFAULT_LAVALINK_YAML,  # Supported in PyLav
                **DEFAULT_LAVALINK_SETTINGS,  # Supported in PyLav
            )

            default_guild = dict(
                auto_play=False,  # Supported in PyLav
                auto_deafen=True,  # Supported in PyLav
                autoplaylist=dict(
                    enabled=True,  # Supported in PyLav
                    id=42069,  # Supported in PyLav
                ),
                disconnect=False,  # Supported in PyLav
                emptydc_enabled=False,  # Supported in PyLav
                emptydc_timer=0,  # Supported in PyLav
                emptypause_enabled=False,  # Supported in PyLav
                emptypause_timer=0,  # Supported in PyLav
                max_volume=150,  # Supported in PyLav
                shuffle=False,  # Supported in PyLav
                volume=100,  # Supported in PyLav
            )
            _playlist = dict(id=None, author=None, name=None, playlist_url=None, tracks=[])
            audio_config.init_custom("EQUALIZER", 1)
            audio_config.register_custom("EQUALIZER", eq_bands=[], eq_presets={})
            audio_config.init_custom(PlaylistScope.GLOBAL.value, 1)
            audio_config.register_custom(PlaylistScope.GLOBAL.value, **_playlist)
            audio_config.init_custom(PlaylistScope.GUILD.value, 2)
            audio_config.register_custom(PlaylistScope.GUILD.value, **_playlist)
            audio_config.init_custom(PlaylistScope.USER.value, 2)
            audio_config.register_custom(PlaylistScope.USER.value, **_playlist)
            audio_config.register_guild(**default_guild)
            audio_config.register_global(**default_global)
            audio_config.register_user(country_code=None)
            audio_db_conn = APSWConnectionWrapper(str(cog_data_path(self.bot.get_cog("Audio")) / "Audio.db"))
            playlist_api = PlaylistWrapper(self.bot, audio_config, audio_db_conn)
            await playlist_api.init()

            global_config = await LibConfigModel(bot=self.bot.user.id, id=1).get_all()
            if (r := await audio_config.java_exc_path()) and r != "java":
                await global_config.set_java_path(r)
            if r := await audio_config.localpath():
                path = aiopath.AsyncPath(r)
                localtracks_path = path / "localtracks"
                try:
                    if await localtracks_path.exists():
                        await global_config.set_localtrack_folder(f"{localtracks_path}")
                except PermissionError:
                    await context.send(
                        embed=await self.lavalink.construct_embed(
                            description=_("I don't have permission to access {folder}.").format(folder=localtracks_path)
                        )
                    )
            if __ := await audio_config.use_external_lavalink():
                await global_config.set_enable_managed_node(False)
                await self.lavalink.add_node(
                    unique_identifier=context.message.id,
                    name="AudioMigratedExternal",
                    host=await audio_config.host(),
                    password=await audio_config.password(),
                    port=await audio_config.rest_port(),
                    ssl=await audio_config.secured_ws(),
                    search_only=False,
                    managed=False,
                    extras=None,
                    disabled_sources=None,
                    yaml=None,
                    skip_db=False,
                )
            else:
                audio_yaml = change_dict_naming_convention(await audio_config.yaml.all())
                bundled_node_config = await self.lavalink.node_db_manager.get_bundled_node_config()
                bundled_node_config.yaml = recursive_merge(bundled_node_config.yaml, audio_yaml)
                bundled_node_config.extras["max_ram"] = await audio_config.java.Xmx()
                await bundled_node_config.save()

        async for guild, guild_config in AsyncIter((await audio_config.all_guilds()).items()):
            player_config = await self.lavalink.player_config_manager.get_config(guild)
            if not guild_config.get("auto_deafen", True):
                player_config.self_deaf = False
            if guild_config.get("autoplaylist", {}).get("enabled", False):
                player_config.auto_play = True
                saved_id = guild_config.get("autoplaylist", {}).get("id", 42069)
                player_config.auto_play_playlist_id = saved_id if saved_id != 42069 else 1
            else:
                player_config.auto_play = False
            if guild_config.get("shuffle", False):
                player_config.shuffle = True
            if guild_config.get("volume", 100) != 100:
                player_config.volume = guild_config.get("volume")

            if guild_config.get("max_volume", 150) != 150:
                player_config.max_volume = guild_config.get("max_volume") / 150
                player_config.extras["max_volume"] = int((guild_config.get("max_volume") / 150) * 1000)

            if guild_config.get("emptypause_enabled"):
                player_config.extras["alone_pause"] = [True, guild_config.get("emptypause_timer", 60)]

            if guild_config.get("emptydc_enabled"):
                player_config.extras["alone_dc"] = [True, guild_config.get("emptydc_timer", 60)]

            if guild_config.get("disconnect"):
                player_config.extras["empty_queue_dc"] = [True, 60]

            await player_config.save()
        query = """
        SELECT
            playlist_id,
            playlist_name,
            scope_id,
            author_id,
            playlist_url,
            tracks
        FROM
            playlists"""
        row_results = await asyncio.to_thread(playlist_api.database.cursor().execute, query)
        async for row in AsyncIter(row_results):
            pl = PlaylistFetchResult(*row)
            if pl.playlist_id == 42069:
                continue

            await self.lavalink.playlist_db_manager.create_or_update_playlist(
                id=pl.playlist_id,
                name=pl.playlist_name,
                scope=pl.scope_id,
                author=pl.author_id,
                url=pl.playlist_url,
                tracks=[t["track"] for t in pl.tracks if "track" in t],
            )
        await context.send(
            content=_(
                "Migration of Audio cog settings to MediaPlayer cog complete. "
                "Restart the bot for it to take effect.\n{requester}"
            ).format(requester=context.author.mention),
            ephemeral=True,
        )
