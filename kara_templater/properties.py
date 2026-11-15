"""Property expressions evaluated on a target's normalized local time."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict, overload

from .model import Segment
from .sampling import SampleContext
from .sources import SourceRef
from .timeline import DisplayWindow, _finite, _milliseconds


@dataclass(frozen=True)
class PropertyTarget:
    """Original visual target, shared by its following decorations."""

    id: str
    text: str
    kind: str
    sources: tuple[SourceRef, ...]
    source_id: str | None = None


@dataclass(frozen=True)
class PropertyContext:
    """A scalar property callback context with millisecond time/interval, progress, target metadata, display window, and seed.

    Named noise is deterministic for that context.
    """

    time_ms: float
    progress: float
    interval: tuple[float, float]
    window: DisplayWindow
    target: PropertyTarget
    seed: int

    def noise(
        self,
        channel: str = "default",
        *,
        animated: bool = True,
        scope: Literal["target", "source"] = "target",
    ) -> float:
        """Return deterministic named noise for this target/time context and seed."""
        if scope not in {"target", "source"}:
            raise ValueError("noise scope must be target or source")
        identity = (
            self.target.source_id or self.target.id
            if scope == "source"
            else self.target.id
        )
        return SampleContext(
            self.time_ms, self.progress, self.window, identity, self.seed
        ).noise(channel, animated=animated)


@dataclass(frozen=True)
class Contextual:
    """Explicit opt-in to target/time context instead of a scalar progress."""

    function: Callable[[PropertyContext], float]
    seed: int = 0

    def __post_init__(self) -> None:
        if not callable(self.function):
            raise TypeError("contextual property requires a callable")
        if type(self.seed) is not int:
            raise TypeError("contextual property seed must be an integer")

    def __call__(self, context: PropertyContext) -> float:
        """Evaluate the scalar function using the full PropertyContext rather than progress alone."""
        return self.function(context)


def linear(p: float) -> float:
    """Return normalized progress unchanged for linear interpolation."""
    return p


def smooth(p: float) -> float:
    """Smoothly ease normalized progress with flat endpoints."""
    return p * p * (3 - 2 * p)


def ease_in(p: float) -> float:
    """An accelerating scalar easing curve for normalized progress."""
    return p * p


def ease_out(p: float) -> float:
    """A decelerating scalar easing curve for normalized progress."""
    return 1 - (1 - p) ** 2


def ease_in_out(p: float) -> float:
    """A scalar easing curve that accelerates then decelerates across normalized progress."""
    return 2 * p * p if p < 0.5 else 1 - 2 * (1 - p) ** 2


@overload
def there_and_back(
    p: float,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
) -> float: ...


@overload
def there_and_back(
    p: None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
) -> BackRate: ...


def there_and_back(
    p: float | None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
) -> float | BackRate:
    """Use as a rate directly, or configure a peak, hold, rise and fall."""
    return_at = peak_at if return_at is None else return_at
    _finite(peak_at, "peak_at")
    _finite(return_at, "return_at")
    if not 0 < peak_at <= return_at < 1:
        raise ValueError("require 0 < peak_at <= return_at < 1")
    if not callable(rise) or not callable(fall):
        raise TypeError("rise and fall must be rate functions")

    rate = BackRate(peak_at, return_at, rise, fall)
    return rate if p is None else rate(p)


@dataclass(frozen=True)
class BackRate:
    peak_at: float
    return_at: float
    rise: Callable[[float], float]
    fall: Callable[[float], float]

    def __call__(self, progress: float) -> float:
        if progress < self.peak_at:
            return self.rise(progress / self.peak_at)
        if progress <= self.return_at:
            return 1.0
        return 1 - self.fall((progress - self.return_at) / (1 - self.return_at))

    @property
    def native_points(self) -> tuple[tuple[float, float], ...] | None:
        if self.rise is not linear or self.fall is not linear:
            return None
        points = [(0, 0), (self.peak_at, 1)]
        if self.return_at > self.peak_at:
            points.append((self.return_at, 1))
        return (*points, (1, 0))


@dataclass(frozen=True)
class Transition:
    """A normalized scalar transition between start and end using an easing rate.

    Track declarations resolve its timing independently of its values.
    """

    start: float
    end: float
    rate: Callable[[float], float] = linear

    def __post_init__(self) -> None:
        _finite(self.start, "transition start")
        _finite(self.end, "transition end")
        if not callable(self.rate):
            raise TypeError("transition rate must be callable")

    def __call__(self, progress: float) -> float:
        """Evaluate the eased scalar transition at normalized progress."""
        fraction = self.rate(progress)
        _finite(fraction, "transition rate result")
        return self.start + (self.end - self.start) * fraction


def expression(
    value: float | tuple[float, float] | Contextual | Callable[[float], float],
) -> float | Contextual | Callable[[float], float]:
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError("property transition requires two endpoints")
        return Transition(*value)
    if callable(value):
        return value
    _finite(value, "property value")
    return value


def singing_progress(time: float, segments: tuple[Segment, ...]) -> float:
    duration = sum(s.end_ms - s.start_ms for s in segments)
    elapsed = sum(max(0, min(time, s.end_ms) - s.start_ms) for s in segments)
    return (
        min(1, elapsed / duration)
        if duration
        else float(bool(segments) and time >= max(s.end_ms for s in segments))
    )


def singing_points(
    points: tuple[tuple[float, float], ...],
    interval: tuple[float, float],
    segments: tuple[Segment, ...],
    *,
    keep: bool,
) -> tuple[tuple[float, float], ...] | None:
    """Map a known linear progress curve onto the original singing clock."""
    start, end = interval
    duration = sum(s.end_ms - s.start_ms for s in segments)
    if not duration or start == end:
        return None
    # A kept rule ending before the last segment still evolves under the sampled
    # singing-progress contract. A native held endpoint cannot represent that.
    if keep and end < max(s.end_ms for s in segments):
        return None
    knots: set[float] = {start, end}
    elapsed = 0
    for segment in segments:
        length = segment.end_ms - segment.start_ms
        knots.update(t for t in (segment.start_ms, segment.end_ms) if start < t < end)
        for time, _ in points[1:-1]:
            target = (time - start) / (end - start) * duration
            if length and elapsed <= target <= elapsed + length:
                mapped = segment.start_ms + target - elapsed
                if start < mapped < end:
                    knots.add(mapped)
        elapsed += length

    def value(time: float) -> float:
        virtual = start + singing_progress(time, segments) * (end - start)
        if virtual >= points[-1][0]:
            return points[-1][1]
        for (a, av), (b, bv) in itertools.pairwise(points):
            if a <= virtual < b:
                return av + (bv - av) * (virtual - a) / (b - a)
        raise ValueError("singing progress precedes curve")

    return tuple((time, value(time)) for time in sorted(knots))


@dataclass(frozen=True)
class TimeRef:
    """A millisecond offset from a named singing/display anchor.

    Adding or subtracting milliseconds creates another reference; resolve binds it
    to source intervals.
    """

    anchor: str
    offset: int = 0

    def __post_init__(self) -> None:
        if self.anchor not in {
            "singing.start",
            "singing.end",
            "display.start",
            "display.end",
        }:
            raise ValueError("unknown time anchor")
        if type(self.offset) is not int:
            raise TypeError("time offsets must be integer milliseconds")

    def __add__(self, milliseconds: int) -> TimeRef:
        if type(milliseconds) is not int:
            raise TypeError("time offsets must be integer milliseconds")
        return TimeRef(self.anchor, self.offset + milliseconds)

    def __sub__(self, milliseconds: int) -> TimeRef:
        return self + (-milliseconds)

    def resolve(
        self, segments: tuple[Segment, ...], window: DisplayWindow
    ) -> int | None:
        """Resolve this anchor and millisecond offset against singing segments and display window."""
        if self.anchor.startswith("singing.") and not segments:
            return None
        anchors = {
            "display.start": window.start_ms,
            "display.end": window.end_ms,
        }
        if segments:
            anchors.update(
                {
                    "singing.start": min(s.start_ms for s in segments),
                    "singing.end": max(s.end_ms for s in segments),
                }
            )
        return anchors[self.anchor] + self.offset


@dataclass(frozen=True)
class _Clock:
    start: TimeRef
    end: TimeRef


singing = _Clock(TimeRef("singing.start"), TimeRef("singing.end"))
display = _Clock(TimeRef("display.start"), TimeRef("display.end"))


def resolve_interval(
    during: TimeInterval, segments: tuple[Segment, ...], window: DisplayWindow
) -> tuple[int, int] | None:
    values = tuple(
        v.resolve(segments, window) if isinstance(v, TimeRef) else v for v in during
    )
    if any(v is None for v in values):
        return None
    if any(type(v) is not int for v in values):
        raise ValueError(
            "animation interval endpoints must resolve to integer milliseconds"
        )
    start, end = values
    assert isinstance(start, int) and isinstance(end, int)
    if end < start:
        raise ValueError(f"reversed animation interval: {start}..{end} ms")
    return start, end


@dataclass(frozen=True)
class Keyframe:
    """A scalar target at a normalized fraction or millisecond TimeRef with an incoming easing curve.

    Resolution binds it to the selected interval.
    """

    at: float | TimeRef
    value: float
    rate: Callable[[float], float] = linear

    def __post_init__(self) -> None:
        if not isinstance(self.at, TimeRef):
            _finite(self.at, "keyframe fraction")
            if not 0 <= self.at <= 1:
                raise ValueError("keyframe fractions must be in 0..1")
        _finite(self.value, "keyframe value")
        if not callable(self.rate):
            raise TypeError("keyframe rate must be callable")


@dataclass(frozen=True, init=False)
class Keyframes:
    """Ordered scalar keyframes for a property interval.

    Use explicit TimeRef values when targets depend on singing or display anchors.
    """

    frames: tuple[Keyframe, ...]

    def __init__(self, *frames: Keyframe) -> None:
        if len(frames) < 2 or any(not isinstance(f, Keyframe) for f in frames):
            raise ValueError("Keyframes requires at least two Keyframe values")
        object.__setattr__(self, "frames", tuple(frames))

    def resolve(
        self,
        interval: tuple[float, float],
        segments: tuple[Segment, ...],
        window: DisplayWindow,
        *,
        progress: ProgressMode = "envelope",
    ) -> tuple[tuple[float, float, Callable[[float], float]], ...]:
        """Resolve normalized fractions or TimeRef anchors to the selected millisecond property interval."""
        start, end = interval

        def timestamp(frame: Keyframe) -> float:
            if isinstance(frame.at, TimeRef):
                resolved = frame.at.resolve(segments, window)
                if resolved is None:
                    raise ValueError("keyframe has no singing time")
                if progress == "singing":
                    return start + singing_progress(resolved, segments) * (end - start)
                return resolved
            return start + (end - start) * frame.at

        points = tuple((timestamp(f), f.value, f.rate) for f in self.frames)
        if any(t is None for t, _, _ in points):
            raise ValueError("keyframe has no singing time")
        if points[0][0] != start or points[-1][0] != end:
            raise ValueError(
                "keyframes must begin and end at the binding interval endpoints"
            )
        fractions = [f.at for f in self.frames if not isinstance(f.at, TimeRef)]
        if any(a >= b for a, b in itertools.pairwise(fractions)):
            raise ValueError("keyframe fractions must increase")
        if start == end and all(t == start for t, _, _ in points):
            return points
        if any(a[0] >= b[0] for a, b in itertools.pairwise(points)):
            raise ValueError(
                f"keyframe times must increase, got {[p[0] for p in points]} ms"
            )
        return points


# Public declaration types; expressions retain the scalar callback signature.
type PropertyValue = (
    float
    | tuple[float, float]
    | Transition
    | Keyframes
    | Contextual
    | Callable[[float], float]
)
type TimePoint = int | TimeRef
type TimeInterval = tuple[TimePoint, TimePoint]
type CompositionMode = Literal["replace", "override", "add", "multiply"]
type ProgressMode = Literal["envelope", "singing"]


class AnimatedProperties(TypedDict, total=False):
    """The typed sparse geometry properties accepted by low-level Track behavior declarations.

    Omitted properties do not write or reset unrelated channels.
    """

    scale: PropertyValue
    opacity: PropertyValue
    offset_x: PropertyValue
    offset_y: PropertyValue


@dataclass(frozen=True, kw_only=True)
class Envelope:
    """A scale envelope with a peak and millisecond attack/release durations.

    Rise and fall functions receive normalized progress.
    """

    peak: float = 1.1
    attack: int = 80
    release: int = 160
    rise: Callable[[float], float] = linear
    fall: Callable[[float], float] = linear

    def __post_init__(self) -> None:
        _finite(self.peak, "envelope peak")
        _milliseconds(self.attack, "attack")
        _milliseconds(self.release, "release")
        if not callable(self.rise) or not callable(self.fall):
            raise TypeError("envelope rates must be callable")

    def _keyframes(self, duration: int, base: float) -> PropertyValue:
        total = duration + self.release
        if total == 0:
            return base
        attack = min(self.attack, duration)
        points = [
            Keyframe(
                0,
                base if attack else self.peak,
                self.rise if attack else self.fall if not duration else linear,
            )
        ]
        if attack:
            points.append(
                Keyframe(
                    attack / total,
                    self.peak,
                    self.fall if attack == duration else linear,
                )
            )
        if duration > attack:
            points.append(Keyframe(duration / total, self.peak, self.fall))
        if self.release:
            points.append(Keyframe(1, base))
        return Keyframes(*points) if len(points) > 1 else base
