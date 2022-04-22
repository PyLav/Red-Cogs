# isort: skip_file
from __future__ import annotations

from typing import Callable, TYPE_CHECKING, TypeVar

from typing_extensions import ParamSpec


T = TypeVar("T")

if TYPE_CHECKING:
    from audio.cog import HybridCommands, MediaPlayer  # noqa: F401
    from audio.cog.menus.sources import PlaylistListSource  # noqa: F401
    from redbot.core.utils import menus  # noqa: F401

    P = ParamSpec("P")
    MaybeAwaitableFunc = Callable[P, "MaybeAwaitable[T]"]


CogT = TypeVar("CogT", bound="MediaPlayer")
SourcesT = TypeVar("SourcesT", bound="Union[PlaylistListSource, menus.ListPageSource]")
