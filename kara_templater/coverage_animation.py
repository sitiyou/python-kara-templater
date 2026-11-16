"""Typed, bounded animation inputs for the coverage-material sampler."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace

from .composition import Glow
from .geometry import finite
from .paint_fields import PaintField
from .raster_settings import RasterSettings
from .scene_animation import (
    AnimationClip,
    AnimationSequence,
    StateAnimation,
    TimeSpan,
    Tween,
    VisualState,
    evaluate_clips,
    linear_rate,
)
from .timeline import Region, union_regions

_DEFAULT_GLOW = Glow()


@dataclass(frozen=True, kw_only=True)
class Coverage:
    """Explicit pre-blur material composition for a visual group.

    Attach to ObjectGroup.coverage (including LyricLine) and compile the normal
    Scene. Ordinary drawing groups retain per-layer alpha; this strategy closes
    component/group alpha scopes after composing coverage. Sampling and spatial
    approximation are explicit and bounded, never selected automatically.
    Ordinary ancestors retain their transforms, masks, opacity and clocks; their
    other children remain separate drawing contributions. Geometry references use
    the shared Scene context. Nested Coverage declarations and opacity references
    require explicit ownership and are rejected.
    """

    components: tuple[str, ...] = ()
    glows: Mapping[str, Glow | GlowFunction] = field(default_factory=dict)
    glow_materials: Mapping[str, PaintField] = field(default_factory=dict)
    partitions: Mapping[str, CoveragePartition] = field(default_factory=dict)
    scope_opacities: Mapping[str, tuple[ScopeOpacity, ...]] = field(
        default_factory=dict
    )
    settings: RasterSettings = RasterSettings()

    def retarget(self, names: Mapping[str, str]) -> Coverage:
        """Retarget all material ownership when copying a visual tree."""

        def name(value: str) -> str:
            return names.get(value, value)

        return replace(
            self,
            components=tuple(name(value) for value in self.components),
            glows={name(key): value for key, value in self.glows.items()},
            glow_materials={
                name(key): value for key, value in self.glow_materials.items()
            },
            partitions={name(key): value for key, value in self.partitions.items()},
            scope_opacities={
                name(key): tuple(
                    replace(rule, owner=name(rule.owner)) for rule in rules
                )
                for key, rules in self.scope_opacities.items()
            },
        )


@dataclass(frozen=True)
class GlowFunction:
    """Pure world-state/local-seconds glow callback with declared spatial bounds.

    None hides only the glow. Width/radius are script pixels: scaling them with
    the source geometry is explicit in the callback. Breakpoints use the visual
    leaf's local clock, just like its paint field and path animation. Signed
    local intervals are validated against Scene zero and the leaf's display end.
    required_interval optionally declares authored local time that lyric layout
    must preserve; it is not inferred from sampling breakpoints. from_animation
    supplies the animation interval automatically.
    """

    function: Callable[[VisualState, float], Glow | None]
    max_blur: float
    max_border: float
    breakpoints: tuple[float, ...] = ()
    required_interval: TimeSpan | None = None

    @classmethod
    def from_animation(
        cls,
        animation: StateAnimation,
        *,
        base: Glow = _DEFAULT_GLOW,
        duration: float | None = None,
        start: float = 0,
        hold: bool = True,
        max_blur: float | None = None,
        max_border: float | None = None,
    ) -> GlowFunction:
        """Use a common paint animation as a local-seconds glow field.

        fill maps to glow color; blur, border and opacity map directly. Other
        channels are rejected. Sequences default to their authored duration;
        other animations need duration. Before start and after a released clip,
        base is returned. This field does not extend the owning leaf's lifetime.

        Linear Tween targets and nested sequences infer conservative spatial
        maxima without sampling callbacks. Custom spatial animations/rates need
        explicit bounds, checked at every sample. Values are script pixels and
        do not implicitly scale with the drawing's world transform.
        """
        if not animation.channels <= {"fill", "blur", "border", "opacity"}:
            raise ValueError(
                "glow animations support fill, blur, border and opacity only"
            )
        if duration is None:
            if not isinstance(animation, AnimationSequence):
                raise ValueError("glow animation requires duration or a sequence")
            duration = animation.duration
        finite(start, duration)
        if start < 0 or duration <= 0:
            raise ValueError(
                "glow animation needs nonnegative start and positive duration"
            )

        def bound(
            current: StateAnimation, channel: str, initial: float
        ) -> float | None:
            if channel not in current.channels:
                return initial
            if type(current) is Tween and current.rate is linear_rate:
                value = (
                    current.target.blur if channel == "blur" else current.target.border
                )
                assert value is not None
                finite(value)
                if value < 0:
                    raise ValueError("glow spatial targets must be nonnegative")
                return max(initial, value)
            if type(current) is AnimationSequence:
                values = [
                    bound(clip.animation, channel, initial) for clip in current.clips
                ]
                return (
                    None
                    if any(value is None for value in values)
                    else max(initial, *(value for value in values if value is not None))
                )
            return None

        limits: list[float] = []
        for channel, initial, supplied in (
            ("blur", base.blur, max_blur),
            ("border", base.border, max_border),
        ):
            inferred = bound(animation, channel, initial)
            if supplied is None:
                if inferred is None:
                    raise ValueError(
                        f"custom glow {channel} animation requires max_{channel}"
                    )
                supplied = inferred
            finite(supplied)
            if supplied < (initial if inferred is None else inferred):
                raise ValueError(f"max_{channel} omits base or known animation targets")
            limits.append(supplied)
        initial_state = VisualState(
            fill=base.color, blur=base.blur, border=base.border, opacity=base.opacity
        )
        clip = AnimationClip(start, duration, animation, hold)

        def sample(state: VisualState, time: float) -> Glow:
            value = evaluate_clips(initial_state, (clip,), time)
            return Glow(
                value.fill, blur=value.blur, border=value.border, opacity=value.opacity
            )

        points = {start, start + duration}
        points.update(start + point for point in clip.breakpoints)
        return cls(
            sample,
            max_blur=limits[0],
            max_border=limits[1],
            breakpoints=tuple(sorted(points)),
            required_interval=TimeSpan(start, start + duration),
        )

    def __post_init__(self) -> None:
        finite(self.max_blur, self.max_border, *self.breakpoints)
        if self.required_interval is not None and (
            self.required_interval.duration <= 0
        ):
            raise ValueError("required glow interval must have positive duration")
        if not callable(self.function):
            raise TypeError("glow function requires a callable")
        if not 0 <= self.max_blur <= 100 or self.max_border < 0:
            raise ValueError(
                "glow bounds require blur in 0..100 and nonnegative border"
            )

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

    The pure callback receives signed seconds from the owner's clock origin.
    Breakpoints must lie between Scene zero and the owner's display end. Its factor is
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
    """Fractional screen-x material ownership, applied before blur (not a clip).

    Breakpoints are signed local seconds; compilation validates their absolute
    times against the owning object's clock and display end.
    """

    function: Callable[[VisualState, float], tuple[Region, ...]]
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

    def sample(self, state: VisualState, time: float) -> tuple[Region, ...]:
        """Evaluate the declared region partition and enforce the configured maximum region count."""
        finite(time)
        regions = self.function(state, time)
        if len(regions) > self.max_regions:
            raise ValueError("coverage partition exceeded its declared region bound")
        return union_regions(regions)
