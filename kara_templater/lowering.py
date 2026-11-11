"""Select native properties where known curves can be represented accurately."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from itertools import pairwise
from math import prod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .behaviors import BoundProperty

from .animation import OffsetAnimation, OpacityAnimation
from .ass_output import TextLayer, native_opacity_supported, quantize


def _points(motion: BoundProperty) -> tuple[tuple[float, float], ...]:
    assert motion.points is not None
    return motion.points


def _point_value(points, time):
    if time >= points[-1][0]:
        return points[-1][1]
    for (a, av), (b, bv) in pairwise(points):
        if a <= time < b:
            return av + (bv - av) * (time - a) / (b - a)
    raise ValueError("time precedes known curve")


def native_motions(
    motions: Sequence[BoundProperty], window_end: int
) -> tuple[BoundProperty, ...] | None:
    """Return disjoint known linear rules, or None when sampling is needed."""
    if any(m.points is None for m in motions):
        return None
    if any(
        m.interval[0] != m.interval[1]
        and any(quantize(a[0]) >= quantize(b[0]) for a, b in pairwise(_points(m)))
        for m in motions
    ):
        return None
    if all(m.compose == "replace" for m in motions):
        return tuple(motions)
    # Split at every activation, release and slope change. Determine the active
    # rules inside each interval, then evaluate both one-sided endpoints from
    # their known points. Never call author functions during native lowering.
    knots = sorted({window_end, *(t for m in motions for t, _ in _points(m))})
    if any(quantize(a) >= quantize(b) for a, b in pairwise(knots)):
        return None
    result = []
    for start, end in pairwise(knots):
        active = [
            m
            for m in motions
            if m.interval[0] <= start and (start < m.interval[1] or m.keep)
        ]
        if not active:
            continue
        if active[-1].compose == "override":
            active = active[-1:]
        elif active[0].compose not in {"add", "multiply"}:
            active = active[:1]
        endpoints = [
            (_point_value(_points(m), start), _point_value(_points(m), end))
            for m in active
        ]
        multiply = active[0].compose == "multiply"
        if multiply:
            # A product of linear factors is linear only when at most one
            # factor varies, unless a constant zero makes the whole product zero.
            zero = any(a == b == 0 for a, b in endpoints)
            if not zero and sum(a != b for a, b in endpoints) > 1:
                return None
        combine = prod if multiply else sum
        result.append(
            replace(
                active[0],
                interval=(start, end),
                points=tuple(
                    (t, combine(values[i] for values in endpoints))
                    for i, t in enumerate((start, end))
                ),
                keep=False,
                compose="replace",
            )
        )
    return tuple(result)


def lower_offsets(
    layers: tuple[TextLayer, ...], property_targets
) -> tuple[TextLayer, ...]:
    window_ends = {}
    for layer in layers:
        identity = layer.animation_id or layer.source_id
        window_ends[identity] = max(
            window_ends.get(identity, layer.window.end_ms), layer.window.end_ms
        )
    native = {}
    for identity, motions in tuple(property_targets.items()):
        converted, animations = set(), []
        for name, axis in (("offset_x", "x"), ("offset_y", "y")):
            selected = tuple(m for m in motions if m.property == name)
            if not selected:
                continue
            composed = native_motions(selected, window_ends[identity])
            if composed is None:
                continue
            converted.add(name)
            animations.extend(
                OffsetAnimation(_points(m), axis, m.keep) for m in composed
            )
        if converted:
            native[identity] = tuple(animations)
            remaining = tuple(m for m in motions if m.property not in converted)
            if remaining:
                property_targets[identity] = remaining
            else:
                property_targets.pop(identity)
    return tuple(
        (
            replace(l, offsets=native[l.animation_id or l.source_id])
            if (l.animation_id or l.source_id) in native
            else l
        )
        for l in layers
    )


def lower_opacity(
    layers: tuple[TextLayer, ...], property_targets, glow_targets
) -> tuple[TextLayer, ...]:
    grouped = {}
    for layer in layers:
        grouped.setdefault(layer.animation_id or layer.source_id, []).append(layer)
    native = {}
    for identity, targets in grouped.items():
        group = tuple(
            m for m in property_targets.get(identity, ()) if m.property == "opacity"
        )
        glow = tuple(
            m
            for m in glow_targets.get(identity, ((), None))[0]
            if m.property == "opacity"
        )
        channels = []
        for component, motions in (("group", group), ("glow", glow)):
            composed = native_motions(motions, max(t.window.end_ms for t in targets))
            if motions and composed is not None:
                channels.append(
                    (
                        component,
                        tuple(
                            OpacityAnimation(_points(m), m.keep, component)
                            for m in composed
                        ),
                    )
                )
        if not channels:
            continue
        candidates = tuple(a for _, animations in channels for a in animations)
        if not all(
            native_opacity_supported(replace(t, opacity_animations=candidates))
            for t in targets
        ):
            # Leave the combined expression on its existing sampling path.
            continue
        native[identity] = candidates
        if any(c == "group" for c, _ in channels):
            remaining = tuple(
                m for m in property_targets[identity] if m.property != "opacity"
            )
            if remaining:
                property_targets[identity] = remaining
            else:
                property_targets.pop(identity)
        if any(c == "glow" for c, _ in channels):
            remaining = tuple(
                m for m in glow_targets[identity][0] if m.property != "opacity"
            )
            if remaining:
                glow_targets[identity] = (remaining, None)
            else:
                glow_targets.pop(identity)
    return tuple(
        (
            replace(l, opacity_animations=native[l.animation_id or l.source_id])
            if (l.animation_id or l.source_id) in native
            else l
        )
        for l in layers
    )
