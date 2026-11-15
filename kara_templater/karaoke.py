"""Typed lyric input and highlight declarations shared by Track frontends."""

from dataclasses import dataclass
from typing import Literal

from .composition import Paint
from .model import KaraokeLine
from .timeline import DisplayWindow, EdgeSweep, ProgressCurve


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


@dataclass(frozen=True)
class Sweep:
    """Highlight progress and completion behavior.

    A progress curve maps singing time to a horizontal cursor. ``release``
    removes a completed sweep's clip after the singing interval, exposing the
    full sung decoration. ``clip`` retains clipping through the display window. Edge
    compensation is for low-level spans; Track overlays use uncompensated edges.
    """

    progress_curve: ProgressCurve = ProgressCurve()
    edges: EdgeSweep = EdgeSweep()
    completion: Literal["release", "clip"] = "release"

    def __post_init__(self) -> None:
        if not isinstance(self.progress_curve, ProgressCurve):
            raise TypeError("sweep progress_curve requires ProgressCurve")
        if not isinstance(self.edges, EdgeSweep):
            raise TypeError("sweep edges require EdgeSweep")
        if self.completion not in {"release", "clip"}:
            raise ValueError("sweep completion must be release or clip")


@dataclass(frozen=True)
class HighlightStyle:
    """Paint and priority for one explicitly named HighlightTrack.

    ``after=None`` uses the lyric's sung paint. Larger priority wins when an
    Overlay uses priority composition; layer composition retains stack order.
    """

    track_id: str
    after: Paint | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.track_id or type(self.priority) is not int:
            raise ValueError("highlight style needs an id and integer priority")
