"""Input selection independent of ASS parsing and visual components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .karaoke import KaraokeItem


class SourceMatch(Protocol):
    """A callable predicate selecting a KaraokeItem.

    Ordinary typed functions can provide domain-specific selection.
    """

    def __call__(self, item: KaraokeItem, /) -> bool:
        """Whether this source item is selected by the predicate."""
        ...


@dataclass(frozen=True, kw_only=True)
class LineMatch:
    """Select lyric items by optional exact source style and body text.

    Both specified criteria must match.
    """

    style: str | None = None
    text: str | None = None

    def __call__(self, item: KaraokeItem) -> bool:
        """Whether the source item satisfies all supplied exact style/text criteria."""
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
