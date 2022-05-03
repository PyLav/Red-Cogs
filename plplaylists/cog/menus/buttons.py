from __future__ import annotations

import itertools
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import discord
from discord import Emoji, PartialEmoji
from red_commons.logging import getLogger
from redbot.core.i18n import Translator

from pylav import emojis
from pylav.sql.models import PlaylistModel

from plplaylists.cog._types import CogT
from plplaylists.cog.menus.modals import PlaylistSaveModal
from plplaylists.cog.menus.selectors import PlaylistPlaySelector
from plplaylists.cog.menus.sources import Base64Source
from plplaylists.cog.utils import rgetattr

if TYPE_CHECKING:
    from plplaylists.cog.menus.menus import PlaylistCreationFlow, PlaylistManageFlow

LOGGER = getLogger("red.3pt.PyLavPlaylists.ui.buttons")

_ = Translator("PyLavPlaylists", Path(__file__))


class NavigateButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | discord.PartialEmoji,
        direction: int | Callable[[], int],
        row: int = None,
        label: str = None,
    ):

        super().__init__(style=style, emoji=emoji, row=row, label=label)
        self.cog = cog
        self._direction = direction

    @property
    def direction(self) -> int:
        return self._direction if isinstance(self._direction, int) else self._direction()

    async def callback(self, interaction: discord.Interaction):
        max_pages = self.view.source.get_max_pages()
        if self.direction == 0:
            self.view.current_page = 0
        elif self.direction == max_pages:
            self.view.current_page = max_pages - 1
        else:
            self.view.current_page += self.direction

        if self.view.current_page >= max_pages:
            self.view.current_page = 0
        elif self.view.current_page < 0:
            self.view.current_page = max_pages - 1

        kwargs = await self.view.get_page(self.view.current_page)
        await self.view.prepare()
        await interaction.response.edit_message(view=self.view, **kwargs)


class RefreshButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await self.view.prepare()
        kwargs = await self.view.get_page(self.view.current_page)
        await interaction.response.edit_message(view=self.view, **kwargs)


class CloseButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.MINIMIZE,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = True
        self.view.stop()
        await self.view.on_timeout()


class SaveQueuePlaylistButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.QUEUE,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        modal = PlaylistSaveModal(self.cog, self, _("What should the playlist name be?"))
        await interaction.response.send_modal(modal)


class EnqueuePlaylistButton(discord.ui.Button):
    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        row: int = None,
        emoji: Emoji | PartialEmoji = emojis.PLAYLIST,
        playlist: PlaylistModel = None,
    ):
        self.cog = cog
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.playlist = playlist

    async def callback(self, interaction: discord.Interaction):
        from plplaylists.cog.menus.menus import PlaylistPickerMenu
        from plplaylists.cog.menus.sources import PlaylistPickerSource

        if not self.playlist:
            playlists = await self.cog.lavalink.playlist_db_manager.get_all_for_user(
                requester=interaction.user.id,
                vc=rgetattr(interaction.user, "voice.channel", None),
                guild=interaction.guild,
                channel=interaction.channel,  # type: ignore
            )
            playlists = list(itertools.chain.from_iterable(playlists))
            await PlaylistPickerMenu(
                cog=self.cog,
                bot=self.cog.bot,
                selector_cls=PlaylistPlaySelector,
                source=PlaylistPickerSource(
                    guild_id=interaction.guild.id,
                    cog=self.cog,
                    pages=playlists,
                    message_str=_("Playlists you can currently play"),
                ),
                delete_after_timeout=True,
                clear_buttons_after=True,
                starting_page=0,
                original_author=interaction.user,
                selector_text=_("Pick a playlist"),
            ).start(interaction)
        else:
            await self.cog.command_playlist_play.callback(self.cog, interaction, playlist=[self.playlist])
        if hasattr(self.view, "prepare"):
            await self.view.prepare()
            kwargs = await self.view.get_page(self.view.current_page)
            await (await interaction.original_message()).edit(view=self.view, **kwargs)


class PlaylistUpsertButton(discord.ui.Button):
    view: PlaylistCreationFlow | PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        op: Literal["url", "name", "scope", "add", "remove"],
        label: str = None,
        emoji: str | Emoji | PartialEmoji = None,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            label=label,
            row=row,
        )
        self.cog = cog
        self.op = op

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        if self.op == "url":
            await self.view.prompt_url(interaction)
        elif self.op == "name":
            await self.view.prompt_name(interaction)
        elif self.op == "scope":
            await self.view.prompt_scope(interaction)
        elif self.op == "add":
            await self.view.prompt_add_tracks(interaction)
        elif self.op == "remove":
            await self.view.prompt_remove_tracks(interaction)


class DoneButton(discord.ui.Button):
    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.CHECK,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.done = True
        self.view.cancelled = False
        self.view.stop()
        await self.view.on_timeout()


class PlaylistDeleteButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.TRASH,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        self.view.delete = not self.view.delete
        if self.view.delete:
            response = _("When you press done this playlist will be permanently delete...")
        else:
            response = _("This playlist will no longer be deleted once you press done...")

        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistClearButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.CLEAR,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        self.view.clear = not self.view.clear
        if self.view.clear:
            response = _("Clearing all tracks from the playlist playlist...")
        else:
            response = _("No longer clearing tracks from the playlist...")

        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistDownloadButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )

        async with self.view.playlist.to_yaml(guild=interaction.guild) as yaml_file:
            yaml_file: BytesIO
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction,
                    description=_("Here is your playlist: {name}{extras}").format(
                        name=await self.view.playlist.get_name_formatted(with_url=True),
                        extras=_(
                            "\n (compressed using gzip to make it possible to send via Discord "
                            "- you can use <https://gzip.swimburger.net/> to decompress it)"
                        ),
                    ),
                ),
                file=discord.File(filename=f"{self.view.playlist.name}.yaml", fp=yaml_file),
                ephemeral=True,
            )


class PlaylistUpdateButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(self, cog: CogT, style: discord.ButtonStyle, row: int = None):
        super().__init__(
            style=style,
            emoji=emojis.UPDATE,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.cancelled = False
        self.view.update = not self.view.update
        if (self.view.playlist.url or self.view.url) and self.view.update:
            response = _("Updating playlist with the latest tracks...")
        else:
            self.view.update = False
            response = _("Not updating playlist...")
        await interaction.response.send_message(
            embed=await self.cog.lavalink.construct_embed(messageable=interaction, description=response),
            ephemeral=True,
        )


class PlaylistInfoButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        playlist: PlaylistModel,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog
        self.playlist = playlist

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        from plplaylists.cog.menus.menus import PaginatingMenu

        await PaginatingMenu(
            bot=self.cog.bot,
            cog=self.cog,
            source=Base64Source(
                guild_id=interaction.guild.id,
                cog=self.cog,
                author=interaction.user,
                entries=self.view.playlist.tracks,
                playlist=self.playlist,
            ),
            delete_after_timeout=True,
            starting_page=0,
            original_author=interaction.user,
        ).start(await self.cog.bot.get_context(interaction))


class PlaylistQueueButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.queue = not self.view.queue
        if self.view.queue:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Adding the current queue to playlist...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No longer adding the current queue to playlist...")
                ),
                ephemeral=True,
            )


class PlaylistDedupeButton(discord.ui.Button):
    view: PlaylistManageFlow

    def __init__(
        self,
        cog: CogT,
        style: discord.ButtonStyle,
        emoji: str | Emoji | PartialEmoji,
        row: int = None,
    ):
        super().__init__(
            style=style,
            emoji=emoji,
            row=row,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if self.view.author.id != interaction.user.id:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("You are not authorized to interact with this option.")
                ),
                ephemeral=True,
            )
        self.view.dedupe = not self.view.dedupe
        if self.view.dedupe:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("Removing all duplicate tracks from the queue...")
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=await self.cog.lavalink.construct_embed(
                    messageable=interaction, description=_("No longer all duplicate tracks from the queue...")
                ),
                ephemeral=True,
            )
