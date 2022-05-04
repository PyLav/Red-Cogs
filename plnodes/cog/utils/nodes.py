from __future__ import annotations

import asyncio
from pathlib import Path

from redbot.core.i18n import Translator

from pylav.sql.models import NodeModel
from pylav.utils import PyLavContext

from plnodes.cog._types import CogT
from plnodes.cog.menus.menus import NodePickerMenu
from plnodes.cog.menus.selectors import NodeSelectSelector
from plnodes.cog.menus.sources import NodePickerSource

_ = Translator("PyLavNodes", Path(__file__))


async def maybe_prompt_for_node(cog: CogT, context: PyLavContext, nodes: list[NodeModel]) -> NodeModel:
    if len(nodes) > 1:
        node_picker = NodePickerMenu(
            cog=cog,
            bot=cog.bot,
            source=NodePickerSource(
                guild_id=context.guild.id,
                cog=cog,
                pages=nodes,
                message_str=_("Multiple nodes matched, pick the one which you meant."),
            ),
            selector_cls=NodeSelectSelector,
            delete_after_timeout=True,
            clear_buttons_after=True,
            starting_page=0,
            selector_text=_("Pick a node"),
            original_author=context.author if not context.interaction else context.interaction.user,
        )

        await node_picker.start(context)
        try:
            await node_picker.wait_for_response()
            node = node_picker.result
        except asyncio.TimeoutError:
            node = None
    else:
        node = nodes[0]
    return node
