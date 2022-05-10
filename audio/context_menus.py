import shlex
from abc import ABC
from pathlib import Path

import discord
from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator

from pylav.query import MERGED_REGEX
from pylav.types import InteractionT, PyLavCogMixin

_ = Translator("PyLavPlayer", Path(__file__))


class ContextMenus(PyLavCogMixin, ABC):
    command_play: HybridCommand

    async def _context_message_play(self, interaction: InteractionT, message: discord.Message) -> None:
        await interaction.response.defer(ephemeral=True)

        if message.embeds and not message.content:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Currently I don't support parsing content from inside an embed message."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return

        if not interaction.guild:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I can't play songs in DMs."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        if player := self.lavalink.get_player(interaction.guild.id):
            config = player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(interaction.guild.id)
        if config.text_channel_id and config.text_channel_id != interaction.channel.id:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    messageable=interaction,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := interaction.guild.get_channel_or_thread(config.text_channel_id))
                        else None
                    ),
                ),
                ephemeral=True,
                wait=True,
            )
            return
        content = message.content.strip()
        try:
            content_parts = shlex.split(content)
        except ValueError:
            content_parts = content.split()
        valid_matches = set()

        for part in content_parts:
            part = part.strip()
            for __ in MERGED_REGEX.finditer(part):
                valid_matches.add(part)
        if not valid_matches:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I couldn't find any valid matches in your message."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return

        if len(valid_matches) > 1:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I found multiple valid matches in your message."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
        else:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I found a single valid match in your message."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )

        await self.command_play.callback(self, interaction, query="\n".join(valid_matches))  # type: ignore

    async def _context_user_play(self, interaction: InteractionT, member: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I can't play songs in DMs."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        if player := self.lavalink.get_player(interaction.guild.id):
            config = player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(interaction.guild.id)
        if config.text_channel_id and config.text_channel_id != interaction.channel.id:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    messageable=interaction,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := interaction.guild.get_channel_or_thread(config.text_channel_id))
                        else None
                    ),
                ),
                ephemeral=True,
                wait=True,
            )
            return
        # The member returned by this interaction doesn't have any activities
        member = interaction.guild.get_member(member.id)
        spotify_activity = next((a for a in member.activities if isinstance(a, discord.Spotify)), None)
        if not spotify_activity:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("{user} is not listening to anything on Spotify.").format(user=member.mention),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )

            return
        if spotify_activity.track_id:
            await self.command_play.callback(
                self,
                interaction,
                query=f"https://open.spotify.com/track/{spotify_activity.track_id}",
            )

        else:
            await interaction.followup.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Couldn't figure out what {user} is listening to.").format(user=member.mention),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
