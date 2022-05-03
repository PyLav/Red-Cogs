from __future__ import annotations

import asyncio
from pathlib import Path

from redbot.core.i18n import Translator

from pylav.sql.models import PlaylistModel
from pylav.types import CogT
from pylav.utils import PyLavContext

from plplaylists.cog.menus.menus import PlaylistPickerMenu
from plplaylists.cog.menus.selectors import PlaylistSelectSelector
from plplaylists.cog.menus.sources import PlaylistPickerSource

_ = Translator("PyLavPlaylists", Path(__file__))


async def maybe_prompt_for_playlist(cog: CogT, context: PyLavContext, playlists: list[PlaylistModel]) -> PlaylistModel:
    if len(playlists) > 1:
        playlist_picker = PlaylistPickerMenu(
            cog=cog,
            bot=cog.bot,
            source=PlaylistPickerSource(
                guild_id=context.guild.id,
                cog=cog,
                pages=playlists,
                message_str=_("Multiple playlist matched, pick the one which you meant."),
            ),
            selector_cls=PlaylistSelectSelector,
            delete_after_timeout=True,
            clear_buttons_after=True,
            starting_page=0,
            selector_text=_("Pick a playlist"),
            original_author=context.author if not context.interaction else context.interaction.user,
        )

        await playlist_picker.start(context)
        try:
            await playlist_picker.wait_for_response()
            playlist = playlist_picker.result
        except asyncio.TimeoutError:
            playlist = None
    else:
        playlist = playlists[0]

    return playlist
