from abc import ABC
from typing import Optional

from redbot.core import commands

from pylav import Track, converters
from pylav.utils import AsyncIter

from audio.cog import MPMixin
from audio.cog.menus.menus import QueueMenu
from audio.cog.menus.sources import QueueSource


class HybridCommands(MPMixin, ABC):
    @commands.hybrid_command(name="play", description="Plays a specified query.", aliases=["p"])
    async def command_play(self, ctx: commands.Context, *, query: converters.QueryConverter):
        """Displays your currently played spotify song"""
        await ctx.defer(ephemeral=True)

        if (player := self.lavalink.get_player(ctx.guild)) is None:
            player = await self.lavalink.connect_player(channel=ctx.author.voice.channel)
        is_partial = query.is_search
        tracks = {}
        if not is_partial:
            tracks: dict = await self.lavalink.get_tracks(query)
            if not tracks:
                await ctx.send(f"No results found for {await query.query_to_string()}", ephemeral=True)
                return
        if is_partial:
            track = Track(node=player.node, data=None, query=query, extra={"requester": ctx.author.id})
            await player.add(requester=ctx.author.id, track=track)
            await ctx.send(f"{await track.get_track_display_name(with_url=True)} enqueued", ephemeral=True)
        elif query.is_single:
            track = Track(
                node=player.node,
                data=tracks["tracks"][0],
                query=query.with_index(0),
                extra={"requester": ctx.author.id},
            )
            await player.add(requester=ctx.author.id, track=track)
            await ctx.send(f"{await track.get_track_display_name(with_url=True)} enqueued", ephemeral=True)
        else:
            tracks = tracks["tracks"]
            track_count = len(tracks)
            await player.bulk_add(
                requester=ctx.author.id,
                tracks_and_queries=[
                    Track(
                        node=player.node,
                        data=track["track"],
                        query=query.with_index(i),
                        extra={"requester": ctx.author.id},
                    )
                    async for i, track in AsyncIter(tracks).enumerate()
                ],
            )
            await ctx.send(f"{track_count} tracks enqueued", ephemeral=True)

        if not player.is_playing:
            await player.play()

    @commands.hybrid_command(name="np", description="Shows the track currently being played.")
    async def commmand_now(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await ctx.send("Nothing is playing.", ephemeral=True)
            return
        current_embed = await player.get_currently_playing_message()
        await ctx.send(embed=current_embed, ephemeral=True)

    @commands.hybrid_command(name="skip", description="Skips or votes to skip the current track.")
    async def commmand_skip(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await ctx.send("Nothing is playing.", ephemeral=True)
            return
        track_name = await player.current.get_track_display_name(with_url=True)
        await player.skip()
        await ctx.send(embed=await self.lavalink.construct_embed(description=f"Skipped - {track_name}"), ephemeral=True)

    @commands.hybrid_command(name="stop", description="Stops the player and remove all tracks from the queue.")
    async def commmand_stop(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await ctx.send("Nothing is playing.", ephemeral=True)
            return
        await player.stop()
        await ctx.send("Player stopped", ephemeral=True)

    @commands.hybrid_command(name="dc", description="Disconnects the player from the voice channel.")
    async def command_disconnect(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        await player.disconnect()
        await ctx.send("Disconnected from voice channel", ephemeral=True)

    @commands.hybrid_command(name="queue", description="Shows the current queue for the player.")
    async def commmand_queue(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if player.queue.empty():
            await ctx.send("There is nothing in the queue.", ephemeral=True)
            return
        await QueueMenu(cog=self, bot=self.bot, source=QueueSource(guild_id=ctx.guild.id, cog=self)).start(ctx=ctx)

    @commands.hybrid_command(name="shuffle", description="Shuffles the player's queue.")
    async def commmand_shuffle(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if player.queue.empty():
            await ctx.send("There is nothing in the queue.", ephemeral=True)
            return
        await player.shuffle_queue()
        await ctx.send(f"{player.queue.qsize()} tracks shuffled", ephemeral=True)

    @commands.hybrid_command(name="repeat", description="Set whether to repeat current song or queue.")
    async def commmand_repeat(self, ctx: commands.Context, queue: Optional[bool] = None):
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return
        if queue:
            player.repeat_queue = True
            player.repeat_current = False
            msg = "Repeating the queue"
        else:
            if player.repeat_queue:
                player.repeat_queue = False
                player.repeat_current = False
                msg = "Repeating disabled"
            else:
                player.repeat_current = True
                player.repeat_queue = False
                msg = f"Repeating {await player.current.get_track_display_name(with_url=True)}"
        await ctx.send(embed=await self.lavalink.construct_embed(description=msg), ephemeral=True)
