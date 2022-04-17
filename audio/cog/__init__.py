from __future__ import annotations

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from pylav import Client, CogAlreadyRegistered, CogHasBeenRegistered, QueryConverter


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
        if (player := self.lavalink.get_player(ctx.guild)) is None:
            player = await self.lavalink.connect_player(channel=ctx.author.voice.channel)

        tracks = await self.lavalink.get_tracks(query)
        if not tracks:
            return await ctx.send("No results found.")
        if query.is_single:
            tracks = [tracks["tracks"].pop(0)]
        else:
            tracks = tracks["tracks"]
        await player.bulk_add(requester=ctx.author.id, tracks_and_queries=[(track["track"], query) for track in tracks])

        if not player.is_playing:
            await player.play()

        await ctx.tick(message=f"{len(tracks)} Tracks enqueued")
