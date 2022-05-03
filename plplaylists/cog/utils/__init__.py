from __future__ import annotations

import functools
from typing import Any

from plplaylists.cog.utils import decorators

__all__ = ("decorators", "rgetattr")


def rgetattr(obj: object, attr: str, *args: Any) -> Any:
    def _getattr(obj2, attr2):
        return getattr(obj2, attr2, *args)

    return functools.reduce(_getattr, [obj] + attr.split("."))
