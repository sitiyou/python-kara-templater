"""Piecewise-linear coverage arrangement for native ASS clip output."""

from dataclasses import dataclass
from itertools import pairwise

from .ass_output import ClipSpan, OutputCapabilityError, sweep_spans
from .composition import Paint
from .timeline import DisplayWindow, EdgeSweep, HighlightTrack, Region


@dataclass(frozen=True)
class PaintedMask:
    track_id: str
    paint: Paint
    priority: int
    spans: tuple[ClipSpan, ...]


@dataclass(frozen=True)
class ComposedMask:
    paints: tuple[Paint, ...]
    span: ClipSpan
    interpolation_span: ClipSpan | None = None
    # Adjacent strips have different visible decoration stacks. Native ASS
    # clips each already-painted stack; it cannot blur their recolored union.
    hard_decoration_boundary: bool = False
    shared_local_clock: bool = False


def _decorations(paints):
    result = []
    for paint in paints:
        if paint.opacity == 0:
            continue
        if paint.border > 0:
            result.append(("outline", paint.outline, paint.border, paint.opacity))
        if paint.glow is not None and paint.glow.opacity > 0:
            result.append(("glow", paint.glow, paint.opacity))
    return tuple(result)


def _interpolation_span(left, right, motions):
    """Keep source integer endpoints when both edges share a native clock.

    The exposure remains the arrangement span. Incompatible moving clocks or
    reversed extrapolated rectangles retain the local approximation.
    """
    moving_left, moving_right = left[0] != left[1], right[0] != right[1]
    if not moving_left and not moving_right:
        return None
    primary = left if moving_left else right
    for start, end, x0, x1 in motions[primary]:
        if moving_left:
            l0, l1 = x0, x1
        else:
            l0 = l1 = left[0]
        if moving_right:
            matching = next((m for m in motions[right] if m[:2] == (start, end)), None)
            if matching is None:
                continue
            r0, r1 = matching[2:]
        else:
            r0 = r1 = right[0]
        if l0 <= r0 and l1 <= r1:
            return ClipSpan(start, end, Region(l0, r0), Region(l1, r1))
    return None


def track_spans(
    track: HighlightTrack,
    *,
    body: Region,
    paint: Region,
    window: DisplayWindow,
    edges: EdgeSweep,
) -> tuple[ClipSpan, ...]:
    """Keep completed partitions, or release them on explicit reset/exit.

    Only outer body boundaries gain decorative margins. Internal partitions
    retain their original boundaries and cannot mark neighbouring text sung.
    """
    result = []
    for singing in track.passes:
        end = window.end_ms
        if track.end_behavior == "hide":
            end = min(end, track.passes[-1].end_ms)
        if track.repeat == "reset":
            end = min(
                end,
                next(
                    (p.start_ms for p in track.passes if p.round_id > singing.round_id),
                    end,
                ),
            )
        if end <= window.start_ms:
            continue
        left = (
            min(paint.left - edges.padding_px, singing.region.left)
            if singing.region.left <= body.left
            else singing.region.left
        )
        right = (
            max(paint.right + edges.padding_px, singing.region.right)
            if singing.region.right >= body.right
            else singing.region.right
        )
        local_edges = EdgeSweep(
            lead_ms=edges.lead_ms if left < singing.region.left else 0,
            tail_ms=edges.tail_ms if right > singing.region.right else 0,
        )
        spans = sweep_spans(
            singing, paint=Region(left, right), window=window, edges=local_edges
        )
        for span in spans:
            stop = min(span.end_ms, end)
            start = max(span.start_ms, window.start_ms)
            if stop > start:
                result.append(ClipSpan(start, stop, span.at(start), span.at(stop)))
    return tuple(result)


def _selected(active, before, overlap):
    # Multiple partitions from one track are a union, not multiple exposures.
    active = {mask.track_id: mask for mask in active}.values()
    if not active:
        return (before,)
    if overlap == "union":
        paints = {m.paint for m in active}
        if len(paints) != 1:
            raise OutputCapabilityError("union overlaps require identical appearances")
        return (next(iter(paints)),)
    if overlap == "priority":
        top = max(m.priority for m in active)
        paints = {m.paint for m in active if m.priority == top}
        if len(paints) != 1:
            raise OutputCapabilityError(
                "conflicting equal-priority highlight appearances"
            )
        return (next(iter(paints)),)
    ordered = sorted(active, key=lambda m: m.priority)
    if len({m.priority for m in ordered}) != len(ordered):
        raise OutputCapabilityError("layer overlaps require distinct priorities")
    return (before, *(m.paint for m in ordered))


def compose_masks(
    masks: tuple[PaintedMask, ...],
    *,
    domain: Region,
    window: DisplayWindow,
    before: Paint,
    overlap: str,
    max_regions: int = 10000,
) -> tuple[ComposedMask, ...]:
    """Partition time at front crossings, then space into nonoverlapping strips.

    Every resulting boundary is linear. No frame sampling is needed to resolve
    parallel sweeps, priorities, pauses, exits or repeated regions.
    """
    if overlap not in {"union", "priority", "layer"}:
        raise ValueError("overlap must be union, priority or layer")
    if len({m.track_id for m in masks}) != len(masks):
        raise ValueError("duplicate mask track ids")
    times = {window.start_ms, window.end_ms}
    for mask in masks:
        for span in mask.spans:
            times.update(
                t
                for t in (span.start_ms, span.end_ms)
                if window.start_ms < t < window.end_ms
            )
    result = []
    stationary = {}
    for start, end in pairwise(sorted(times)):
        active = [
            (mask, span)
            for mask in masks
            for span in mask.spans
            if span.start_ms <= start and span.end_ms >= end
        ]
        # Edges represented by their values at this interval's endpoints.
        edges = {(domain.left, domain.left), (domain.right, domain.right)}
        motions = {}
        for _, span in active:
            a, b = span.at(start), span.at(end)
            edges.update(((a.left, b.left), (a.right, b.right)))
            for side in ("left", "right"):
                edge = (getattr(a, side), getattr(b, side))
                motions.setdefault(edge, []).append(
                    (
                        span.start_ms,
                        span.end_ms,
                        getattr(span.start, side),
                        getattr(span.end, side),
                    )
                )
        edges = sorted(edges)
        cuts = {0.0, 1.0}
        for i, (a0, a1) in enumerate(edges):
            for b0, b1 in edges[i + 1 :]:
                denominator = (a1 - a0) - (b1 - b0)
                if denominator:
                    crossing = (b0 - a0) / denominator
                    if 0 < crossing < 1:
                        cuts.add(crossing)

        def at(edge, t):
            return edge[0] + (edge[1] - edge[0]) * t

        for p0, p1 in pairwise(sorted(cuts)):
            middle = (p0 + p1) / 2
            ordered = sorted(edges, key=lambda edge: at(edge, middle))
            strips = []
            for left, right in pairwise(ordered):
                x0, x1 = at(left, middle), at(right, middle)
                if (
                    x0 < domain.left - 1e-8
                    or x1 > domain.right + 1e-8
                    or x1 - x0 < 1e-8
                ):
                    continue
                x = (x0 + x1) / 2
                time = start + (end - start) * middle
                chosen = [
                    mask
                    for mask, span in active
                    if span.at(time).left <= x < span.at(time).right
                ]
                paints = _selected(chosen, before, overlap)
                if strips and strips[-1][2] == paints:
                    strips[-1] = (strips[-1][0], right, paints)
                else:
                    strips.append((left, right, paints))
            hard_edges = set()
            for index, (first, second) in enumerate(pairwise(strips)):
                if _decorations(first[2]) != _decorations(second[2]):
                    hard_edges.update((index, index + 1))
            anchors = [
                _interpolation_span(left, right, motions) for left, right, _ in strips
            ]
            # A rectangular transform has one clock for both edges. If a
            # middle strip cannot retain both source clocks, all neighboring
            # strips must use this same arrangement clock: otherwise the same
            # geometric edge rounds/interpolates differently on its two sides.
            local_clock = any(
                anchor is None and (left[0] != left[1] or right[0] != right[1])
                for (left, right, _), anchor in zip(strips, anchors, strict=True)
            )
            for index, (first, _second) in enumerate(pairwise(strips)):
                if first[1][0] == first[1][1]:
                    continue
                a, b = anchors[index : index + 2]
                if (
                    a is None
                    or b is None
                    or (a.start_ms, a.end_ms, a.start.right, a.end.right)
                    != (b.start_ms, b.end_ms, b.start.left, b.end.left)
                ):
                    local_clock = True
            for index, (left, right, paints) in enumerate(strips):
                hard_boundary = index in hard_edges
                span = ClipSpan(
                    start + (end - start) * p0,
                    start + (end - start) * p1,
                    Region(at(left, p0), max(at(left, p0), at(right, p0))),
                    Region(at(left, p1), max(at(left, p1), at(right, p1))),
                )
                # Arrangement boundaries can be irrelevant to an already fully
                # sung/unsung glyph. Retain one continuous stationary exposure;
                # the output compiler still splits at fade/animation knots.
                key = (
                    (paints, span.start, hard_boundary, local_clock)
                    if span.start == span.end
                    else None
                )
                previous_index = stationary.get(key) if key is not None else None
                if previous_index is not None:
                    previous = result[previous_index]
                    if previous.span.end_ms == span.start_ms:
                        result[previous_index] = ComposedMask(
                            paints,
                            ClipSpan(
                                previous.span.start_ms,
                                span.end_ms,
                                span.start,
                                span.end,
                            ),
                            hard_decoration_boundary=hard_boundary,
                            shared_local_clock=local_clock,
                        )
                        continue
                if len(result) >= max_regions:
                    raise OutputCapabilityError(
                        f"mask arrangement exceeds {max_regions} regions"
                    )
                if key is not None:
                    stationary[key] = len(result)
                result.append(
                    ComposedMask(
                        paints,
                        span,
                        None if local_clock else anchors[index],
                        hard_boundary,
                        local_clock,
                    )
                )
    return tuple(result)
