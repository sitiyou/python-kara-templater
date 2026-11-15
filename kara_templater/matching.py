"""Input selection independent of ASS parsing and visual components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .recipe import KaraokeItem


class SourceMatch(Protocol):
    def __call__(self, item: KaraokeItem, /) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class LineMatch:
    style: str | None = None
    text: str | None = None

    def __call__(self, item: KaraokeItem) -> bool:
        return (self.style is None or item.style == self.style) and (
            self.text is None or "".join(u.text for u in item.source.units) == self.text
        )

    def __invert__(self) -> NotMatch:
        return NotMatch(self)


@dataclass(frozen=True)
class NotMatch:
    match: SourceMatch

    def __call__(self, item: KaraokeItem) -> bool:
        return not self.match(item)

    def __invert__(self) -> SourceMatch:
        return self.match
