"""Lower continuous known group alpha after pixels have been composited once."""

import re
from collections.abc import Sequence
from itertools import pairwise
from math import floor

from .ass_output import quantize
from .behaviors import BoundProperty
from .lowering import native_motions
from .timeline import DisplayWindow


def _value(motions: Sequence[BoundProperty], time: int, *, left: bool) -> float:
    for motion in motions:
        assert motion.points is not None
        points = tuple((quantize(t), value) for t, value in motion.points)
        start, end = points[0][0], points[-1][0]
        if time < start or (left and time == start):
            continue
        if time > end or (time == end and not left) or start == end:
            if motion.keep:
                return points[-1][1]
            continue
        for (a, av), (b, bv) in pairwise(points):
            if a <= time <= b and a < b:
                return av + (bv - av) * (time - a) / (b - a)
    return 1.0


def opacity_curve(
    groups: tuple[tuple[BoundProperty, ...], ...],
    window: DisplayWindow,
) -> tuple[tuple[int, float], ...] | None:
    converted = tuple(native_motions(group, window.end_ms) for group in groups)
    if not converted or any(group is None for group in converted):
        return None
    first = converted[0]
    assert first is not None
    signature = tuple((motion.interval, motion.points, motion.keep) for motion in first)
    if any(
        tuple((motion.interval, motion.points, motion.keep) for motion in group)
        != signature
        for group in converted
        if group is not None
    ):
        return None
    start, end = quantize(window.start_ms), quantize(window.end_ms)
    knots = sorted(
        {
            start,
            end,
            *(
                quantize(t)
                for motion in first
                for t, _ in (motion.points or ())
                if start < quantize(t) < end
            ),
        }
    )
    if any(
        _value(first, time, left=True) != _value(first, time, left=False)
        for time in knots[1:-1]
    ):
        return None
    return tuple((time, _value(first, time, left=time == end)) for time in knots)


def apply_opacity(
    text: str, start_ms: int, curve: tuple[tuple[int, float], ...]
) -> str:
    original = re.search(r"\\alpha&H([0-9A-F]{2})&", text)
    if original is None:
        raise ValueError("raster event has no encoded alpha")
    coverage = 255 - int(original[1], 16)

    def alpha(value: float) -> str:
        # Match RasterCanvas rounding: quantize coverage before inverting alpha.
        return f"&H{255 - floor(coverage * value + 0.5):02X}&"

    initial = curve[0][1]
    transforms = ""
    for (start, before), (end, after) in pairwise(curve):
        if end <= start_ms:
            # Discard completed segments. Besides saving bytes, this avoids
            # ASS interpreting a relative t2=0 as the new event's duration.
            initial = after
        elif before != after:
            transforms += (
                rf"\t({start - start_ms},{end - start_ms},1,\alpha{alpha(after)})"
            )
    tags = rf"\alpha{alpha(initial)}" + transforms
    return text[: original.start()] + tags + text[original.end() :]
