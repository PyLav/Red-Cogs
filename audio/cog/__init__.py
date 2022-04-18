from __future__ import annotations

from abc import ABC
from typing import Literal

from discord import Object
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from pylav import Client, CogAlreadyRegistered, CogHasBeenRegistered, Track, converters
from pylav.utils import AsyncIter

from audio.cog.abc import MPMixin
from audio.cog.slash import MPSlash


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """


class MediaPlayer(
    commands.Cog,
    MPSlash,
    metaclass=CompositeMetaClass,
):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        try:
            self.lavalink: Client = Client(bot=bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        except (CogHasBeenRegistered, CogAlreadyRegistered):
            self.lavalink: Client = self.bot.lavalink
            # self.lavalink is easier for type hinting
            #   However this is here just for the sake of completeness
            #   you can access the client via self.bot.lavalink if you prefer
            #   the only important thing here is that you initialize the client and handle the 3 exceptions it can throw
            #   CogHasBeenRegistered, CogAlreadyRegistered, AnotherClientAlreadyRegistered
            #   In this example I don't handle AnotherClientAlreadyRegistered, as I want the cog to error loading
            #   if another client is already registered (i.e lavalink.py)
        self.config = Config.get_conf(self, identifier=208903205982044161)
        self.config.register_guild(enable_slash=True, enable_context=False)
        self.config.register_global(
            enable_slash=False,
            enable_context=False,
        )

    async def initialize(self) -> None:
        if not self.lavalink.initialized:
            await self.lavalink.initialize()

    async def _sync_tree(self) -> None:
        await self.bot.wait_until_red_ready()
        await self.bot.tree.sync()
        await self.bot.tree.sync(guild=Object(id=133049272517001216))

    async def cog_unload(self) -> None:
        # await self.bot.lavalink.unregister(cog=self)
        self.bot.tree.remove_command(self.slash_now.name, type=self.slash_now.type)
        self.bot.tree.remove_command(self.slash_play.name, type=self.slash_play.type)
        self.bot.tree.remove_command(self.slash_skip.name, type=self.slash_skip.type)
        self.bot.tree.remove_command(self.slash_stop.name, type=self.slash_stop.type)
        self.bot.tree.remove_command(self.slash_queue.name, type=self.slash_queue.type)
        self.bot.tree.remove_command(self.slash_disconnect.name, type=self.slash_disconnect.type)
        self.bot.tree.remove_command(self.slash_shuffle.name, type=self.slash_shuffle.type)
        self.bot.tree.remove_command(self.slash_repeat.name, type=self.slash_repeat.type)

    @commands.command(name="play", aliases=["p"])
    @commands.guild_only()
    @commands.is_owner()
    async def command_play(self, context: commands.Context, *, query: converters.QueryConverter) -> None:
        """Match query to a song and play it."""
        user = context.author
        guild = context.guild
        if (player := self.lavalink.get_player(guild)) is None:
            player = await self.lavalink.connect_player(channel=user.voice.channel)
        is_partial = query.is_search
        if not is_partial:
            tracks: dict = await self.lavalink.get_tracks(query)
            if not tracks:
                await context.send(f"No results found for {await query.query_to_string()}")
                return
        if is_partial:
            track = Track(node=player.node, data=None, query=query, extra={"requester": user.id})
            await player.add(requester=user.id, track=track, query=query)
            await context.send(f"{await track.get_track_display_name()} enqueued")
        elif query.is_single:
            track = Track(node=player.node, data=tracks["tracks"].pop(0), query=query, extra={"requester": user.id})
            await player.add(requester=user.id, track=track["track"], query=query)
            await context.send(f"{await track.get_track_display_name()} enqueued")
        else:
            tracks = tracks["tracks"]
            track_count = len(tracks)
            await player.bulk_add(
                requester=user.id, tracks_and_queries=[track["track"] async for track in AsyncIter(tracks)]
            )
            await context.send(f"{track_count} tracks enqueued")

        if not player.is_playing:
            await player.play()

    @commands.command(name="sync")
    @commands.guild_only()
    @commands.is_owner()
    async def command_sync(self, context: commands.Context) -> None:
        """Sync the tree with the current guild."""
        await self._sync_tree()
        await context.send("Synced tree with guild")

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name: str, api_tokens: dict[str, str]) -> None:
        if service_name == "spotify":
            ...  # Update lib with new token

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """
        Method for finding users data inside the cog and deleting it.
        """
        await self.config.user_from_id(user_id).clear()
