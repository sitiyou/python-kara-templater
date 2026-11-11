"""Karaoke source items, execution contexts and backend configuration values."""

from dataclasses import dataclass, field

from .ass import Line, Style
from .ass_output import TextLayer
from .composition import Paint
from .model import KaraokeLine, LaidOutLine
from .sampling import DynamicEffect
from .timeline import (
    DisplayWindow,
    EdgeSweep,
    ProgressCurve,
)


@dataclass(frozen=True)
class KaraokeItem:
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
class EffectContext:
    layout: LaidOutLine
    style: Style
    ruby_style: Style
    resolution: tuple[int, int]
    max_regions: int = 10000


@dataclass(frozen=True)
class EffectPlan:
    layers: tuple[TextLayer, ...] = ()
    diagnostics: tuple[str, ...] = ()
    raw_lines: tuple[Line, ...] = ()
    dynamic: DynamicEffect | None = None


@dataclass(frozen=True)
class Sweep:
    progress_curve: ProgressCurve = field(default_factory=ProgressCurve)
    edges: EdgeSweep = field(default_factory=EdgeSweep)
    completion: str = "release"

    def __post_init__(self) -> None:
        if self.completion not in {"release", "clip"}:
            raise ValueError("sweep completion must be release or clip")


@dataclass(frozen=True)
class TrackStyle:
    track_id: str
    after: Paint | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.track_id or type(self.priority) is not int:
            raise ValueError("track appearance needs an id and integer priority")


@dataclass(frozen=True)
class RubyPolicy:
    enabled: bool = True
    offset_y: float = 0
    follow: str = "none"

    def __post_init__(self) -> None:
        from .timeline import _finite

        _finite(self.offset_y, "ruby offset")
        if self.follow not in {"none", "syllable"}:
            raise ValueError("ruby follow must be none or syllable")
