"""Typed visual properties and stateless animation scheduling (seconds)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, Protocol

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


@dataclass(frozen=True)
class VisualState:
    """Finite drawing state in script pixels, degrees, RGB colors, and opacity 0 through 1.

    Position, scale, rotation, skew, paint, blur, and shadow compose through the
    scene hierarchy.
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

    def __post_init__(self) -> None:
        finite(self.rotation, self.opacity, self.border, self.blur)
        if not 0 <= self.opacity <= 1 or self.border < 0 or self.blur < 0:
            raise ValueError("opacity must be in 0..1, border/blur must be nonnegative")

    @property
    def singular(self) -> bool:
        """Whether this linear map collapses filled geometry to zero area."""
        return self.scale.x == 0 or self.scale.y == 0 or self.skew.x * self.skew.y == 1

    @property
    def transform(self) -> Affine2D:
        """Local shear, axis scale, clockwise rotation, then translation."""
        x = Vec2(self.scale.x, self.skew.y * self.scale.y).rotated(self.rotation)
        y = Vec2(self.skew.x * self.scale.x, self.scale.y).rotated(self.rotation)
        return Affine2D(x.x, x.y, y.x, y.y, self.position.x, self.position.y)


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
        )


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
    The compiler reports sampling intervals, not an error bound for this function.
    """

    function: Callable[[VisualState, float], VisualState]
    channels: frozenset[Channel] = CHANNELS

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Call the custom normalized-progress evaluator with the incoming visual state."""
        return self.function(base, progress)


@dataclass(frozen=True)
class AnimationClip:
    """A positive-duration state animation starting at local seconds from object birth.

    hold retains final written channels; breakpoints are offsets from the clip
    start.
    """

    start: float
    duration: float
    animation: StateAnimation
    hold: bool = True
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(self.start, self.duration, *self.breakpoints)
        if any(t < 0 or t > self.duration for t in self.breakpoints):
            raise ValueError("animation breakpoint outside its local duration")
        if self.start < 0 or self.duration <= 0:
            raise ValueError(
                "animation needs a nonnegative start and positive duration"
            )
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
            if max(clip.start, other.start) < min(clip.end, other.end):
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
    ordered = tuple(sorted(clips, key=lambda clip: clip.start))
    captured: list[VisualState] = []

    def evaluate_prefix(at: float, count: int) -> VisualState:
        result = base
        for index, clip in enumerate(ordered[:count]):
            if at < clip.start or (at >= clip.end and not clip.hold):
                continue
            progress = min(1, (at - clip.start) / clip.duration)
            value = clip.animation.sample(captured[index], progress)
            result = merge_channels(result, value, clip.animation.channels)
        return result

    for index, clip in enumerate(ordered):
        captured.append(evaluate_prefix(clip.start, index))
    return evaluate_prefix(time, len(ordered))


class SceneTimeline:
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
    ) -> SceneTimeline:
        """Schedule animations; breakpoints are seconds from this play's start.

        All parallel animations receive these sampling boundaries. Repeating the
        timeline preserves them relative to each copied clip.
        """
        start = self._cursor if at is None else at
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

    def wait(self, duration: float) -> SceneTimeline:
        """Advance the local seconds cursor without scheduling an animation."""
        finite(duration)
        if duration < 0:
            raise ValueError("wait duration cannot be negative")
        self._cursor += duration
        return self

    def keyframes(
        self, *frames: StateKeyframe, at: float | None = None
    ) -> SceneTimeline:
        """Reach successive targets at local seconds, retaining completed values.

        Times must increase strictly from zero. Each frame interpolates its
        declared channels from the state at the preceding frame's time; omitted
        channels retain their existing animations/state. The entire insertion
        is validated before changing the timeline.
        """
        if not frames:
            raise ValueError("keyframes requires at least one frame")
        start = self._cursor if at is None else at
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

    def repeat(self, count: int) -> SceneTimeline:
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
