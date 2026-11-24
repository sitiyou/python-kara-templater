"""Recognize adjacent, complementary lyric draws that can share GPU coverage."""

from dataclasses import dataclass, replace

from ..._scene_tree import SceneLeaf
from ...lyrics.highlights import _FeatheredWipeClip
from ...paint_fields import LinearGradient
from ...scene import RectangleKeyframes, _LyricPaintClip
from ...scene_animation import VisualState
from .motion import _curve


@dataclass(frozen=True)
class Wipe:
    before: VisualState
    gradient: LinearGradient | None
    # Index of the moving side in (left, top, right, bottom) of the after clip.
    edge: int


def match_wipe(before: SceneLeaf, after: SceneLeaf) -> Wipe | None:
    first, second = before.node, after.node
    a, b = first.clip, second.clip
    if not isinstance(a, _LyricPaintClip) or not isinstance(b, (_LyricPaintClip, _FeatheredWipeClip)):
        return None
    if (a.space != "local" or b.space != "local"
            or not isinstance(a.deform, RectangleKeyframes) or not isinstance(b.deform, RectangleKeyframes)
            or len(a.deform.keyframes) != len(b.deform.keyframes)):
        return None
    # Keep painter order and every property affecting the mask or its motion.
    # A custom motion can depend on the incoming color even when it only writes geometry.
    if (before.parents != after.parents or first.shader_paint or first.extrusion or second.extrusion
            or before.evaluator.referenced(first.id) or after.evaluator.referenced(second.id)
            or any(_curve(c) is None for c in first.animations)):
        return None
    state = replace(first.state, fill=second.state.fill, outline=second.state.outline)
    if replace(first, id=second.id, state=state, material=second.material, clip=b) != second:
        return None
    if isinstance(b, _FeatheredWipeClip) and (
        b.before_fill != first.state.fill or b.before_outline != first.state.outline
        or b.before_gradient != first.material
    ):
        return None
    assert first.material is None or isinstance(first.material, LinearGradient)
    # Only collapse a true partition. Other effects can narrow these clips
    # (e.g. a scanline) or insert additional draws between the two sides.
    full = (-65536., -65536., 65536., 65536.)
    for edge in range(4):
        opposite = (edge + 2) % 4
        if all(t == u and left[opposite] == right[edge]
               and all(left[i] == full[i] for i in range(4) if i != opposite)
               and all(right[i] == full[i] for i in range(4) if i != edge)
               for (t, left), (u, right) in zip(a.deform.keyframes, b.deform.keyframes, strict=True)):
            return Wipe(first.state, first.material, edge)
    return None
