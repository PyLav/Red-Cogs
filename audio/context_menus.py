from __future__ import annotations

import re
import shlex

import discord
from discord.ext.commands import HybridCommand
from redbot.core.i18n import Translator, cog_i18n

from pylav.constants.regex import SOURCE_INPUT_MATCH_MERGED
from pylav.extension.red.utils.decorators import is_dj_logic
from pylav.extension.red.utils.validators import valid_query_attachment
from pylav.players.query.obj import Query
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN, DISCORD_INTERACTION_TYPE

_ = Translator("PyLavPlayer", __file__)

YOUTUBE_MUSIC_ACTIVITY = re.compile(r"i\.ytimg\.com/vi/([A-Za-z0-9_\-]{11}).*\.jpg", re.IGNORECASE)


@cog_i18n(_)
class ContextMenus(DISCORD_COG_TYPE_MIXIN):
    command_play: HybridCommand

    async def _context_message_play(self, interaction: DISCORD_INTERACTION_TYPE, message: discord.Message) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("I can not play songs in direct messages. Sorry, try again on a server."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        is_dj = await is_dj_logic(interaction)
        if not is_dj:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("You need to be a disc jockey in this server to play tracks in this server."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return

        if player := self.pylav.get_player(interaction.guild.id):
            config = player.config
        else:
            config = self.pylav.player_config_manager.get_config(interaction.guild.id)

        if (channel_id := await config.fetch_text_channel_id()) != 0 and channel_id != interaction.channel.id:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    messageable=interaction,
                    description=_(
                        "This command is unavailable in this channel. Please use {channel_name_variable_do_not_translate} instead."
                    ).format(
                        channel_name_variable_do_not_translate=(
                            channel.mention
                            if (channel := interaction.guild.get_channel_or_thread(channel_id))
                            else channel_id
                        )
                    ),
                ),
                ephemeral=True,
                wait=True,
            )
            return
        content = await self._reconstruct_msg_content(message)

        try:
            content_parts = shlex.split(content)
        except ValueError:
            content_parts = content.split()
        valid_matches = set()

        for part in content_parts:
            part = part.strip()
            for __ in SOURCE_INPUT_MATCH_MERGED.finditer(part):
                valid_matches.add(part)
        for attachment in message.attachments:
            if valid_query_attachment(attachment.filename):
                valid_matches.add(attachment.url)

        if not valid_matches:
            message = _("I could not find any suitable matches in this message.")
        elif len(valid_matches) > 1:
            message = _("I found many suitable matches in this message.")
        else:
            message = _("I found a single suitable match in this message.")

        await interaction.followup.send(
            embed=await self.pylav.construct_embed(
                description=message,
                messageable=interaction,
            ),
            ephemeral=True,
            wait=True,
        )

        await self.command_play.callback(self, interaction, query="\n".join(valid_matches))  # type: ignore

    @staticmethod
    async def _reconstruct_msg_content(message):
        content = message.content.strip()
        for embed in message.embeds:
            if embed.description:
                content += f" {embed.description}"
            if embed.title:
                content += f" {embed.title}"
            if embed.url and valid_query_attachment(embed.url):
                content += f" {embed.url}"
            if embed.footer:
                if embed.footer.text:
                    content += f" {embed.footer.text}"
                if embed.footer.icon_url and valid_query_attachment(embed.footer.icon_url):
                    content += f" {embed.footer.icon_url}"
            if (
                hasattr(embed, "video")
                and embed.video
                and embed.video.url
                and ("www.youtube.com" not in embed.video.url or "/embed/" not in embed.video.url)
            ):
                content += f" {embed.video.url}"
            for field in embed.fields:
                if field.value:
                    content += f" {field.value}"
                if field.name:
                    content += f" {field.name}"
        return content

    async def _context_user_play(
        self, interaction: DISCORD_INTERACTION_TYPE, member: discord.Member
    ) -> None:  # sourcery skip: low-code-quality
        # sourcery no-metrics
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("I can not play songs in direct messages. Sorry, try again on a server."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        is_dj = await is_dj_logic(interaction)
        if not is_dj:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_("You need to be a disc jockey to play tracks in this server."),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        if player := self.pylav.get_player(interaction.guild.id):
            config = player.config
        else:
            config = self.pylav.player_config_manager.get_config(interaction.guild.id)
        if (channel_id := await config.fetch_text_channel_id()) != 0 and channel_id != interaction.channel.id:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    messageable=interaction,
                    description=_(
                        "This command is unavailable in this channel. Please use {channel_name_variable_do_not_translate} instead."
                    ).format(
                        channel_name_variable_do_not_translate=(
                            channel.mention
                            if (channel := interaction.guild.get_channel_or_thread(channel_id))
                            else channel_id
                        )
                    ),
                ),
                ephemeral=True,
                wait=True,
            )
            return
        # The member returned by this interaction doesn't have any activities.
        member = interaction.guild.get_member(member.id)
        spotify_activity = next((a for a in member.activities if isinstance(a, discord.Spotify)), None)
        apple_music_activity = next(
            (a for a in member.activities if a.name in ["Apple Music", "Cider", "Cider-2", "AppleMusic"]), None
        )
        youtube_music_activity = next((a for a in member.activities if a.name in ["YouTube Music"]), None)
        if not any([spotify_activity, apple_music_activity, youtube_music_activity]):
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "I could not find any supported activity in the activities {user_name_variable_do_not_translate} is partaking."
                    ).format(user_name_variable_do_not_translate=member.mention),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
            return
        if spotify_activity and spotify_activity.track_id:
            await self.command_play.callback(
                self,
                interaction,
                query=f"https://open.spotify.com/track/{spotify_activity.track_id}",
            )
        elif apple_music_activity:
            assert isinstance(apple_music_activity, discord.activity.Activity)
            album = apple_music_activity.assets.get("large_text")
            artist = apple_music_activity.state
            track = apple_music_activity.details
            # TODO: This should use the button URL instead of a search for 100% accuracy
            #   Currently discord.py doesnt provide the button URLs, the day they do this can be updated
            search_string = "amsearch:" if (album or artist or track) else ""
            if album:
                search_string += f"{album} "
            if artist:
                search_string += f"{artist} "
            if track:
                search_string += f"{track}"
            if not search_string:
                await interaction.followup.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I could not find a valid Apple Music track in the activity "
                            "{user_name_variable_do_not_translate} is partaking in."
                        ).format(user_name_variable_do_not_translate=member.mention),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
                return
            response = await self.pylav.get_tracks(
                await Query.from_string(search_string),
                player=interaction.client.pylav.get_player(interaction.guild.id),
            )
            match response.loadType:
                case "track":
                    tracks = [response.data]
                case "search":
                    tracks = response.data
                case "playlist":
                    tracks = response.data.tracks
                case __:
                    tracks = []
            if not tracks:
                await interaction.followup.send(
                    embed=await self.pylav.construct_embed(
                        description=_("I could not find any tracks matching {query_variable_do_not_translate}.").format(
                            query_variable_do_not_translate=search_string
                        ),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
                return
            await self.command_play.callback(
                self,
                interaction,
                query=tracks[0],
            )
        elif youtube_music_activity and youtube_music_activity.application_id == 1143202598460076053:
            assert isinstance(youtube_music_activity, discord.activity.Activity)
            if image_url := youtube_music_activity.assets.get("large_image"):
                track_id_match = YOUTUBE_MUSIC_ACTIVITY.search(image_url)
                if track_id_match and track_id_match.group(1):
                    await self.command_play.callback(
                        self,
                        interaction,
                        query=f"https://music.youtube.com/watch?v={track_id_match.group(1)}",
                    )
                    return
            track = apple_music_activity.details
            # TODO: This should use the button URL instead of a search for 100% accuracy
            #   Currently discord.py doesnt provide the button URLs, the day they do this can be updated
            search_string = "ytmsearch:" if (track) else ""
            if track:
                search_string += f"{track}"
            if not search_string:
                await interaction.followup.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I could not find a valid YouTube Music track in the activity "
                            "{user_name_variable_do_not_translate} is partaking in."
                        ).format(user_name_variable_do_not_translate=member.mention),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
                return
            response = await self.pylav.get_tracks(
                await Query.from_string(search_string),
                player=interaction.client.pylav.get_player(interaction.guild.id),
            )
            match response.loadType:
                case "track":
                    tracks = [response.data]
                case "search":
                    tracks = response.data
                case "playlist":
                    tracks = response.data.tracks
                case __:
                    tracks = []
            if not tracks:
                await interaction.followup.send(
                    embed=await self.pylav.construct_embed(
                        description=_("I could not find any tracks matching {query_variable_do_not_translate}.").format(
                            query_variable_do_not_translate=search_string
                        ),
                        messageable=interaction,
                    ),
                    ephemeral=True,
                    wait=True,
                )
                return
            await self.command_play.callback(
                self,
                interaction,
                query=tracks[0],
            )
        else:
            await interaction.followup.send(
                embed=await self.pylav.construct_embed(
                    description=_(
                        "I could not figure out what {user_name_variable_do_not_translate} is listening to."
                    ).format(user_name_variable_do_not_translate=member.mention),
                    messageable=interaction,
                ),
                ephemeral=True,
                wait=True,
            )
