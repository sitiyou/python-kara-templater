"""Resolve author property rules to existing visual targets before expansion."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from .targets import PreparedLyrics

from .animation import Pulse, ScaleAnimation, plan_pulses
from .ass_output import OutputCapabilityError
from .characters import TextRange, layout_characters, select_characters
from .follow import Follow
from .lowering import native_motions
from .model import Segment
from .properties import (
    BackRate,
    Contextual,
    Keyframes,
    PropertyContext,
    PropertyTarget,
    TimeInterval,
    Transition,
    expression,
    linear,
    resolve_interval,
    singing,
    singing_points,
    singing_progress,
    there_and_back,
)
from .sources import EventOrigin, SourceRef, _source_context
from .timeline import DisplayWindow, _finite


@dataclass(frozen=True)
class MotionRule:
    units: tuple[int, ...]
    mode: str
    value: object
    during: TimeInterval
    keep: bool = False
    ranges: tuple[TextRange, ...] | None = None
    property: str = "scale"
    compose: str = "replace"
    progress: str = "envelope"
    arrival: Pulse | None = None
    segments: tuple[tuple[int, int], ...] | None = None
    breakpoints: tuple[float, ...] = ()


def declare_properties(
    properties,
    *,
    during,
    keep=False,
    compose="replace",
    progress="envelope",
    arrival=None,
    units=(),
    mode="halo",
    ranges=None,
    segments=None,
) -> tuple[MotionRule, ...]:
    if len(during) != 2:
        raise ValueError("during requires start and end")
    if type(keep) is not bool:
        raise TypeError("keep must be bool")
    if progress not in {"envelope", "singing"}:
        raise ValueError("progress must be envelope or singing")
    if progress == "singing" and tuple(during) != (singing.start, singing.end):
        raise ValueError("singing progress requires the source singing interval")
    if not properties:
        raise ValueError("animation needs at least one property")
    pending: list[MotionRule] = []
    for name, value in properties.items():
        if name not in _BASE or (name == "glow_blur" and mode != "halo"):
            raise ValueError(f"unsupported animated property {name!r}")
        allowed = {
            "replace",
            "override",
            "multiply" if name in {"scale", "opacity"} else "add",
        }
        if compose not in allowed:
            raise ValueError(f"{name} does not support composition {compose!r}")
        value = value if isinstance(value, Keyframes) else expression(value)
        pending.append(
            MotionRule(
                units,
                mode,
                value,
                tuple(during),
                keep,
                ranges,
                name,
                compose,
                progress,
                arrival,
                segments,
            )
        )
    return tuple(pending)


_BASE = {
    "scale": 1.0,
    "opacity": 1.0,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "glow_blur": None,
}


def _validate_property(name: str, value: object) -> float:
    _finite(value, f"{name} result")
    assert isinstance(value, (float, int))
    if name == "scale" and value <= 0:
        raise ValueError("scale must be positive")
    if name == "opacity" and not 0 <= value <= 1:
        raise ValueError("opacity must be in 0..1")
    if name == "glow_blur" and value < 0:
        raise ValueError("blur must be nonnegative")
    return value


@dataclass(frozen=True)
class BoundProperty:
    interval: tuple[float, float]
    value: object
    keep: bool
    pivot: tuple[float, float]
    points: tuple[tuple[float, float], ...] | None
    frames: tuple[tuple[float, float, Callable[[float], float]], ...] | None = None
    property: str = "scale"
    compose: str = "replace"
    progress: str = "envelope"
    segments: tuple[Segment, ...] = ()
    target: PropertyTarget | None = None
    window: DisplayWindow | None = None
    scope: Literal["group", "unit", "local"] = "local"
    breakpoints: tuple[float, ...] = ()

    def at(self, time: float) -> float | None:
        start, end = self.interval
        if time < start or (time >= end and not self.keep):
            return _BASE[self.property]
        absolute_time = min(time, end)
        p = 1.0 if start == end else min(1.0, (time - start) / (end - start))
        if self.progress == "singing":
            p = singing_progress(time, self.segments)
            time = start + p * (end - start)
        if isinstance(self.value, Contextual):
            if self.target is None or self.window is None:
                raise ValueError("contextual property requires a bound target")
            result = self.value(
                PropertyContext(
                    absolute_time,
                    p,
                    self.interval,
                    self.window,
                    self.target,
                    self.value.seed,
                )
            )
        elif self.frames is not None:
            if time >= end:
                result = self.frames[-1][1]
            else:
                for (a, av, rate), (b, bv, _) in pairwise(self.frames):
                    if a <= time <= b:
                        fraction = rate((time - a) / (b - a))
                        _finite(fraction, "keyframe rate")
                        result = av + (bv - av) * fraction
                        break
                else:
                    raise ValueError("time is outside keyframe intervals")
        else:
            result = self.value(p) if callable(self.value) else self.value
        return _validate_property(self.property, result)


def bind_property(
    rule, segments, window, pivot, *, interval=None, target=None
) -> BoundProperty | None:
    interval = (
        resolve_interval(rule.during, segments, window)
        if interval is None
        else interval
    )
    if interval is None:
        return None
    start, end = interval
    value, frames, points = rule.value, None, None
    if isinstance(value, Keyframes):
        frames = value.resolve(interval, segments, window, progress=rule.progress)
        if all(rate is linear for _, _, rate in frames):
            points = tuple((t, v) for t, v, _ in frames)
    elif isinstance(value, Transition) and value.rate is linear:
        points = ((start, value.start), (end, value.end))
    elif isinstance(value, Transition) and value.rate is there_and_back:
        points = (
            (start, value.start),
            ((start + end) / 2, value.end),
            (end, value.start),
        )
    elif (
        isinstance(value, Transition)
        and isinstance(value.rate, BackRate)
        and value.rate.native_points is not None
    ):
        points = tuple(
            (
                start + (end - start) * p,
                value.start + (value.end - value.start) * fraction,
            )
            for p, fraction in value.rate.native_points
        )
    elif not callable(value):
        points = ((start, value), (end, value))
    if points is not None:
        for _, value_at in points:
            _validate_property(rule.property, value_at)
    if rule.progress == "singing" and points is not None:
        points = singing_points(points, interval, segments, keep=rule.keep)
    return BoundProperty(
        interval,
        value,
        rule.keep,
        pivot,
        points,
        frames,
        rule.property,
        rule.compose,
        rule.progress,
        segments,
        target,
        window,
        breakpoints=rule.breakpoints,
    )


def resolve_behaviors(
    prepared: PreparedLyrics,
    context,
    rules,
    *,
    ruby_follow,
    item_id,
    hierarchical: bool = False,
    lower_native: bool = True,
) -> tuple[PreparedLyrics, dict[str, tuple[BoundProperty, ...]]]:
    targets, schedules = [], {}
    sampled: dict[str, tuple[BoundProperty, ...]] = {}
    # Source candidates may become a single shaped ligature. Validate selected
    # coverage against layout and bind to its real clusters, never silently drop
    # a rule because its source candidate has no exact visual counterpart.
    characters = None
    if any(r.ranges is not None for r in rules):
        characters = layout_characters(context.layout, style=context.style)
        normalized = []
        for rule in rules:
            if rule.ranges is None:
                normalized.append(rule)
                continue
            merged = []
            for span in sorted(rule.ranges, key=lambda r: (r.unit_index, r.start)):
                if (
                    merged
                    and merged[-1].unit_index == span.unit_index
                    and span.start <= merged[-1].end
                ):
                    merged[-1] = replace(merged[-1], end=max(merged[-1].end, span.end))
                else:
                    merged.append(span)
            selected = []
            for span in merged:
                with _source_context(
                    EventOrigin(
                        (SourceRef(item_id, span.unit_index),), "property animation"
                    )
                ):
                    selected.extend(
                        c.source for c in select_characters(characters, span)
                    )
            normalized.append(replace(rule, ranges=tuple(selected)))
        rules = tuple(normalized)
    # Threshold scheduling runs once per trigger configuration, before expansion.
    arrivals = {r.arrival for r in rules if r.arrival is not None}
    if arrivals:
        if characters is None:
            characters = layout_characters(context.layout, style=context.style)
        tracks = {
            t.id: t for v in prepared.targets if v.kind == "body" for t in v.tracks
        }
        for trigger in arrivals:
            schedule = plan_pulses(
                (trigger,),
                layout=context.layout,
                characters=tuple(c.target for c in characters),
                tracks=tuple(tracks.values()),
                window=prepared.window,
                check_conflicts=False,
            )
            schedules[trigger] = schedule.animations
    for visual in prepared.targets:
        ui = visual.sources[0].unit_index
        relevant = [
            r
            for r in rules
            if ui in r.units
            and (r.mode != "ruby" or visual.kind == "ruby")
            and (
                r.segments is None
                or visual.kind != "ruby"
                or any(
                    (ref.unit_index, ref.segment_index) in r.segments
                    for ref in visual.sources
                )
            )
            and (
                visual.kind == "ruby"
                or r.ranges is None
                or visual.text_range in r.ranges
            )
        ]
        if visual.kind == "ruby":
            if isinstance(ruby_follow, Follow):
                relevant = [
                    r
                    for r in relevant
                    if r.mode in {"ruby", "group"} or ruby_follow.allows(r.property)
                ]
            elif ruby_follow != "syllable":
                relevant = [r for r in relevant if r.mode in {"ruby", "group"}]
            if any(r.mode == "character" for r in relevant):
                raise ValueError(
                    f"{item_id}/{visual.id}: ruby syllable following cannot follow per-character motion"
                )
        bound = []
        origin = EventOrigin(
            visual.sources, "property animation", tuple(t.id for t in visual.tracks)
        )
        for rule in relevant:
            box = (
                context.layout.box
                if rule.mode == "group"
                else context.layout.units[ui].box
                if rule.mode == "syllable"
                else (visual.transform_box or visual.box)
            )
            segments = context.layout.units[ui].source.segments
            if rule.segments is not None:
                segments = tuple(
                    segments[si] for unit, si in rule.segments if unit == ui
                )
            intervals = (
                [None]
                if rule.arrival is None
                else [
                    (a.start_ms, a.end_ms)
                    for a in schedules[rule.arrival]
                    if a.target_id == visual.id
                ]
            )
            rule_origin = (
                replace(
                    origin,
                    sources=tuple(
                        SourceRef(item_id, unit, si) for unit, si in rule.segments
                    ),
                )
                if rule.segments is not None
                else origin
            )
            for interval in intervals:
                with _source_context(rule_origin):
                    motion = bind_property(
                        rule,
                        segments,
                        prepared.window,
                        (box.center, box.middle),
                        interval=interval,
                        target=PropertyTarget(
                            f"{item_id}/{visual.id}",
                            visual.text,
                            visual.kind,
                            rule_origin.sources,
                        ),
                    )
                if motion is not None:
                    if hierarchical:
                        motion = replace(
                            motion,
                            scope=(
                                "group"
                                if rule.mode == "group"
                                else "unit"
                                if rule.mode == "syllable"
                                else "local"
                            ),
                        )
                    bound.append(motion)
        check_motion_conflicts(bound, prepared.window, origin, f"{item_id}/{visual.id}")
        scales = [m for m in bound if m.property == "scale"]
        native = (
            None
            if not lower_native or needs_affine_sampling(bound)
            else native_motions(scales, prepared.window.end_ms)
        )
        if native is not None:
            animations = tuple(
                ScaleAnimation(
                    visual.id,
                    "author",
                    index,
                    *m.interval,
                    1,
                    m.pivot,
                    m.points,
                    m.keep,
                )
                for index, m in enumerate(sorted(native, key=lambda m: m.interval))
            )
            targets.append(replace(visual, animations=animations))
            bound = [m for m in bound if m.property != "scale"]
        else:
            targets.append(visual)
        if bound:
            sampled[visual.id] = tuple(bound)
    return replace(prepared, targets=tuple(targets)), sampled


def check_motion_conflicts(bound, window, origin, identity) -> None:
    for index, motion in enumerate(bound):
        for previous in bound[:index]:
            if previous.scope != motion.scope:
                # Distinct transform ancestors compose; sibling writes still
                # obey replace/add/multiply/override conflict rules below.
                continue
            if previous.property != motion.property:
                continue
            a = max(motion.interval[0], previous.interval[0], window.start_ms)
            b = min(
                window.end_ms,
                window.end_ms if motion.keep else motion.interval[1],
                window.end_ms if previous.keep else previous.interval[1],
            )
            compatible = (
                motion.compose == previous.compose and motion.compose != "replace"
            )
            if motion.property == "scale" and motion.pivot != previous.pivot:
                compatible = False
            if a < b and not compatible:
                raise OutputCapabilityError(
                    f"{identity}: {motion.property} conflict at {a}..{b} ms",
                    origin=origin,
                    time_ms=a,
                )


class PropertySamples(TypedDict, total=False):
    scale: float
    opacity: float
    offset_x: float
    offset_y: float
    glow_blur: float | None
    pivot: tuple[float, float]


def needs_affine_sampling(motions: Sequence[BoundProperty]) -> bool:
    geometry = [m for m in motions if m.property in {"scale", "offset_x", "offset_y"}]
    return (
        any(m.property == "scale" for m in geometry)
        and len({m.scope for m in geometry}) > 1
    )


def sample_hierarchy(motions: Sequence[BoundProperty], time: float) -> PropertySamples:
    """Apply reading/local, syllable, then group transforms in parent order.

    Uniform scale and translation compose as x' = scale*x + translation.
    Returning an origin pivot plus the final translation also transforms clips
    and attached paints once through the existing sampled output adapter.
    """
    if len({motion.scope for motion in motions}) <= 1:
        return sample_properties(motions, time)
    result: PropertySamples = {}
    scale, x, y, opacity = 1.0, 0.0, 0.0, 1.0
    for scope in ("local", "unit", "group"):
        values = sample_properties(tuple(m for m in motions if m.scope == scope), time)
        factor = values.get("scale", 1.0)
        px, py = values.get("pivot", (0.0, 0.0))
        x = factor * x + (1 - factor) * px + values.get("offset_x", 0.0)
        y = factor * y + (1 - factor) * py + values.get("offset_y", 0.0)
        scale *= factor
        opacity *= values.get("opacity", 1.0)
        if "glow_blur" in values:
            result["glow_blur"] = values["glow_blur"]
    result.update(offset_x=x, offset_y=y, opacity=opacity)
    if any(m.property == "scale" for m in motions):
        result.update(scale=scale, pivot=(0.0, 0.0))
    return result


def sample_properties(motions, time) -> PropertySamples:
    result: PropertySamples = {}
    for name, base in _BASE.items():
        active = [
            m
            for m in motions
            if m.property == name
            and m.interval[0] <= time
            and (time < m.interval[1] or m.keep)
        ]
        if not active:
            continue
        if active[-1].compose == "override":
            value = active[-1].at(time)
        elif active[0].compose == "multiply":
            value = base
            for motion in active:
                value *= motion.at(time)
        elif active[0].compose == "add":
            value = sum(m.at(time) for m in active)
        else:
            value = active[0].at(time)
        checked = _validate_property(name, value)
        # Enumerate supported keys so sampled kwargs remain statically typed.
        if name == "scale":
            result["scale"] = checked
        elif name == "opacity":
            result["opacity"] = checked
        elif name == "offset_x":
            result["offset_x"] = checked
        elif name == "offset_y":
            result["offset_y"] = checked
        elif name == "glow_blur":
            result["glow_blur"] = checked
        if name == "scale":
            result["pivot"] = active[0].pivot
    return result
