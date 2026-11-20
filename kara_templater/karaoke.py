"""Structured lyric items returned by the ASS importer."""

from dataclasses import dataclass

from .model import KaraokeLine
from .timeline import DisplayWindow


@dataclass(frozen=True)
class KaraokeItem:
    """Structured lyrics with a stable identity and a millisecond display window.

    style names the source Document style. margins preserves the event
    overrides in left, right and vertical order.
    """

    id: str
    source: KaraokeLine
    style: str
    window: DisplayWindow
    margins: tuple[int, int, int] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("karaoke item needs a stable id")
        if self.margins is not None and (
            len(self.margins) != 3 or any(type(v) is not int for v in self.margins)
        ):
            raise ValueError("item margins must be three integers")
