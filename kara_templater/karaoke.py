"""Structured lyric input shared by parsing and Track frontends."""

from dataclasses import dataclass

from .model import KaraokeLine
from .timeline import DisplayWindow


@dataclass(frozen=True)
class KaraokeItem:
    """Structured lyrics with a stable identity and a millisecond display window.

    ``style`` names a Document style. ``ruby_style`` selects an explicit reading
    style; otherwise the frontend uses or creates ``style + '-ruby'``. Positive
    ``margins`` override left, right, and vertical source margins respectively.
    """

    id: str
    source: KaraokeLine
    style: str
    window: DisplayWindow
    ruby_style: str | None = None
    margins: tuple[int, int, int] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("karaoke item needs a stable id")
        if self.margins is not None and (
            len(self.margins) != 3 or any(type(v) is not int for v in self.margins)
        ):
            raise ValueError("item margins must be three integers")
