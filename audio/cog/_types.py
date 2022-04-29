# isort: skip_file
from __future__ import annotations

from typing import Callable, TYPE_CHECKING, TypeVar, Union

from typing_extensions import ParamSpec


T = TypeVar("T")

if TYPE_CHECKING:
    from redbot.core.commands import Cog, CogMixin
    from audio.cog import (
        HybridCommands,
        MediaPlayer,
        PlaylistCommands,
        UtilityCommands,
        PlayerCommands,
        ConfigCommands,
        NodeCommands,
    )  # noqa: F401
    from audio.cog.menus.sources import PlaylistListSource  # noqa: F401
    from redbot.core.utils import menus  # noqa: F401

    Cog = Union[
        MediaPlayer,
        HybridCommands,
        PlaylistCommands,
        UtilityCommands,
        PlayerCommands,
        Cog,
        CogMixin,
        ConfigCommands,
        NodeCommands,
    ]

    P = ParamSpec("P")
    MaybeAwaitableFunc = Callable[P, "MaybeAwaitable[T]"]

CogT = TypeVar("CogT", bound="Cog")
SourcesT = TypeVar("SourcesT", bound="Union[PlaylistListSource, menus.ListPageSource]")
