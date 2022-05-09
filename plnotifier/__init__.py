from __future__ import annotations

from redbot.core.utils import get_end_user_data_statement

from pylav.types import BotT
from pylavcogs_shared.utils.required_methods import complex_setup

from plnotifier.cog import PyLavNotifier

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    await complex_setup(bot, PyLavNotifier)
