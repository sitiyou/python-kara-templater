"""Typed, bounded animation inputs for the coverage-material sampler."""

from collections.abc import Callable
from dataclasses import dataclass

from .composition import Glow
from .geometry import finite
from .scene_animation import VisualState
from .timeline import Region, union_regions


@dataclass(frozen=True)
class GlowFunction:
    """Pure world-state/local-seconds glow callback with declared spatial bounds.

    None hides only the glow. Width/radius are script pixels: scaling them with
    the source geometry is explicit in the callback. Breakpoints use the visual
    leaf's birth clock, just like its paint field and path animation.
    """

    function: Callable[[VisualState, float], Glow | None]
    max_blur: float
    max_border: float
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(self.max_blur, self.max_border, *self.breakpoints)
        if not callable(self.function):
            raise TypeError("glow function requires a callable")
        if not 0 <= self.max_blur <= 100 or self.max_border < 0:
            raise ValueError(
                "glow bounds require blur in 0..100 and nonnegative border"
            )
        if any(time < 0 for time in self.breakpoints):
            raise ValueError("glow breakpoints must be nonnegative local seconds")

    def sample(self, state: VisualState, time: float) -> Glow | None:
        """Evaluate a glow field while enforcing its declared blur and border bounds."""
        finite(time)
        value = self.function(state, time)
        if value is None:
            return None
        if not isinstance(value, Glow):
            raise TypeError("glow function must return Glow or None")
        if value.blur > self.max_blur or value.border > self.max_border:
            raise ValueError("glow function exceeded its declared blur/border bounds")
        return value


@dataclass(frozen=True)
class ScopeOpacity:
    """A leaf contribution's extra alpha at a named leaf or ancestor scope.

    The pure callback receives seconds since the owner's birth. Its factor is
    multiplied by that owner's normal state opacity, without changing geometry
    evaluation or material callbacks. Copying needs an explicit owner remap.
    """

    owner: str
    function: Callable[[float], float]
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.owner or not callable(self.function):
            raise ValueError("scope opacity requires an owner and callable")
        finite(*self.breakpoints)
        if any(time < 0 for time in self.breakpoints):
            raise ValueError("opacity breakpoints must be nonnegative local seconds")

    def sample(self, time: float) -> float:
        """Evaluate scope opacity at seconds time and validate the 0 through 1 result."""
        finite(time)
        value = self.function(time)
        if not isinstance(value, (int, float)):
            raise TypeError("scope opacity must return a number")
        finite(value)
        if not 0 <= value <= 1:
            raise ValueError("scope opacity must be in 0..1")
        return float(value)


@dataclass(frozen=True)
class CoveragePartition:
    """Fractional screen-x material ownership, applied before blur (not a clip)."""

    function: Callable[[VisualState, float], tuple["Region", ...]]
    max_regions: int
    inside: bool = True
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(*self.breakpoints)
        if (
            not callable(self.function)
            or type(self.max_regions) is not int
            or self.max_regions < 1
        ):
            raise ValueError(
                "coverage partition needs a callable and positive region bound"
            )
        if any(time < 0 for time in self.breakpoints):
            raise ValueError("partition breakpoints must be nonnegative local seconds")

    def sample(self, state: VisualState, time: float) -> tuple["Region", ...]:
        """Evaluate the declared region partition and enforce the configured maximum region count."""
        finite(time)
        regions = self.function(state, time)
        if len(regions) > self.max_regions:
            raise ValueError("coverage partition exceeded its declared region bound")
        return union_regions(regions)
