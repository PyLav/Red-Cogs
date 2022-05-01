import shlex
from abc import ABC
from pathlib import Path

import discord
from redbot.core.i18n import Translator

from pylav.query import MERGED_REGEX

from audio.cog import MPMixin

_ = Translator("MediaPlayer", Path(__file__))


class ContextMenus(MPMixin, ABC):
    async def _context_message_play(self, interaction: discord.Interaction, message: discord.Message) -> None:
        context = await self.bot.get_context(interaction)
        await context.defer(ephemeral=True)
        if message.embeds and not message.content:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Currently I don't support parsing content from inside an embed message."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if not context.interaction.guild:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I can't play songs in DMs."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        if config.text_channel_id and config.text_channel_id != context.channel.id:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := context.guild.get_channel_or_thread(config.text_channel_id))
                        else None
                    ),
                ),
                ephemeral=True,
            )
            return
        content = message.content.strip()
        content_parts = shlex.split(content)
        valid_matches = set()

        for part in content_parts:
            part = part.strip()
            for __ in MERGED_REGEX.finditer(part):
                valid_matches.add(part)
        if not valid_matches:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I couldn't find any valid matches in your message."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if len(valid_matches) > 1:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I found multiple valid matches in your message."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I found a single valid match in your message."),
                    messageable=context,
                ),
                ephemeral=True,
            )

        await self.command_play.callback(self, context, query="\n".join(valid_matches))  # type: ignore

    async def _context_user_play(self, interaction: discord.Interaction, member: discord.Member) -> None:
        context = await self.bot.get_context(interaction)
        await context.defer(ephemeral=True)
        if not context.interaction.guild:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("I can't play songs in DMs."),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if context.player:
            config = context.player.config
        else:
            config = await self.lavalink.player_config_manager.get_config(context.guild.id)
        if config.text_channel_id and config.text_channel_id != context.channel.id:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_("This command is not available in this channel. Please use {channel}").format(
                        channel=channel.mention
                        if (channel := context.guild.get_channel_or_thread(config.text_channel_id))
                        else None
                    ),
                ),
                ephemeral=True,
            )
            return
        # The member returned by this interaction doesn't have any activities
        member = context.guild.get_member(member.id)
        spotify_activity = next((a for a in member.activities if isinstance(a, discord.Spotify)), None)
        if not spotify_activity:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("{user} is not listening to anything on Spotify.").format(user=member.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )

            return
        if spotify_activity.track_id:
            await self.command_play.callback(  # type: ignore
                self, context, query="https://open.spotify.com/track/" + spotify_activity.track_id
            )
        else:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("Couldn't figure out what {user} is listening to.").format(user=member.mention),
                    messageable=context,
                ),
                ephemeral=True,
            )
