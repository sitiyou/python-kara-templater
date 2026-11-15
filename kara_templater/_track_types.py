"""Internal layout context and lowering plans for Track compilation."""

from dataclasses import dataclass

from .ass import Style
from .ass_output import TextLayer
from .model import LaidOutLine
from .raster_settings import RasterPlan, RasterSettings
from .sampling import DynamicEffect
from .timeline import _finite


@dataclass(frozen=True)
class TrackContext:
    layout: LaidOutLine
    style: Style
    ruby_style: Style
    resolution: tuple[int, int]
    max_regions: int = 10000
    raster: RasterSettings | None = None


@dataclass(frozen=True)
class TrackPlan:
    layers: tuple[TextLayer, ...] = ()
    diagnostics: tuple[str, ...] = ()
    dynamic: DynamicEffect | None = None
    raster: RasterPlan | None = None


@dataclass(frozen=True)
class RubyPolicy:
    enabled: bool = True
    offset_y: float = 0
    follow: str = "none"

    def __post_init__(self) -> None:
        _finite(self.offset_y, "ruby offset")
        if self.follow not in {"none", "syllable"}:
            raise ValueError("ruby follow must be none or syllable")
