"""Resolve author property rules to existing visual targets before expansion."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import TYPE_CHECKING, Literal, Self, TypedDict

if TYPE_CHECKING:
    from .effect import Component
    from .targets import PreparedLyrics

from .animation import HighlightEnter, Pulse, ScaleAnimation, plan_pulses
from .ass_output import OutputCapabilityError
from .characters import TextRange, _clusters, layout_characters, select_characters
from .follow import Follow
from .lowering import native_motions
from .model import KaraokeLine, Segment
from .properties import (
    AnimatedProperties,
    BackRate,
    CompositionMode,
    Contextual,
    Keyframes,
    ProgressMode,
    PropertyContext,
    PropertyTarget,
    PropertyValue,
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
from .stylesheet import UNSET, SelectionStyle, Selector, StyleKeyword
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


class TargetSelection:
    units: tuple[int, ...]
    mode: str
    ranges: tuple[TextRange, ...] | None

    def __init__(
        self,
        source: KaraokeLine,
        rules: list[MotionRule],
        *,
        item_id: str,
        style_targets: Callable[[TargetSelection], tuple[Component, ...]] | None = None,
        query_target: Callable[[TargetSelection], Component] | None = None,
        units: Iterable[int] | None = None,
        mode: str = "syllable",
        ranges: tuple[TextRange, ...] | None = None,
        segments: tuple[tuple[int, int], ...] | None = None,
    ) -> None:
        self.source = source
        self.item_id = item_id
        self._style_targets = style_targets
        self._query_target = query_target
        self._rules = rules
        self.units = tuple(range(len(source.units))) if units is None else tuple(units)
        self.mode = mode
        self.ranges = ranges
        self._segments = segments

    def _style_nodes(self) -> tuple[Component, ...]:
        if self._style_targets is None:
            raise ValueError("selection is not bound to author styles")
        return self._style_targets(self)

    @property
    def style(self) -> SelectionStyle:
        return SelectionStyle(tuple(node.style for node in self._style_nodes()))

    def add_class(self, *names: str) -> Self:
        # Validate even empty selections, without partially changing targets.
        if any(
            not isinstance(n, str) or not n or any(c.isspace() for c in n)
            for n in names
        ):
            raise ValueError("class names must be nonempty without whitespace")
        for node in self._style_nodes():
            node.add_class(*names)
        return self

    @property
    def _segment_members(self) -> tuple[tuple[int, int], ...]:
        assert self._segments is not None
        return self._segments

    @property
    def _character_members(self) -> tuple[TextRange, ...]:
        if self.ranges is not None:
            return self.ranges
        return tuple(
            TextRange(ui, start, end)
            for ui in self.units
            for start, end, _ in _clusters(self.source.units[ui].text)
        )

    @property
    def _members(self):
        if self.mode in {"segment", "ruby"}:
            return self._segments
        if self.mode == "syllable":
            return self.units
        if self.ranges is not None:
            return self.ranges
        # Source candidates only. Final measurement verifies independent drawing
        # and cluster boundaries before any selected animation is compiled.
        return tuple(
            TextRange(ui, start, end)
            for ui in self.units
            for start, end, _ in _clusters(self.source.units[ui].text)
        )

    def __iter__(self) -> Iterator[TargetSelection]:
        return (self[index] for index in range(len(self)))

    def __len__(self) -> int:
        return len(self._members)

    def __getitem__(self, index: int | slice) -> TargetSelection:
        members = self._members[index]
        members = members if isinstance(index, slice) else (members,)
        return self._with_members(members)

    def _with_members(self, members) -> TargetSelection:
        if self.mode in {"segment", "ruby"}:
            return TargetSelection(
                self.source,
                self._rules,
                item_id=self.item_id,
                style_targets=self._style_targets,
                query_target=self._query_target,
                units=tuple(dict.fromkeys(ui for ui, _ in members)),
                mode=self.mode,
                segments=members,
            )
        if self.mode == "character":
            return TargetSelection(
                self.source,
                self._rules,
                item_id=self.item_id,
                style_targets=self._style_targets,
                query_target=self._query_target,
                units=tuple(dict.fromkeys(r.unit_index for r in members)),
                mode=self.mode,
                ranges=members,
            )
        return TargetSelection(
            self.source,
            self._rules,
            item_id=self.item_id,
            style_targets=self._style_targets,
            query_target=self._query_target,
            units=members,
            mode=self.mode,
        )

    def query(self, selector: str) -> TargetSelection:
        """Filter this source collection without inspecting or creating output layers."""
        parsed = Selector.parse(selector)
        if self._query_target is None:
            raise ValueError("selection is not bound to author queries")
        members = tuple(
            member
            for member in self._members
            if parsed.matches(self._query_target(self._with_members((member,))))
        )
        return self._with_members(members)

    def query_one(self, selector: str) -> TargetSelection:
        found = self.query(selector)
        if len(found) != 1:
            raise ValueError(
                f"selector {selector!r} expected one source target, found {len(found)}"
            )
        return found

    @property
    def text(self) -> str:
        if self.mode == "ruby":
            return "".join(self.readings)
        if self.mode == "character":
            return "".join(
                self.source.units[r.unit_index].text[r.start : r.end]
                for r in self._character_members
            )
        return "".join(self.source.units[i].text for i in self.units)

    @property
    def segments(self) -> TargetSelection:
        """Singing segments, in source order; static units contribute no members."""
        if self.mode == "segment":
            return self
        if self.mode == "ruby":
            return TargetSelection(
                self.source,
                self._rules,
                item_id=self.item_id,
                style_targets=self._style_targets,
                query_target=self._query_target,
                units=self.units,
                mode="segment",
                segments=self._members,
            )
        if self.mode == "character":
            raise ValueError(
                "select segments from syllables, not pre-layout characters"
            )
        members = tuple(
            (ui, si)
            for ui in self.units
            for si in range(len(self.source.units[ui].segments))
        )
        return TargetSelection(
            self.source,
            self._rules,
            item_id=self.item_id,
            style_targets=self._style_targets,
            query_target=self._query_target,
            units=tuple(dict.fromkeys(ui for ui, _ in members)),
            mode="segment",
            segments=members,
        )

    @property
    def rubies(self) -> TargetSelection:
        """Nonempty source readings, independently configurable before layout."""
        if self.mode == "ruby":
            return self
        members = tuple(
            (ui, si)
            for ui, si in self.segments._members
            if self.source.units[ui].segments[si].ruby
        )
        return TargetSelection(
            self.source,
            self._rules,
            item_id=self.item_id,
            style_targets=self._style_targets,
            query_target=self._query_target,
            units=tuple(dict.fromkeys(ui for ui, _ in members)),
            mode="ruby",
            segments=members,
        )

    @property
    def characters(self) -> TargetSelection:
        if self.mode in {"segment", "ruby"}:
            raise ValueError("select characters from syllables, not temporal segments")
        if self.mode == "character":
            return self
        return TargetSelection(
            self.source,
            self._rules,
            item_id=self.item_id,
            style_targets=self._style_targets,
            query_target=self._query_target,
            units=self.units,
            mode="character",
        )

    @property
    def _selected_units(self) -> tuple[int, ...]:
        if self.mode == "character":
            return tuple(dict.fromkeys(r.unit_index for r in self._character_members))
        return self.units

    @property
    def source_refs(self) -> tuple[SourceRef, ...]:
        if self.mode in {"segment", "ruby"}:
            return tuple(SourceRef(self.item_id, ui, si) for ui, si in self._members)
        return tuple(SourceRef(self.item_id, ui) for ui in self._selected_units)

    @property
    def intervals(self) -> tuple[tuple[int, int], ...]:
        """Original singing intervals, without coalescing gaps or zero durations."""
        members = (
            self._segment_members
            if self.mode in {"segment", "ruby"}
            else (
                (ui, si)
                for ui in self._selected_units
                for si in range(len(self.source.units[ui].segments))
            )
        )
        return tuple(
            (
                self.source.units[ui].segments[si].start_ms,
                self.source.units[ui].segments[si].end_ms,
            )
            for ui, si in members
        )

    @property
    def readings(self) -> tuple[str, ...]:
        if self.mode not in {"segment", "ruby"}:
            raise ValueError("readings requires a segment selection")
        return tuple(
            self.source.units[ui].segments[si].ruby for ui, si in self._segment_members
        )

    def on_singing(
        self,
        *,
        pulse: float | None = None,
        keep: bool = False,
        compose: CompositionMode = "replace",
        progress: ProgressMode = "envelope",
        scale: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        opacity: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_x: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_y: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
    ) -> Self:
        properties = _animated_properties(scale, opacity, offset_x, offset_y)
        if pulse is not None:
            if "scale" in properties:
                raise ValueError("pulse and scale write the same property")
            properties["scale"] = Transition(1, pulse, rate=there_and_back)
        return self.animate(
            during=(singing.start, singing.end),
            keep=keep,
            compose=compose,
            progress=progress,
            **properties,
        )

    def on_highlight(
        self,
        *,
        duration_ms: int | Literal["traversal"] = "traversal",
        threshold: Literal["enter", "center", "complete"] = "enter",
        tracks: Literal["first", "each", "named"] = "first",
        track_id: str | None = None,
        retrigger: bool = True,
        pulse: float | None = None,
        keep: bool = False,
        compose: CompositionMode = "replace",
        scale: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        opacity: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_x: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_y: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
    ) -> Self:
        properties = _animated_properties(scale, opacity, offset_x, offset_y)
        if self.mode != "character":
            raise ValueError("on_highlight requires a character selection")
        if pulse is not None:
            if "scale" in properties:
                raise ValueError("pulse and scale write the same property")
            properties["scale"] = Transition(1, pulse, rate=there_and_back)
        trigger = Pulse(
            trigger=HighlightEnter(threshold),
            duration_ms=duration_ms,
            tracks=tracks,
            track_id=track_id,
            retrigger=retrigger,
            scale=1,
        )
        return self._add(
            properties, (singing.start, singing.end), keep, compose, "envelope", trigger
        )

    def animate(
        self,
        *,
        during: TimeInterval,
        keep: bool = False,
        compose: CompositionMode = "replace",
        progress: ProgressMode = "envelope",
        scale: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        opacity: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_x: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
        offset_y: PropertyValue | Literal[StyleKeyword.UNSET] = UNSET,
    ) -> Self:
        properties = _animated_properties(scale, opacity, offset_x, offset_y)
        return self._add(properties, during, keep, compose, progress, None)

    def _add(self, properties, during, keep, compose, progress, arrival) -> Self:
        if self.mode in {"segment", "ruby"}:
            # Each segment owns a separate clock, even when a selection includes
            # multiple readings of the same unit. Validate before committing.
            pending = []
            for ui, si in self._members:
                pending.extend(
                    declare_properties(
                        properties,
                        during=during,
                        keep=keep,
                        compose=compose,
                        progress=progress,
                        units=(ui,),
                        mode="ruby" if self.mode == "ruby" else "syllable",
                        segments=((ui, si),),
                    )
                )
            # Empty selections still validate declarations like other selections.
            if not self._members:
                declare_properties(
                    properties,
                    during=during,
                    keep=keep,
                    compose=compose,
                    progress=progress,
                )
            self._rules.extend(pending)
            return self
        self._rules.extend(
            declare_properties(
                properties,
                during=during,
                keep=keep,
                compose=compose,
                progress=progress,
                arrival=arrival,
                units=self.units,
                mode=self.mode,
                ranges=self.ranges,
            )
        )
        return self


def _animated_properties(
    scale: PropertyValue | Literal[StyleKeyword.UNSET],
    opacity: PropertyValue | Literal[StyleKeyword.UNSET],
    offset_x: PropertyValue | Literal[StyleKeyword.UNSET],
    offset_y: PropertyValue | Literal[StyleKeyword.UNSET],
) -> AnimatedProperties:
    properties: AnimatedProperties = {}
    if scale is not UNSET:
        properties["scale"] = scale
    if opacity is not UNSET:
        properties["opacity"] = opacity
    if offset_x is not UNSET:
        properties["offset_x"] = offset_x
    if offset_y is not UNSET:
        properties["offset_y"] = offset_y
    return properties


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
    )


def resolve_behaviors(
    prepared: PreparedLyrics, context, rules, *, ruby_follow, item_id
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
                    if r.mode == "ruby" or ruby_follow.allows(r.property)
                ]
            elif ruby_follow != "syllable":
                relevant = [r for r in relevant if r.mode == "ruby"]
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
                context.layout.units[ui].box if rule.mode == "syllable" else visual.box
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
                    bound.append(motion)
        check_motion_conflicts(bound, prepared.window, origin, f"{item_id}/{visual.id}")
        scales = [m for m in bound if m.property == "scale"]
        native = native_motions(scales, prepared.window.end_ms)
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
