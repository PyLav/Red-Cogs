# isort: skip_file
from __future__ import annotations

from typing import Callable, TYPE_CHECKING, TypeVar, Union

from typing_extensions import ParamSpec


T = TypeVar("T")

if TYPE_CHECKING:
    from redbot.core.commands import Cog, CogMixin
    from plplaylists.cog import (
        PlaylistCommands,
    )  # noqa: F401
    from plplaylists.cog.menus.sources import PlaylistListSource  # noqa: F401
    from redbot.core.utils import menus  # noqa: F401

    Cog = Union[Cog, CogMixin, PlaylistCommands]

    P = ParamSpec("P")
    MaybeAwaitableFunc = Callable[P, "MaybeAwaitable[T]"]

CogT = TypeVar("CogT", bound="Cog")
SourcesT = TypeVar("SourcesT", bound="Union[PlaylistListSource, menus.ListPageSource]")
