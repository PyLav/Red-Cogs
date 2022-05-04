# isort: skip_file
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Union


T = TypeVar("T")

if TYPE_CHECKING:
    from redbot.core.commands import Cog, CogMixin
    from plnodes.cog import (
        NodeCommands,
    )

    Cog = Union[
        Cog,
        CogMixin,
        NodeCommands,
    ]


CogT = TypeVar("CogT", bound="Cog")
