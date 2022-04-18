from typing import Optional

import discord
from discord import app_commands

from pylav import Query, Track
from pylav.utils import AsyncIter

from audio.cog import MPMixin
from audio.cog.menus.menus import QueueMenu
from audio.cog.menus.sources import QueueSource


class MPSlash(MPMixin):
    @app_commands.command(name="play", description="Plays a specified query.")
    async def slash_play(self, interaction: discord.Interaction, *, query: str):
        """Displays your currently played spotify song"""
        user = interaction.user
        guild = interaction.guild
        context = interaction.response
        if not context.is_done():
            await context.defer(ephemeral=True)
        query = await Query.from_string(query)

        if (player := self.lavalink.get_player(guild)) is None:
            player = await self.lavalink.connect_player(channel=user.voice.channel)
        is_partial = query.is_search
        if not is_partial:
            tracks: dict = await self.lavalink.get_tracks(query)
            if not tracks:
                await interaction.followup.send(f"No results found for {await query.query_to_string()}", ephemeral=True)
                return
        if is_partial:
            track = Track(node=player.node, data=None, query=query, extra={"requester": user.id})
            await player.add(requester=user.id, track=track, query=query)
            await interaction.followup.send(f"{await track.get_track_display_name()} enqueued", ephemeral=True)
        elif query.is_single:
            track = Track(node=player.node, data=tracks["tracks"].pop(0), query=query, extra={"requester": user.id})
            await player.add(requester=user.id, track=track["track"], query=query)
            await interaction.followup.send(f"{await track.get_track_display_name()} enqueued", ephemeral=True)
        else:
            tracks = tracks["tracks"]
            track_count = len(tracks)
            await player.bulk_add(
                requester=user.id, tracks_and_queries=[track["track"] async for track in AsyncIter(tracks)]
            )
            await interaction.followup.send(f"{track_count} tracks enqueued", ephemeral=True)

        if not player.is_playing:
            await player.play()

    @app_commands.command(name="np", description="Shows the track currently being played.")
    async def slash_now(self, interaction: discord.Interaction):
        guild = interaction.guild
        context = interaction.response
        if not context.is_done():
            await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await interaction.followup.send("Nothing is playing.", ephemeral=True)
            return
        current_embed = await player.get_currently_playing_message()
        await interaction.followup.send(embed=current_embed, ephemeral=True)

    @app_commands.command(name="skip", description="Skips or votes to skip the current track.")
    async def slash_skip(self, interaction: discord.Interaction):
        print("skip", interaction.user)

        guild = interaction.guild
        context = interaction.response
        if not context.is_done():
            await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await interaction.followup.send("Nothing is playing.", ephemeral=True)
            return
        track_name = await player.current.get_track_display_name(with_url=True)
        await player.skip()
        await interaction.followup.send(
            embed=await self.lavalink.construct_embed(description=f"Skipped - {track_name}"), ephemeral=True
        )

    @app_commands.command(name="stop", description="Stops the player and remove all tracks from the queue.")
    async def slash_stop(self, interaction: discord.Interaction):
        print("stop", interaction.user)

        guild = interaction.guild
        context = interaction.response
        await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        if not player.current:
            await interaction.followup.send("Nothing is playing.", ephemeral=True)
            return
        await player.stop()
        await interaction.followup.send("Player stopped", ephemeral=True)

    @app_commands.command(name="dc", description="Disconnects the player from the voice channel.")
    async def slash_disconnect(self, interaction: discord.Interaction):
        print("dc", interaction.user)

        guild = interaction.guild
        context = interaction.response
        await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        await player.disconnect()
        await interaction.followup.send("Disconnected from voice channel", ephemeral=True)

    @app_commands.command(name="queue", description="Shows the current queue for the player.")
    async def slash_queue(self, interaction: discord.Interaction):
        guild = interaction.guild
        context = interaction.response
        await context.defer(ephemeral=True, thinking=False)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        if player.queue.empty():
            await interaction.followup.send("There is nothing in the queue.", ephemeral=True)
            return
        await QueueMenu(cog=self, bot=self.bot, source=QueueSource(guild_id=guild.id, cog=self)).start(ctx=interaction)

    @app_commands.command(name="shuffle", description="Shuffles the player's queue.")
    async def slash_shuffle(self, interaction: discord.Interaction):
        print("shuffle", interaction.user)

        guild = interaction.guild
        context = interaction.response
        await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return
        if player.queue.empty():
            await interaction.followup.send("There is nothing in the queue.", ephemeral=True)
            return
        await player.shuffle_queue()
        await interaction.followup.send(f"{player.queue.qsize()} tracks shuffled", ephemeral=True)

    @app_commands.command(name="repeat", description="Set whether to repeat current song or queue.")
    async def slash_repeat(self, interaction: discord.Interaction, queue: Optional[bool] = None):
        print("repeat", interaction.user)
        guild = interaction.guild
        context = interaction.response
        await context.defer(ephemeral=True)
        player = self.lavalink.get_player(guild)
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
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
        await interaction.followup.send(embed=await self.lavalink.construct_embed(description=msg), ephemeral=True)
