"""Typed visual properties and stateless animation scheduling (seconds)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from math import cos, pi, radians, sin
from typing import Literal, Protocol, runtime_checkable

from .composition import Color
from .geometry import Affine2D, Vec2, finite

type Channel = Literal[
    "position",
    "scale",
    "rotation",
    "skew",
    "opacity",
    "fill",
    "outline",
    "border",
    "blur",
    "shadow",
]
CHANNELS: frozenset[Channel] = frozenset(
    (
        "position",
        "scale",
        "rotation",
        "skew",
        "opacity",
        "fill",
        "outline",
        "border",
        "blur",
        "shadow",
    )
)


def local_seconds(time: float, origin: float) -> float:
    """Canonical local clock (1e-10 s), stable across ordinary song-time offsets.

    This removes cancellation noise far below ASS's 10 ms event grid. It is a
    numerical time resolution, not a promise about arbitrary callback smoothness.
    """
    return round(time - origin, 10)


def linear_rate(progress: float) -> float:
    """Return normalized Scene animation progress unchanged."""
    return progress


def smooth_rate(progress: float) -> float:
    """Ease Scene animation progress smoothly between endpoints."""
    return progress * progress * (3 - 2 * progress)


def smoother_rate(progress: float) -> float:
    """Quintic easing with zero velocity and acceleration at both endpoints.

    Input is normalized progress in [0, 1]; outside that interval the polynomial
    extrapolates. Use as a rate for shared animations or inside custom curves.
    """
    return progress ** 3 * (progress * (progress * 6 - 15) + 10)


@dataclass(frozen=True)
class TimeSpan:
    """A finite seconds interval, including zero-length singing spans.

    The binding context determines whether its endpoints are absolute or local.
    """

    start: float
    end: float

    def __post_init__(self) -> None:
        finite(self.start, self.end)
        if self.end < self.start:
            raise ValueError("interval end must not precede start")

    @property
    def duration(self) -> float:
        """The seconds difference between end and start."""
        return self.end - self.start

    @property
    def interval(self) -> TimeSpan:
        """This seconds interval, suitable for Timeline.play(during=...)."""
        return self


@dataclass(frozen=True)
class VisualState:
    """Finite drawing state in script pixels, degrees, RGB colors, and opacity 0 through 1.

    Position, scale, rotation, skew, paint, blur, and shadow compose through the
    scene hierarchy.
    shadow_opacity multiplies the drawing opacity for the shadow alone.
    """

    position: Vec2 = Vec2()
    scale: Vec2 = Vec2(1, 1)
    rotation: float = 0
    skew: Vec2 = Vec2()
    opacity: float = 1
    fill: Color = Color(255, 255, 255)
    outline: Color = Color(0, 0, 0)
    border: float = 0
    blur: float = 0
    shadow: Vec2 = Vec2()
    shadow_opacity: float = 1

    def __post_init__(self) -> None:
        if not isinstance(self.fill, Color) or not isinstance(self.outline, Color):
            raise TypeError("visual fill and outline must be Color values")
        if not (isinstance(self.position, Vec2) and isinstance(self.scale, Vec2)
                and isinstance(self.skew, Vec2) and isinstance(self.shadow, Vec2)):
            raise TypeError(
                "visual position, scale, skew and shadow must be Vec2 values"
            )
        finite(self.rotation, self.opacity, self.border, self.blur, self.shadow_opacity)
        if not 0 <= self.opacity <= 1 or self.border < 0 or self.blur < 0:
            raise ValueError("opacity must be in 0..1, border/blur must be nonnegative")
        if not 0 <= self.shadow_opacity <= 1:
            raise ValueError("shadow opacity must be in 0..1")

    @property
    def singular(self) -> bool:
        """Whether this linear map collapses filled geometry to zero area."""
        return self.scale.x == 0 or self.scale.y == 0 or self.skew.x * self.skew.y == 1

    @cached_property
    def transform(self) -> Affine2D:
        """Local shear, axis scale, clockwise rotation, then translation."""
        theta = radians(self.rotation)
        c, s = cos(theta), sin(theta)
        sx, sy = self.scale.x, self.scale.y
        return Affine2D(c*sx - s*self.skew.y*sy, s*sx + c*self.skew.y*sy,
                        c*self.skew.x*sx - s*sy, s*self.skew.x*sx + c*sy,
                        self.position.x, self.position.y)


@dataclass(frozen=True, kw_only=True)
class StatePatch:
    """A sparse set of VisualState targets for interpolation.

    Omitted channels retain the incoming state.
    """

    position: Vec2 | None = None
    scale: Vec2 | None = None
    rotation: float | None = None
    skew: Vec2 | None = None
    opacity: float | None = None
    fill: Color | None = None
    outline: Color | None = None
    border: float | None = None
    blur: float | None = None
    shadow: Vec2 | None = None

    @property
    def channels(self) -> frozenset[Channel]:
        """The channels explicitly supplied by this sparse patch."""
        pairs: tuple[tuple[Channel, object], ...] = (
            ("position", self.position),
            ("scale", self.scale),
            ("rotation", self.rotation),
            ("skew", self.skew),
            ("opacity", self.opacity),
            ("fill", self.fill),
            ("outline", self.outline),
            ("border", self.border),
            ("blur", self.blur),
            ("shadow", self.shadow),
        )
        return frozenset(key for key, value in pairs if value is not None)

    def interpolate(self, base: VisualState, progress: float) -> VisualState:
        """Interpolate supplied targets from the base state, preserving omitted channels."""

        def scalar(a: float, b: float | None) -> float:
            return a if b is None else a + (b - a) * progress

        def vector(a: Vec2, b: Vec2 | None) -> Vec2:
            return a if b is None else a.lerp(b, progress)

        def color(a: Color, b: Color | None) -> Color:
            if b is None:
                return a
            return Color(
                *(
                    max(0, min(255, round(x + (y - x) * progress)))
                    for x, y in zip(
                        (a.red, a.green, a.blue), (b.red, b.green, b.blue), strict=True
                    )
                )
            )

        return VisualState(
            vector(base.position, self.position),
            vector(base.scale, self.scale),
            scalar(base.rotation, self.rotation),
            vector(base.skew, self.skew),
            scalar(base.opacity, self.opacity),
            color(base.fill, self.fill),
            color(base.outline, self.outline),
            scalar(base.border, self.border),
            scalar(base.blur, self.blur),
            vector(base.shadow, self.shadow),
            base.shadow_opacity,
        )


@runtime_checkable
class StateAnimation(Protocol):
    """Protocol for a pure normalized-progress state animation with explicitly declared written channels.

    Implement sample without depending on prior frame evaluation.
    """

    @property
    def channels(self) -> frozenset[Channel]:
        """The explicit set of VisualState channels this animation may write."""
        ...

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Evaluate normalized clip progress from the incoming state without prior-frame state."""
        ...


@dataclass(frozen=True, kw_only=True)
class Transform:
    """Custom relative motion from normalized progress, with inferred channels.

    Each supplied value is constant or a pure function of progress in 0..1.
    offset adds parent-space script pixels; scale multiplies captured scale
    (a scalar applies to both axes); rotation adds degrees; opacity multiplies
    captured opacity. Omitted fields do not write their channels. Constant values
    apply throughout the clip, rather than interpolating toward that value.

    Scaling/rotation preserve the local pivot's transformed position before
    applying offset. Both therefore also write position. StateFunction remains
    available for custom behavior needing the complete incoming VisualState.
    An omitted pivot uses the local origin on direct objects; LyricRule resolves
    it to the measured target center. Pass Vec2() to explicitly keep the origin.
    """

    offset: Vec2 | Callable[[float], Vec2] | None = None
    scale: float | Vec2 | Callable[[float], float | Vec2] | None = None
    rotation: float | Callable[[float], float] | None = None
    opacity: float | Callable[[float], float] | None = None
    pivot: Vec2 | None = None

    @property
    def channels(self) -> frozenset[Channel]:
        """Infer writes from supplied fields, including pivot compensation."""
        result: set[Channel] = set()
        if self.offset is not None or self.scale is not None or self.rotation is not None:
            result.add("position")
        if self.scale is not None:
            result.add("scale")
        if self.rotation is not None:
            result.add("rotation")
        if self.opacity is not None:
            result.add("opacity")
        return frozenset(result)

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Apply relative values to the captured state, independently of seek order."""
        finite(progress)
        offset = (
            self.offset
            if self.offset is None or isinstance(self.offset, Vec2)
            else self.offset(progress)
        )
        scale = (
            self.scale
            if self.scale is None or isinstance(self.scale, (int, float, Vec2))
            else self.scale(progress)
        )
        rotation = (
            self.rotation
            if self.rotation is None or isinstance(self.rotation, (int, float))
            else self.rotation(progress)
        )
        opacity = (
            self.opacity
            if self.opacity is None or isinstance(self.opacity, (int, float))
            else self.opacity(progress)
        )
        if scale is None and rotation is None:
            return replace(base, position=base.position if offset is None else base.position + offset,
                           opacity=base.opacity if opacity is None else base.opacity * opacity)
        factor = scale if isinstance(scale, Vec2) else Vec2(1, 1) * (
            1 if scale is None else scale
        )
        transformed = replace(
            base,
            scale=Vec2(base.scale.x * factor.x, base.scale.y * factor.y),
            rotation=base.rotation + (0 if rotation is None else rotation),
            opacity=base.opacity * (1 if opacity is None else opacity),
        )
        shift = (
            base.transform.apply(self.pivot or Vec2())
            - transformed.transform.apply(self.pivot or Vec2())
            if self.scale is not None or self.rotation is not None
            else Vec2()
        )
        return replace(
            transformed, position=base.position + shift + (offset or Vec2())
        )


@dataclass(frozen=True)
class Tween:
    """Interpolate a StatePatch from the incoming VisualState using normalized progress and an easing rate.

    The patch determines the written channels.
    """

    target: StatePatch
    rate: Callable[[float], float] = linear_rate

    @property
    def channels(self) -> frozenset[Channel]:
        """The channels written by the target StatePatch."""
        return self.target.channels

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Interpolate the target patch using eased normalized progress."""
        value = self.rate(progress)
        finite(value)
        return self.target.interpolate(base, value)


@dataclass(frozen=True)
class Slide:
    """Translate by a relative offset in script pixels and fade over the bound interval.

    An entrance moves from offset to rest. By default it reaches full opacity
    in the first quarter. Set fast_reveal=False to fade along the travel curve.
    An exit moves from rest to offset and fades throughout. Hook playback
    interpolates eligible intervals directly from the offset and easing.
    """

    offset: Vec2
    entering: bool
    fast_reveal: bool = True
    rate: Callable[[float], float] = smooth_rate

    @property
    def channels(self) -> frozenset[Channel]:
        """Move and fade relative to the captured state."""
        return frozenset(("position", "opacity"))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Evaluate the pose at normalized progress."""
        q = self.rate(progress)
        distance = 1 - q if self.entering else q
        alpha = (
            min(1.0, 4 * progress)
            if self.entering and self.fast_reveal
            else 1 - distance
        )
        return replace(
            base,
            position=base.position + self.offset * distance,
            opacity=base.opacity * alpha,
        )


@dataclass(frozen=True)
class FadeIn:
    """Reveal the incoming opacity from zero, using normalized progress.

    The final opacity is the captured base opacity, including any prior held
    animation. This works identically on a drawing or a visual parent.
    """

    rate: Callable[[float], float] = linear_rate

    @property
    def channels(self) -> frozenset[Channel]:
        """Only opacity is written."""
        return frozenset(("opacity",))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Reveal the captured opacity without changing other channels."""
        return replace(base, opacity=base.opacity * self.rate(progress))


@dataclass(frozen=True)
class FadeOut:
    """Reduce the incoming opacity to zero, using normalized progress."""

    rate: Callable[[float], float] = linear_rate

    @property
    def channels(self) -> frozenset[Channel]:
        """Only opacity is written."""
        return frozenset(("opacity",))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Fade the captured opacity without changing other channels."""
        return replace(base, opacity=base.opacity * (1 - self.rate(progress)))


@dataclass(frozen=True)
class Jump:
    """Move up and return to the captured position over normalized progress.

    Height is in script pixels; a negative height moves downward. Durations and
    lyric singing anchors belong to clip binding, not to this animation.
    """

    height: float = 12

    def __post_init__(self) -> None:
        finite(self.height)

    @property
    def channels(self) -> frozenset[Channel]:
        """Only position is written."""
        return frozenset(("position",))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Return the captured position exactly at both endpoints."""
        offset = 0.0 if progress in (0, 1) else -self.height * sin(pi * progress)
        return replace(base, position=base.position + Vec2(0, offset))


@dataclass(frozen=True)
class ScalePulse:
    """Scale up and back around a fixed local pivot over normalized progress.

    peak multiplies the captured scale; values between zero and one shrink.
    peak_at locates the peak within normalized progress (strictly between 0 and 1).
    rate eases each attack/release phase; the default has zero endpoint velocity.
    Position is adjusted to preserve
    the pivot under existing scale, rotation and skew. Binding chooses duration
    and lyric anchors; this animation works on ordinary objects and groups too.
    An omitted pivot uses the local origin on direct objects and the measured
    target center when bound with LyricRule. Vec2() explicitly selects the origin.
    """

    pivot: Vec2 | None = None
    peak: float = 1.1
    peak_at: float = 0.5
    rate: Callable[[float], float] = smooth_rate

    def __post_init__(self) -> None:
        finite(self.peak, self.peak_at)
        if self.peak <= 0:
            raise ValueError("pulse peak must be positive")
        if not 0 < self.peak_at < 1:
            raise ValueError("pulse peak_at must be strictly between 0 and 1")

    @property
    def channels(self) -> frozenset[Channel]:
        """Scale and pivot compensation both participate in conflict detection."""
        return frozenset(("position", "scale"))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Return the captured state at endpoints and preserve all other channels."""
        finite(progress)
        phase = (
            progress / self.peak_at
            if progress <= self.peak_at
            else (1 - progress) / (1 - self.peak_at)
        )
        weight = 0.0 if progress in (0, 1) else self.rate(phase)
        finite(weight)
        factor = 1 + (self.peak - 1) * weight
        if factor <= 0:
            raise ValueError("pulse curve must retain positive scale")
        scaled = replace(base, scale=base.scale * factor)
        pivot = self.pivot or Vec2()
        shift = base.transform.apply(pivot) - scaled.transform.apply(pivot)
        return replace(scaled, position=base.position + shift)


@dataclass(frozen=True)
class DriftOut:
    """Drift away while shrinking and fading, using the common relative transform.

    offset is the total displacement in parent-space script pixels. scale is the
    final factor on captured scale; pivot is local. rate controls travel, shrink
    and fade over normalized progress. travel_rate overrides only displacement
    easing (None follows rate); linear_rate gives constant-speed travel. Duration and any pause belong to binding.
    An omitted pivot uses the local origin on direct objects and the measured
    target center when bound with LyricRule. Vec2() explicitly selects the origin.
    """

    offset: Vec2 = Vec2(0, -36)
    scale: float = 0.96
    pivot: Vec2 | None = None
    rate: Callable[[float], float] = smooth_rate
    travel_rate: Callable[[float], float] | None = None

    def __post_init__(self) -> None:
        finite(self.scale)
        if self.scale <= 0:
            raise ValueError("drift scale must be positive")

    @property
    def channels(self) -> frozenset[Channel]:
        """Travel/pivot, relative scale and captured opacity."""
        return frozenset(("position", "scale", "opacity"))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Apply the same transform an author can express with custom callbacks."""
        phase = self.rate(progress)
        travel = phase if self.travel_rate is None else self.travel_rate(progress)
        finite(phase, travel)
        return Transform(
            offset=self.offset * travel,
            scale=1 + (self.scale - 1) * phase,
            opacity=1 - phase,
            pivot=self.pivot,
        ).sample(base, progress)


@dataclass(frozen=True)
class CurveIn:
    """Reveal text along a quadratic local-offset trajectory to its base pose.

    offset is the initial parent-space displacement and bend is the quadratic
    control offset; the final offset is zero. scale and rotation are the initial
    relative scale factor and added degrees. rate eases trajectory, pose and
    opacity together. Omitted pivot follows LyricRule's measured-center policy.
    """

    offset: Vec2 = Vec2(-40, 24)
    bend: Vec2 = Vec2(20, -36)
    scale: float = 0.85
    rotation: float = -12
    pivot: Vec2 | None = None
    rate: Callable[[float], float] = smooth_rate

    def __post_init__(self) -> None:
        finite(self.scale, self.rotation)
        if self.scale <= 0:
            raise ValueError("curve entrance scale must be positive")

    @property
    def channels(self) -> frozenset[Channel]:
        """Relative position, scale, rotation and opacity."""
        return frozenset(("position", "scale", "rotation", "opacity"))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Use the common relative transform to follow the authored curve."""
        p = self.rate(progress)
        finite(p)
        return Transform(
            offset=self.offset * ((1 - p) ** 2) + self.bend * (2 * p * (1 - p)),
            scale=self.scale + (1 - self.scale) * p,
            rotation=self.rotation * (1 - p), opacity=p, pivot=self.pivot,
        ).sample(base, progress)


@dataclass(frozen=True)
class StateKeyframe:
    """A target reached at a positive local time, with an incoming easing curve."""

    time: float
    target: StatePatch
    rate: Callable[[float], float] = linear_rate

    def __post_init__(self) -> None:
        finite(self.time)
        if self.time <= 0:
            raise ValueError("state keyframe time must be positive")
        if not self.target.channels:
            raise ValueError("state keyframe needs at least one property")
        if not callable(self.rate):
            raise TypeError("state keyframe rate must be callable")
        self.target.interpolate(VisualState(), 1)


@dataclass(frozen=True)
class StateFunction:
    """Custom pure evaluator. Declare written channels for conflict detection.

    Randomness must be tied to object identity, not callback invocation order.
    Standalone outputs require a compilable animation declaration.
    """

    function: Callable[[VisualState, float], VisualState]
    channels: frozenset[Channel] = CHANNELS

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Call the custom normalized-progress evaluator with the incoming visual state."""
        value = self.function(base, progress)
        if not isinstance(value, VisualState):
            raise TypeError("state function must return VisualState")
        return value


@dataclass(frozen=True)
class ShaderMotion(StateFunction):
    """Affine GPU animation with a seekable Python evaluator for state capture.

    The GLSL body receives normalized progress p, parameters at data via item(),
    and mutable local channels pos, scale, skew, angle (degrees), alpha, pen
    (outline radius), fill and outline (RGB in 0..1).
    basisOf(scale, skew, angle) returns the local linear transform.
    Supply the same motion in function for evaluation at authored boundaries.
    """

    source: str = ""
    parameters: tuple[float, ...] = ()
    progress_scale: float = 1.0
    progress_offset: float = 0.0
    functions: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip() or "//!" in self.source + self.functions:
            raise ValueError("shader motion requires a GLSL function body")
        if self.channels - {"position", "scale", "skew", "rotation", "opacity", "border", "fill", "outline"}:
            raise ValueError("shader motion supports affine channels, border, opacity, fill and outline")
        finite(self.progress_scale, self.progress_offset, *self.parameters)

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Evaluate the same local motion at a scene clock boundary."""
        return self.function(base, self.progress_offset + progress * self.progress_scale)


@dataclass(frozen=True)
class AnimationClip:
    """A positive-duration state animation starting at local clock seconds.

    hold retains final written channels; breakpoints are offsets from the clip
    start. Negative starts support visibility extended before a preserved clock
    origin. The owning node validates that the absolute start is nonnegative;
    nested sequences and Timeline still start at zero or later.
    """

    start: float
    duration: float
    animation: StateAnimation
    hold: bool = True
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.animation, AnimationSequence):
            object.__setattr__(
                self,
                "breakpoints",
                tuple(
                    sorted(
                        {
                            *self.breakpoints,
                            *(
                                value * self.duration
                                for value in self.animation.breakpoints
                            ),
                        }
                    )
                ),
            )
        finite(self.start, self.duration, *self.breakpoints)
        if any(t < 0 or t > self.duration for t in self.breakpoints):
            raise ValueError("animation breakpoint outside its local duration")
        if self.duration <= 0:
            raise ValueError("animation needs a positive duration")
        if not self.animation.channels <= CHANNELS:
            raise ValueError("animation declares unknown channels")

    @property
    def end(self) -> float:
        """The local clip start plus duration, in seconds."""
        return self.start + self.duration


def merge_channels(
    base: VisualState, value: VisualState, channels: frozenset[Channel]
) -> VisualState:
    """Ignore undeclared writes, so a custom animation cannot hijack other tracks."""
    if base is value:
        return base
    return VisualState(
        value.position if "position" in channels else base.position,
        value.scale if "scale" in channels else base.scale,
        value.rotation if "rotation" in channels else base.rotation,
        value.skew if "skew" in channels else base.skew,
        value.opacity if "opacity" in channels else base.opacity,
        value.fill if "fill" in channels else base.fill,
        value.outline if "outline" in channels else base.outline,
        value.border if "border" in channels else base.border,
        value.blur if "blur" in channels else base.blur,
        value.shadow if "shadow" in channels else base.shadow,
    )


def validate_clips(clips: tuple[AnimationClip, ...]) -> None:
    for index, clip in enumerate(clips):
        for other in clips[index + 1 :]:
            if max(local_seconds(clip.start, 0), local_seconds(other.start, 0)) < min(
                local_seconds(clip.end, 0), local_seconds(other.end, 0)
            ):
                conflict = clip.animation.channels & other.animation.channels
                if conflict:
                    raise ValueError(
                        f"overlapping animation channels: {sorted(conflict)}"
                    )


def evaluate_clips(
    base: VisualState, clips: tuple[AnimationClip, ...], time: float
) -> VisualState:
    """Absolute local time, with immutable capture at each animation's start.

    Held values are taken over by later clips. Released values restore the
    underlying state after the clip ends. Nonoverlapping channels run in parallel.
    """
    if not clips:
        return base
    at = local_seconds(time, 0)
    ordered = sorted((clip for clip in clips if local_seconds(clip.start, 0) <= at),
                     key=lambda clip: clip.start)
    captured: list[VisualState] = []

    def evaluate_prefix(at: float, count: int) -> VisualState:
        # The same 1e-10s clock used by node seeking must also apply to authored
        # boundaries: .1 + .2 and a seek to .3 denote the same instant.
        at = local_seconds(at, 0)
        result = base
        for index, clip in enumerate(ordered[:count]):
            start, end = local_seconds(clip.start, 0), local_seconds(clip.end, 0)
            if at < start or (at >= end and not clip.hold):
                continue
            progress = (
                1 if at >= end else min(1, local_seconds(at, start) / clip.duration)
            )
            value = clip.animation.sample(captured[index], progress)
            result = merge_channels(result, value, clip.animation.channels)
        return result

    for index, clip in enumerate(ordered):
        captured.append(evaluate_prefix(clip.start, index))
    return evaluate_prefix(time, len(ordered))


class Timeline:
    """Author sequential/parallel plays. Times are local to the object's birth."""

    def __init__(self) -> None:
        self._clips: list[AnimationClip] = []
        self._cursor = 0.0

    def play(
        self,
        *animations: StateAnimation,
        duration: float,
        at: float | None = None,
        hold: bool = True,
        breakpoints: tuple[float, ...] = (),
    ) -> Timeline:
        """Schedule animations; breakpoints are seconds from this play's start.

        All parallel animations receive these sampling boundaries. Repeating the
        timeline preserves them relative to each copied clip.
        """
        start = self._cursor if at is None else at
        if start < 0:
            raise ValueError("timeline start must be nonnegative")
        additions = tuple(
            AnimationClip(start, duration, animation, hold, breakpoints)
            for animation in animations
        )
        if not additions:
            raise ValueError("play needs at least one animation")
        validate_clips((*self._clips, *additions))
        self._clips.extend(additions)
        self._cursor = max(self._cursor, start + duration)
        return self

    def wait(self, duration: float) -> Timeline:
        """Advance the local seconds cursor without scheduling an animation."""
        finite(duration)
        if duration < 0:
            raise ValueError("wait duration cannot be negative")
        self._cursor += duration
        return self

    def keyframes(self, *frames: StateKeyframe, at: float | None = None) -> Timeline:
        """Reach successive targets at local seconds, retaining completed values.

        Times must increase strictly from zero. Each frame interpolates its
        declared channels from the state at the preceding frame's time; omitted
        channels retain their existing animations/state. The entire insertion
        is validated before changing the timeline.
        """
        if not frames:
            raise ValueError("keyframes requires at least one frame")
        start = self._cursor if at is None else at
        if start < 0:
            raise ValueError("timeline start must be nonnegative")
        additions: list[AnimationClip] = []
        previous = 0.0
        for frame in frames:
            if frame.time <= previous:
                raise ValueError("state keyframe times must strictly increase")
            additions.append(
                AnimationClip(
                    start + previous,
                    frame.time - previous,
                    Tween(frame.target, frame.rate),
                )
            )
            previous = frame.time
        validate_clips((*self._clips, *additions))
        self._clips.extend(additions)
        self._cursor = max(self._cursor, start + previous)
        return self

    def repeat(self, count: int) -> Timeline:
        """Repeat a complete schedule while preserving clip-local clocks and breakpoints."""
        if type(count) is not int or count < 1 or self._cursor <= 0:
            raise ValueError("repeat requires a positive count and nonempty duration")
        original, duration = tuple(self._clips), self._cursor
        self._clips = [
            replace(clip, start=clip.start + iteration * duration)
            for iteration in range(count)
            for clip in original
        ]
        self._cursor *= count
        return self

    @property
    def clips(self) -> tuple[AnimationClip, ...]:
        """The validated immutable AnimationClip schedule for assignment to an object."""
        return tuple(self._clips)

    @property
    def animation(self) -> AnimationSequence:
        """Freeze this schedule as an animation reusable on any visual target.

        The containing clip's duration scales the entire schedule, including
        waits and repeats. Interior boundaries propagate into ordinary sampling.
        """
        return AnimationSequence(tuple(self._clips), self._cursor)


@dataclass(frozen=True)
class AnimationSequence:
    """A nested schedule evaluated by the same clip evaluator as a visual node.

    Build through Timeline.animation. Duration is the schedule's local length;
    normalized outer progress maps onto that length. There is no secondary
    evaluator or incremental playback state.
    """

    clips: tuple[AnimationClip, ...]
    duration: float

    def __post_init__(self) -> None:
        finite(self.duration)
        if self.duration <= 0 or not self.clips:
            raise ValueError("animation sequence needs clips and positive duration")
        validate_clips(self.clips)
        if any(clip.start < 0 for clip in self.clips):
            raise ValueError("sequence clip start must be nonnegative")
        if any(clip.end > self.duration for clip in self.clips):
            raise ValueError("sequence clip extends beyond its duration")

    @property
    def channels(self) -> frozenset[Channel]:
        """All channels written by the schedule."""
        return frozenset(
            channel for clip in self.clips for channel in clip.animation.channels
        )

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Normalized internal boundaries, including nested child boundaries."""
        return tuple(
            sorted(
                {
                    value / self.duration
                    for clip in self.clips
                    for value in (
                        clip.start,
                        clip.end,
                        *(clip.start + t for t in clip.breakpoints),
                    )
                }
            )
        )

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Evaluate the immutable schedule at normalized outer progress."""
        return evaluate_clips(base, self.clips, round(progress * self.duration, 10))


def _resolve_pivot(animation: StateAnimation, center: Vec2) -> StateAnimation:
    """Resolve lyric geometry without adding an animation evaluator or wrapper."""
    if isinstance(animation, (Transform, ScalePulse, DriftOut, CurveIn)):
        return replace(animation, pivot=center) if animation.pivot is None else animation
    if isinstance(animation, AnimationSequence):
        return replace(animation, clips=tuple(
            replace(clip, animation=_resolve_pivot(clip.animation, center))
            for clip in animation.clips
        ))
    return animation


@dataclass(frozen=True)
class _TranslatedAnimation:
    animation: StateAnimation
    offset: Vec2

    @property
    def channels(self) -> frozenset[Channel]:
        return self.animation.channels

    def sample(self, base: VisualState, progress: float) -> VisualState:
        local = replace(base, position=base.position - self.offset)
        value = self.animation.sample(local, progress)
        return replace(value, position=value.position + self.offset)


def translate_clips(
    clips: tuple[AnimationClip, ...], offset: Vec2
) -> tuple[AnimationClip, ...]:
    if offset == Vec2():
        return clips
    shifted: list[AnimationClip] = []
    for clip in clips:
        animation = clip.animation
        if isinstance(animation, Tween):
            if animation.target.position is not None:
                animation = replace(
                    animation,
                    target=replace(
                        animation.target, position=animation.target.position + offset
                    ),
                )
        else:
            animation = _TranslatedAnimation(animation, offset)
        shifted.append(replace(clip, animation=animation))
    return tuple(shifted)
