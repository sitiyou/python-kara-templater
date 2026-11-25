"""Lower disjoint color strips to one GPU paint lookup per coverage plane."""

from array import array
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from math import ceil

from ..._karaoke_motion import _LyricShaderMotion
from ..._native_types import RasterImage
from ..._scene_tree import SceneLeaf
from ...scene import RectangleKeyframes, _ColorStripClip
from .motion import DrawSpan


@dataclass(frozen=True)
class ColorBand:
    # Each row contains top, bottom and the ordered x boundaries.
    keys: tuple[tuple[float, tuple[float, ...]], ...]
    orders: tuple[int, ...]


def band_key(leaf: SceneLeaf) -> str:
    clip = leaf.node.clip
    return clip.band if isinstance(clip, _ColorStripClip) else ""


def match_band(leaves: Sequence[SceneLeaf], orders: tuple[int, ...]) -> ColorBand | None:
    """Check that all animated clips partition the same band in local space."""
    if len(orders) < 2:
        return None
    first = leaves[orders[0]]
    clip = first.node.clip
    assert isinstance(clip, _ColorStripClip)
    details = {}
    for order in orders:
        leaf = leaves[order]
        other = leaf.node.clip
        assert isinstance(other, _ColorStripClip)
        if (not isinstance(other.deform, RectangleKeyframes) or other.space != "local"
                or leaf.parents != first.parents or leaf.start != first.start or leaf.end != first.end
                or leaf.node.time_origin != first.node.time_origin
                or (other.slope, other.pivot_y) != (clip.slope, clip.pivot_y)):
            return None
        details[order] = other.deform.keyframes
    reference = details[orders[0]]
    sample = next((i for i, (_, bounds) in enumerate(reference) if bounds[0] < bounds[2]), None)
    if sample is None or any(len(keys) != len(reference) for keys in details.values()):
        return None
    ordered = tuple(sorted(orders, key=lambda order: details[order][sample][1][0]))
    rows = []
    for row in zip(*(details[order] for order in ordered), strict=True):
        time, (left, top, _, bottom) = row[0]
        edges = [left]
        for t, (lo, y0, hi, y1) in row:
            if t != time or y0 != top or y1 != bottom or lo != edges[-1]:
                return None
            edges.append(hi)
        rows.append((time, (top, bottom, *edges)))
    return ColorBand(tuple(rows), ordered)


def visible_windows(
    keys: RectangleKeyframes, clock: float, fps: int, origin: int, count: int,
) -> Iterator[tuple[int, int]]:
    """Conservatively retain the frame ranges where a shader rectangle can have area."""
    # Use the same float32 frame clock as the serialized rectangle. Multiple
    # keys at one frame-clock value form a reset; the last key takes effect.
    times = array("f", ((clock + t) * fps - origin for t, _ in keys.keyframes))
    bounds = [rect for _, rect in keys.keyframes]
    entries = [(0, bounds[0]), *zip(times, bounds, strict=True), (count, bounds[-1])]
    pending_start, pending_stop = 0, 0
    for (t, a), (u, b) in pairwise(entries):
        start, stop = ceil(max(0, min(count, t))), ceil(max(0, min(count, u)))
        if start >= stop or (a[0] == a[2] and b[0] == b[2]) or (a[1] == a[3] and b[1] == b[3]):
            continue
        if pending_start == pending_stop:
            pending_start = start
        elif start > pending_stop:
            yield pending_start, pending_stop
            pending_start = start
        pending_stop = stop
    if pending_start < pending_stop:
        yield pending_start, pending_stop


def _same_masks(a: tuple[RasterImage, ...] | None, b: tuple[RasterImage, ...] | None) -> bool:
    if a is None or b is None:
        return a is b
    return len(a) == len(b) and all(
        i[:5] == j[:5] and i[6] == j[6] for i, j in zip(a, b, strict=True)
    )


def same_band_span(first: DrawSpan, other: DrawSpan) -> bool:
    """Prove common geometry and motion; RGB and layer opacity may differ."""
    a, b = first.draw, other.draw
    if (first.first_frame != other.first_frame or first.stop_frame != other.stop_frame
            or a.shader_paint is not None or b.shader_paint is not None
            or a.material_effects or b.material_effects
            or a.side_shading is not None or b.side_shading is not None
            or a.fixed_stroke != b.fixed_stroke or a.transform != b.transform
            or not _same_masks(a.mask_planes, b.mask_planes)
            or not _same_masks(first.alternate_masks, other.alternate_masks)):
        return False
    shader, other_shader = first.shader, other.shader
    if shader is not None and other_shader is not None and isinstance(shader.program, _LyricShaderMotion):
        base = replace(shader.base, opacity=other_shader.base.opacity,
                       fill=other_shader.base.fill, outline=other_shader.base.outline)
        if replace(shader, base=base) != other_shader:
            return False
        if first.alternate_masks is not None:
            return (round((1 - a.opacity * a.face_opacity) * 255) == 0) == (
                round((1 - b.opacity * b.face_opacity) * 255) == 0
            )
        return True
    if shader != other_shader:
        return False
    if (shader is not None or first.alternate_masks is not None) and (
        a.opacity != b.opacity or a.face_opacity != b.face_opacity
    ):
        return False
    x, y = first.motion, other.motion
    if x is None or y is None:
        return x is y
    if first.alternate_masks is not None and x.end_state.opacity != y.end_state.opacity:
        return False
    end = replace(
        x.end_state, opacity=y.end_state.opacity, fill=y.end_state.fill, outline=y.end_state.outline,
    )
    return replace(x, end_state=end) == y
