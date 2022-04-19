from abc import ABC
from typing import Optional

import discord
from discord import app_commands
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.commands import Context

from pylav import Track, converters
from pylav.utils import AsyncIter

from audio.cog import MY_GUILD, MPMixin
from audio.cog.menus.menus import QueueMenu
from audio.cog.menus.sources import QueueSource

LOGGER = getLogger("red.3pt.mp.commands.hybrids")


class HybridCommands(MPMixin, ABC):
    @commands.hybrid_command(name="play", description="Plays a specified query.", aliases=["p"])
    @app_commands.guilds(MY_GUILD)
    async def command_play(self, ctx: commands.Context, *, query: converters.QueryConverter):
        """Displays your currently played spotify song"""
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)

        if (player := self.lavalink.get_player(ctx.guild)) is None:
            player = await self.lavalink.connect_player(channel=ctx.author.voice.channel)
        is_partial = query.is_search
        tracks = {}
        if not is_partial:
            tracks: dict = await self.lavalink.get_tracks(query)
            if not tracks:
                await ctx.send(
                    embed=await self.lavalink.construct_embed(
                        messageable=ctx, description=f"No results found for {await query.query_to_string()}"
                    ),
                    ephemeral=True,
                )
                return
        if is_partial:
            track = Track(node=player.node, data=None, query=query, requester=ctx.author.id)
            await player.add(requester=ctx.author.id, track=track)
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx,
                    description=f"{await track.get_track_display_name(with_url=True)} enqueued",
                ),
                ephemeral=True,
            )
        elif query.is_single:
            track = Track(
                node=player.node, data=tracks["tracks"][0], query=query.with_index(0), requester=ctx.author.id
            )
            await player.add(requester=ctx.author.id, track=track)
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description=f"{await track.get_track_display_name(with_url=True)} enqueued"
                ),
                ephemeral=True,
            )
        else:
            tracks = tracks["tracks"]
            track_count = len(tracks)
            await player.bulk_add(
                requester=ctx.author.id,
                tracks_and_queries=[
                    Track(node=player.node, data=track["track"], query=query.with_index(i), requester=ctx.author.id)
                    async for i, track in AsyncIter(tracks).enumerate()
                ],
            )
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description=f"{track_count} tracks enqueued"
                ),
                ephemeral=True,
            )

        if not player.is_playing:
            await player.play()

    @commands.hybrid_command(name="np", description="Shows the track currently being played.", aliases=["now"])
    @app_commands.guilds(MY_GUILD)
    async def command_now(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if not player.current:
            await ctx.send(
                embed=await self.lavalink.construct_embed(messageable=ctx, description="Nothing is playing."),
                ephemeral=True,
            )
            return
        current_embed = await player.get_currently_playing_message(messageable=ctx)
        await ctx.send(embed=current_embed, ephemeral=True)

    @commands.hybrid_command(name="skip", description="Skips or votes to skip the current track.")
    @app_commands.guilds(MY_GUILD)
    async def command_skip(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if not player.current:
            await ctx.send(
                embed=await self.lavalink.construct_embed(messageable=ctx, description="Nothing is playing."),
                ephemeral=True,
            )
            return
        track_name = await player.current.get_track_display_name(with_url=True)
        await player.skip()
        await ctx.send(
            embed=await self.lavalink.construct_embed(description=f"Skipped - {track_name}", messageable=ctx),
            ephemeral=True,
        )

    @commands.hybrid_command(name="stop", description="Stops the player and remove all tracks from the queue.")
    @app_commands.guilds(MY_GUILD)
    @commands.is_owner()
    async def command_stop(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if not player.current:
            await ctx.send(
                embed=await self.lavalink.construct_embed(messageable=ctx, description="Nothing is playing."),
                ephemeral=True,
            )
            return
        await player.stop()
        await ctx.send(
            embed=await self.lavalink.construct_embed(messageable=ctx, description="Player stopped"), ephemeral=True
        )

    @commands.hybrid_command(
        name="dc", description="Disconnects the player from the voice channel.", aliases=["disconnect"]
    )
    @app_commands.guilds(MY_GUILD)
    @commands.is_owner()
    async def command_disconnect(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        LOGGER.info("Disconnecting from voice channel - {}", ctx.author)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        await player.disconnect()
        await ctx.send(
            embed=await self.lavalink.construct_embed(messageable=ctx, description="Disconnected from voice channel"),
            ephemeral=True,
        )

    @commands.hybrid_command(name="queue", description="Shows the current queue for the player.", aliases=["q"])
    @app_commands.guilds(MY_GUILD)
    async def command_queue(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if player.queue.empty():
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="There is nothing in the queue."
                ),
                ephemeral=True,
            )
            return
        await QueueMenu(cog=self, bot=self.bot, source=QueueSource(guild_id=ctx.guild.id, cog=self)).start(ctx=ctx)

    @commands.hybrid_command(name="shuffle", description="Shuffles the player's queue.")
    @app_commands.guilds(MY_GUILD)
    async def command_shuffle(self, ctx: commands.Context):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if player.queue.empty():
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="There is nothing in the queue."
                ),
                ephemeral=True,
            )
            return
        await player.shuffle_queue()
        await ctx.send(
            embed=await self.lavalink.construct_embed(
                messageable=ctx, description=f"{player.queue.qsize()} tracks shuffled"
            ),
            ephemeral=True,
        )

    @commands.hybrid_command(name="repeat", description="Set whether to repeat current song or queue.")
    @app_commands.guilds(MY_GUILD)
    async def command_repeat(self, ctx: commands.Context, queue: Optional[bool] = None):
        if isinstance(ctx, discord.Interaction):
            ctx = await self.bot.get_context(ctx)
        await ctx.defer(ephemeral=True)
        player = self.lavalink.get_player(ctx.guild)
        if not player:
            await ctx.send(
                embed=await self.lavalink.construct_embed(
                    messageable=ctx, description="Not connected to a voice channel."
                ),
                ephemeral=True,
            )
            return
        if queue:
            player.repeat_queue = True
            player.repeat_current = False
            msg = "Repeating the queue"
        else:
            if player.repeat_queue or player.repeat_current:
                player.repeat_queue = False
                player.repeat_current = False
                msg = "Repeating disabled"
            else:
                player.repeat_current = True
                player.repeat_queue = False
                msg = f"Repeating {await player.current.get_track_display_name(with_url=True)}"
        await ctx.send(embed=await self.lavalink.construct_embed(description=msg, messageable=ctx), ephemeral=True)
