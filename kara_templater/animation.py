"""Resolve karaoke triggers to scale animations before choosing an ASS backend."""

from dataclasses import dataclass
from itertools import pairwise

from .sources import _source_location
from .timeline import DisplayWindow, HighlightTrack, Region, _finite, _milliseconds


@dataclass(frozen=True)
class CharacterTarget:
    """An independently drawable cluster supplied by layout, never a codepoint.

    A layout backend must establish that the cluster can be drawn independently.
    This model deliberately does not split text or claim shaping support.
    """

    id: str
    unit_index: int
    region: Region
    center_y: float
    drawable: bool = True
    center_x: float | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("character target needs a stable id")
        if type(self.unit_index) is not int or self.unit_index < 0:
            raise ValueError("unit_index must be a nonnegative integer")
        _finite(self.center_y, "center_y")
        if self.center_x is not None:
            _finite(self.center_x, "center_x")


@dataclass(frozen=True)
class HighlightEnter:
    threshold: str = "enter"

    def __post_init__(self):
        if self.threshold not in {"enter", "center", "complete"}:
            raise ValueError("threshold must be enter, center or complete")


@dataclass(frozen=True)
class SyllableStart:
    pass


@dataclass(frozen=True)
class SegmentStart:
    pass


@dataclass(frozen=True)
class Pulse:
    trigger: HighlightEnter | SyllableStart | SegmentStart = HighlightEnter()
    target: str = "triggering_char"
    pivot: str = "char_center"
    scale: float = 1.1
    duration_ms: int | str = "traversal"
    tracks: str = "first"
    track_id: str | None = None
    retrigger: bool = True

    def __post_init__(self):
        if not isinstance(self.trigger, (HighlightEnter, SyllableStart, SegmentStart)):
            raise TypeError("unsupported pulse trigger")
        if (self.target, self.pivot) not in {
            ("triggering_char", "char_center"),
            ("chars", "each_center"),
            ("syllable", "group_center"),
        }:
            raise ValueError("unsupported target/pivot pair")
        if self.target == "triggering_char" and not isinstance(
            self.trigger, HighlightEnter
        ):
            raise ValueError("triggering_char requires a character threshold trigger")
        _finite(self.scale, "scale")
        if self.scale <= 0:
            raise ValueError("scale must be positive")
        if self.duration_ms != "traversal":
            _milliseconds(self.duration_ms, "pulse duration")
        if self.tracks not in {"first", "each", "named"}:
            raise ValueError("tracks must be first, each or named")
        if (self.tracks == "named") != (self.track_id is not None):
            raise ValueError("track_id is required only for named track selection")

    @classmethod
    def each_char(cls, **kwargs):
        return cls(**kwargs)

    @classmethod
    def simultaneous_chars(cls, **kwargs):
        return cls(
            trigger=SyllableStart(), target="chars", pivot="each_center", **kwargs
        )

    @classmethod
    def whole_syllable(cls, **kwargs):
        return cls(
            trigger=SyllableStart(), target="syllable", pivot="group_center", **kwargs
        )


@dataclass(frozen=True)
class OffsetAnimation:
    """Known piecewise-linear translation applied after scaling."""

    points: tuple[tuple[float, float], ...]
    axis: str
    keep: bool = False

    def __post_init__(self):
        object.__setattr__(self, "points", tuple(tuple(p) for p in self.points))
        if (
            len(self.points) < 2
            or self.axis not in {"x", "y"}
            or type(self.keep) is not bool
        ):
            raise ValueError(
                "offset animation requires points, x/y axis and boolean keep"
            )
        for time, value in self.points:
            _finite(time, "offset time")
            _finite(value, "offset value")
        times = [t for t, _ in self.points]
        if not all(t == times[0] for t in times) and any(
            a >= b for a, b in pairwise(times)
        ):
            raise ValueError("offset point times must increase")


@dataclass(frozen=True)
class OpacityAnimation:
    """Known piecewise-linear opacity; group multiplies, glow replaces glow alpha."""

    points: tuple[tuple[float, float], ...]
    keep: bool = False
    component: str = "group"

    def __post_init__(self):
        object.__setattr__(self, "points", tuple(tuple(p) for p in self.points))
        if len(self.points) < 2:
            raise ValueError("opacity animation needs at least two points")
        if type(self.keep) is not bool or self.component not in {"group", "glow"}:
            raise ValueError("invalid opacity keep/component")
        for time, value in self.points:
            _finite(time, "opacity time")
            _finite(value, "opacity value")
            if not 0 <= value <= 1:
                raise ValueError("opacity must be in 0..1")
        times = [t for t, _ in self.points]
        if not all(t == times[0] for t in times) and any(
            a >= b for a, b in pairwise(times)
        ):
            raise ValueError("opacity point times must increase")


@dataclass(frozen=True)
class ScaleAnimation:
    target_id: str
    track_id: str
    round_id: int
    start_ms: float
    end_ms: float
    peak_scale: float
    pivot: tuple[float, float]

    keyframes: tuple[tuple[float, float], ...] | None = None
    keep: bool = False

    @property
    def points(self):
        return (
            self.keyframes
            if self.keyframes is not None
            else (
                (self.start_ms, 1.0),
                ((self.start_ms + self.end_ms) / 2, self.peak_scale),
                (self.end_ms, 1.0),
            )
        )

    def scale_at(self, time_ms: float) -> float:
        _finite(time_ms, "time")
        if time_ms < self.start_ms:
            return 1.0
        if time_ms >= self.end_ms:
            return self.points[-1][1] if self.keep else 1.0
        for (start, a), (end, b) in zip(self.points, self.points[1:]):
            if start <= time_ms <= end and end > start:
                return a + (b - a) * (time_ms - start) / (end - start)
        return 1.0

    def point_at(self, x: float, y: float, time_ms: float) -> tuple[float, float]:
        scale = self.scale_at(time_ms)
        px, py = self.pivot
        return px + (x - px) * scale, py + (y - py) * scale


@dataclass(frozen=True)
class AnimationPlan:
    animations: tuple[ScaleAnimation, ...]
    window: DisplayWindow
    diagnostics: tuple[str, ...] = ()


def _arrivals(passes, x, threshold):
    # At a partition boundary, entering belongs to the following region and
    # completing belongs to the preceding one. A pause between them matters.
    result = []
    for singing in passes:
        if threshold == "enter" and x == singing.region.right:
            continue
        if threshold == "complete" and x == singing.region.left:
            continue
        time = singing.arrival(x)
        if time is not None:
            result.append(time)
    return result


def plan_pulses(
    pulses: tuple[Pulse, ...],
    *,
    layout,
    characters: tuple[CharacterTarget, ...],
    tracks: tuple[HighlightTrack, ...],
    window: DisplayWindow,
    overflow: str = "truncate",
    check_conflicts: bool = True,
) -> AnimationPlan:
    """Resolve triggers and reject conflicting scale animations.

    Thresholds use the original character region. A threshold outside a track's
    mapped body is not crossed. First-arrival selection is per target/round and
    independent of visual track priority. Truncation retains original animation
    times so clipping a display window never restarts or accelerates a pulse.
    check_conflicts=False delegates overlap validation to a property composition
    planner, which must validate the resulting intervals before output.
    """
    if type(check_conflicts) is not bool:
        raise TypeError("check_conflicts must be bool")
    if overflow not in {"truncate", "extend"}:
        raise ValueError("overflow must be truncate or extend")
    if len({c.id for c in characters}) != len(characters):
        raise ValueError("duplicate character target ids")
    if len({t.id for t in tracks}) != len(tracks):
        raise ValueError("duplicate track ids")
    for item in (*characters, *tracks):
        if item.unit_index >= len(layout.units):
            raise ValueError(f"{item.id}: unit_index is outside the layout")
    result, diagnostics = [], []
    for pulse in pulses:
        selected = [
            t for t in tracks if pulse.tracks != "named" or t.id == pulse.track_id
        ]
        if pulse.tracks == "named" and not selected:
            raise ValueError(f"unknown track {pulse.track_id!r}")
        candidates = []
        for track in selected:
            chars = [
                c
                for c in characters
                if c.unit_index == track.unit_index and c.drawable and c.region.width
            ]
            rounds = sorted({p.round_id for p in track.passes})
            for round_id in rounds:
                passes = [p for p in track.passes if p.round_id == round_id]
                if isinstance(pulse.trigger, HighlightEnter):
                    for char in chars:
                        x = {
                            "enter": char.region.left,
                            "center": char.region.center,
                            "complete": char.region.right,
                        }[pulse.trigger.threshold]
                        arrivals = _arrivals(passes, x, pulse.trigger.threshold)
                        if not arrivals:
                            continue
                        enters = _arrivals(passes, char.region.left, "enter")
                        exits = _arrivals(passes, char.region.right, "complete")
                        if pulse.duration_ms == "traversal" and (
                            not enters or not exits
                        ):
                            with _source_location(
                                track.unit_index, track_ids=(track.id,)
                            ):
                                raise ValueError(
                                    f"{track.id}/{char.id}: incomplete traversal; specify duration_ms"
                                )
                        duration = (
                            max(0, min(exits) - min(enters)) if enters and exits else 0
                        )
                        candidates.append(
                            (
                                min(arrivals),
                                track.id,
                                round_id,
                                char.id,
                                track.unit_index,
                                duration,
                            )
                        )
                else:
                    anchors = (
                        passes
                        if isinstance(pulse.trigger, SegmentStart)
                        else passes[:1]
                    )
                    for index, singing in enumerate(anchors):
                        duration = (
                            singing.end_ms - singing.start_ms
                            if isinstance(pulse.trigger, SegmentStart)
                            else passes[-1].end_ms - passes[0].start_ms
                        )
                        candidates.append(
                            (
                                singing.start_ms,
                                track.id,
                                round_id,
                                f"segment:{index}",
                                track.unit_index,
                                duration,
                            )
                        )
        seen = set()
        for start, track_id, round_id, trigger_id, unit_index, traversal in sorted(
            candidates
        ):
            # Track id breaks simultaneous first-arrival ties deterministically.
            key = (
                unit_index,
                trigger_id,
                round_id if pulse.retrigger else None,
                track_id if pulse.tracks == "each" else None,
            )
            if key in seen:
                continue
            seen.add(key)
            duration = (
                traversal if pulse.duration_ms == "traversal" else pulse.duration_ms
            )
            end = start + duration
            for char in characters:
                if (
                    char.unit_index != unit_index
                    or not char.drawable
                    or not char.region.width
                ):
                    continue
                if pulse.target == "triggering_char" and char.id != trigger_id:
                    continue
                box = layout.units[unit_index].box
                pivot = (
                    (box.center, box.middle)
                    if pulse.pivot == "group_center"
                    else (
                        char.region.center if char.center_x is None else char.center_x,
                        char.center_y,
                    )
                )
                result.append(
                    ScaleAnimation(
                        char.id, track_id, round_id, start, end, pulse.scale, pivot
                    )
                )
    result.sort(key=lambda a: (a.target_id, a.start_ms, a.track_id))
    for i, current in enumerate(result):
        for previous in result[:i]:
            if current.target_id != previous.target_id:
                continue
            left = max(current.start_ms, previous.start_ms)
            right = min(current.end_ms, previous.end_ms)
            if overflow == "truncate":
                left, right = max(left, window.start_ms), min(right, window.end_ms)
            if check_conflicts and left < right:
                unit_index = next(
                    c.unit_index for c in characters if c.id == current.target_id
                )
                with _source_location(
                    unit_index, track_ids=(previous.track_id, current.track_id)
                ):
                    raise ValueError(
                        f"scale conflict for {current.target_id}: tracks {previous.track_id}, {current.track_id}"
                    )
    if overflow == "extend" and result:
        from math import ceil, floor

        window = DisplayWindow(
            min(window.start_ms, floor(min(a.start_ms for a in result))),
            max(window.end_ms, ceil(max(a.end_ms for a in result))),
        )
    else:
        for animation in result:
            if animation.start_ms < window.start_ms or animation.end_ms > window.end_ms:
                diagnostics.append(
                    f"{animation.target_id}/{animation.track_id}: pulse clipped by display window"
                )
    return AnimationPlan(tuple(result), window, tuple(diagnostics))
