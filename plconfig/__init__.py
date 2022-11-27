from __future__ import annotations

from redbot.core.utils import get_end_user_data_statement

from pylav.red_utils.utils.required_methods import pylav_auto_setup
from pylav.types import BotT

from plconfig.cog import PyLavConfigurator

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: BotT):
    await pylav_auto_setup(bot, PyLavConfigurator)
