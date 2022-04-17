from __future__ import annotations

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from pylav import Client, CogAlreadyRegistered, CogHasBeenRegistered, Query, QueryConverter
from pylav.utils import AsyncIter


class MediaPlayer(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        try:
            self.lavalink: Client = Client(bot=bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        except (CogHasBeenRegistered, CogAlreadyRegistered):
            self.lavalink: Client = self.bot.lavalink

    async def initialize(self):
        if not self.bot.lavalink.initialized:
            await self.bot.lavalink.initialize()

    async def cog_unload(self) -> None:
        pass
        # await self.bot.lavalink.unregister(cog=self)

    @commands.command(name="play", aliases=["p"])
    @commands.guild_only()
    @commands.is_owner()
    async def command_play(self, ctx: commands.Context, *, query: QueryConverter):
        """Match query to a song and play it."""
        query: Query
        if (player := self.lavalink.get_player(ctx.guild)) is None:
            player = await self.lavalink.connect_player(channel=ctx.author.voice.channel)

        tracks: dict = await self.lavalink.get_tracks(query)
        if not tracks:
            return await ctx.send("No results found.")
        if query.is_single:
            track = tracks["tracks"].pop(0)
            await player.add(requester=ctx.author.id, track=track["track"], query=query)
        else:
            tracks = tracks["tracks"]
            await player.bulk_add(
                requester=ctx.author.id, tracks_and_queries=[track["track"] async for track in AsyncIter(tracks)]
            )

        if not player.is_playing:
            await player.play()

        await ctx.send(f"{len(tracks)} Tracks enqueued")
