# isort: skip_file
from __future__ import annotations

from typing import Callable, TYPE_CHECKING, TypeVar
from typing_extensions import ParamSpec

T = TypeVar("T")

if TYPE_CHECKING:
    from audio.cog import HybridCommands, MediaPlayer, PlayerCommands, PlaylistCommands, UtilityCommands  # noqa: F401

    P = ParamSpec("P")
    MaybeAwaitableFunc = Callable[P, "MaybeAwaitable[T]"]
else:
    from redbot.core.commands import Cog as MediaPlayer  # noqa: F401

    P = TypeVar("P")
    MaybeAwaitableFunc = tuple[P, T]


CogT = TypeVar("CogT", bound="Union[MediaPlayer, HybridCommands, PlayerCommands, PlaylistCommands, UtilityCommands]")
