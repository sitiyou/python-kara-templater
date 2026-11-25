"""Resolve the shared Scene into owner-specific GPU draws, without ASS banding.

This first adapter supports ordinary text/static paths, affine state, normal
rectangle clips and LinearGradient. Unsupported composition fails explicitly.
It does not serialize author callbacks or invent a second animation evaluator.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from math import log, sqrt

from ..._contour_stroke import ContourStroke, contour_grid
from ..._native_types import RasterImage
from ..._path_raster import STROKE_FACE, cutout_border, path_coverage
from ..._scene_tree import SceneLeaf, scene_leaves
from ...composition import Color
from ...geometry import Affine2D, Vec2, VectorPath, finite
from ...lyrics.materials import _solid_glow
from ...paint_fields import LinearGradient, MaterialClip, ShaderPaint
from ...scene import (
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneCompileError,
    TextObject,
    _LyricPaintClip,
)
from ...scene_animation import VisualState, local_seconds
from ...text_geometry import outline_text


@dataclass(frozen=True)
class GpuClip:
    bounds: tuple[float, float, float, float]
    local: bool = False

    def __post_init__(self) -> None:
        finite(*self.bounds)
        left, top, right, bottom = self.bounds
        if left > right or top > bottom:
            raise ValueError("GPU clip bounds cannot be inverted")


def _clip_at(rectangle: RectangleClip, time: float) -> GpuClip | None:
    bounds = (rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)
    if rectangle.deform is not None:
        sampled = rectangle.deform.sample(time)
        if sampled is None:
            return None
        bounds = sampled
    return GpuClip(bounds, local=rectangle.space == "local")


@dataclass(frozen=True)
class DrawCommand:
    object_id: str
    mask_planes: tuple[RasterImage, ...]
    transform: Affine2D
    opacity: float
    gradient: LinearGradient | None
    clip: GpuClip | None
    shader_paint: ShaderPaint | None = None
    time_origin: float = 0
    border: float = 0
    side_shading: tuple[bytes, Color] | None = None
    inherited_clips: tuple[GpuClip, ...] = ()
    fixed_stroke: FixedStroke | None = None
    face_opacity: float = 1
    material_effects: tuple[MaterialClip, ...] = ()
    time_end: float = 0
    solid_backing: bool = False


@dataclass(frozen=True)
class FixedStroke:
    grid: tuple[float, ...]
    face: RasterImage
    sigma: float
    filled: bool
    shadow: Vec2
    solid_backing: bool = False


def _isometry(transform: Affine2D) -> bool:
    a, b, c, d = transform.a, transform.b, transform.c, transform.d
    return max(abs(a * a + b * b - 1), abs(c * c + d * d - 1), abs(a * c + b * d)) < 1e-9


class _ExtrusionSide(SceneLeaf):
    """A second paint pass sharing the face's scene identity and animation clock."""


def _shape_key(leaf: SceneLeaf, state: VisualState) -> tuple[object, ...]:
    node = leaf.node
    shape = (
        (
            node.text,
            node.font,
            node.font_size,
            node.bold,
            node.italic,
            node.spacing,
            node.alignment,
            node.encoding,
        )
        if isinstance(node, TextObject)
        else (node.path,)
    )
    if isinstance(leaf, _ExtrusionSide):
        assert node.extrusion is not None
        return ("extrusion", *shape, node.filled, state.border, state.blur, node.extrusion.offset,
                node.extrusion.back_color is not None)
    if isinstance(node.shader_paint, ContourStroke):
        return ("stroke", node.shader_paint.bounds)
    if _solid_glow(node.material_effects):
        return ("solid glow", *shape, state.border, state.blur)
    return (*shape, node.filled, state.border, state.blur, state.shadow, cutout_border(state, node.filled))


type _CachedCoverage = tuple[tuple[RasterImage, ...], tuple[float, ...] | None]


def _coverage(
    leaf: SceneLeaf, state: VisualState, pixel_budget: int, screen_space_stroke: bool
) -> _CachedCoverage:
    node = leaf.node
    if isinstance(node.shader_paint, ContourStroke):
        # Coverage is evaluated from geometry by the fragment shader.
        return ((*node.shader_paint.bounds, 1, 0, b""),), None
    path = (
        outline_text(node, max_points=200_000).path
        if isinstance(node, TextObject)
        else node.path
    )
    if path is None:
        return (), None
    if screen_space_stroke and any(not contour.closed for contour in path.contours):
        # ASS and the raster mask close drawing contours before stroking.
        path = VectorPath(tuple(replace(contour, closed=True) for contour in path.contours))
    offset = node.extrusion.offset if isinstance(leaf, _ExtrusionSide) and node.extrusion else None
    images = path_coverage(
        path, state, node.filled, pixel_budget, node.id, sweep=offset,
        shaded=bool(node.extrusion and node.extrusion.back_color is not None),
        keep_face=screen_space_stroke,
        solid_backing=_solid_glow(node.material_effects),
    )
    return images, contour_grid(path, 1)[1] if screen_space_stroke else None


class HookDrawResolver:
    """Seekable draws using SceneEvaluator and bounded, reusable native coverage."""

    def __init__(self, scene: Scene, *, cache_bytes: int = 64 * 1024 * 1024) -> None:
        if type(cache_bytes) is not int or cache_bytes < 1:
            raise ValueError("GPU scene cache budget must be a positive integer")
        self._evaluator = scene.evaluator()
        # Hook export traverses simultaneous leaves from the same group.
        # Reuse their world poses within this immutable snapshot only.
        self._states: dict[tuple[str, float], VisualState] = {}
        leaves, native, _ = scene_leaves(scene, self._evaluator)
        if native:
            event = native[0]
            raise SceneCompileError(
                f"hook cannot compile native events at {event.event.start_time / 1000:g}s",
                object_id=event.id, origin=event.origin,
            )
        group_clips: dict[str, tuple[tuple[ObjectGroup, RectangleClip], ...]] = {}
        for leaf in leaves:
            node = leaf.node
            reason = None
            if isinstance(node, PathObject) and node.deform is not None:
                reason = "deformed paths"
            elif node.clip is not None and (
                not isinstance(node.clip, RectangleClip) or node.clip.inverse
            ):
                reason = "vector/inverse clips"
            if isinstance(node.material, LinearGradient) and any(
                ramp is not None and len(ramp.stops) > 16
                for ramp in (node.material.fill, node.material.outline)
            ):
                reason = "gradients with more than 16 stops"
            if reason:
                raise SceneCompileError(
                    f"hook cannot compile {reason} at {leaf.start:g}s",
                    object_id=node.id, origin=node.origin,
                )
            inherited: list[tuple[ObjectGroup, RectangleClip]] = []
            for parent in leaf.parents:
                clip = parent.clip
                if clip is None:
                    continue
                if (
                    not isinstance(clip, RectangleClip)
                    or clip.inverse
                    or clip.space != "screen"
                    or (
                        clip.deform is not None
                        and not isinstance(clip.deform, RectangleKeyframes)
                    )
                ):
                    raise SceneCompileError(
                        "hook requires a normal screen rectangle with optional "
                        f"keyframes for inherited clips at {leaf.start:g}s",
                        object_id=parent.id,
                        origin=parent.origin,
                    )
                inherited.append((parent, clip))
            if inherited:
                group_clips[node.id] = tuple(inherited)
        self.group_clips = group_clips
        passes = list(leaves)
        for leaf in leaves:
            node = leaf.node
            if node.extrusion is None or node.extrusion.offset == Vec2():
                continue
            # Only a timing-color partition is face-specific. User clip masks
            # still cut the entire extruded object.
            side = replace(node, material=None, shader_paint=None, material_effects=(),
                           clip=None if isinstance(node.clip, _LyricPaintClip) else node.clip)
            passes.append(_ExtrusionSide(side, leaf.parents, leaf.start, leaf.end, leaf.evaluator))
        self.leaves = tuple(sorted(passes, key=lambda leaf: (
            leaf.node.layer + sum(p.layer for p in leaf.parents),
            0 if isinstance(leaf, _ExtrusionSide) else 1,
        )))
        self._cache: OrderedDict[tuple[object, ...], _CachedCoverage] = (
            OrderedDict()
        )
        self._bytes = 0
        self._limit = cache_bytes
        self.resolution = (scene.document.meta.res_x, scene.document.meta.res_y)
        self.end = max((leaf.end for leaf in leaves), default=0.0)

    @property
    def cached_bytes(self) -> int:
        return self._bytes

    def at(self, time: float) -> tuple[DrawCommand, ...]:
        finite(time)
        result = []
        for leaf in self.leaves:
            if not leaf.start <= time < leaf.end:
                continue
            draw = self.draw_at(leaf, time)
            if draw is not None:
                result.append(draw)
        return tuple(result)

    def draw_at(self, leaf: SceneLeaf, time: float) -> DrawCommand | None:
        if len(self._states) >= 4096:
            self._states.clear()
        state = self._evaluator._at(leaf.node.id, time, self._states)
        if state.opacity == 0 or state.singular:
            return None
        node = leaf.node
        clip = None
        if isinstance(node.clip, RectangleClip):
            clip = _clip_at(node.clip, local_seconds(time, node.time_origin))
            if clip is None:
                return None
        inherited = []
        for owner, rectangle in self.group_clips.get(node.id, ()):
            screen_clip = _clip_at(rectangle, local_seconds(time, owner.time_origin))
            if screen_clip is None:
                return None
            inherited.append(screen_clip)
        draw = self.draw_state(leaf, state, clip)
        return replace(draw, inherited_clips=tuple(inherited)) if inherited else draw

    def draw_state(
        self, leaf: SceneLeaf, state: VisualState, clip: GpuClip | None, *,
        varying_basis: bool = False,
    ) -> DrawCommand:
        node = leaf.node
        solid_backing = _solid_glow(node.material_effects)
        screen_space_stroke = (
            state.border > 0
            and not node.scale_border
            and not isinstance(leaf, _ExtrusionSide)
            and not isinstance(node.shader_paint, ContourStroke)
            and (varying_basis or not _isometry(state.transform))
        )
        key = (*_shape_key(leaf, state), screen_space_stroke)
        cached = self._cache.get(key)
        if cached is None:
            cached = _coverage(leaf, state, self._limit, screen_space_stroke)
            images, grid = cached
            size = sum(len(image[6]) for image in images) + (8 * len(grid) if grid else 0)
            if size > self._limit:
                raise SceneCompileError(
                    "GPU glyph coverage exceeds cache budget", object_id=node.id
                )
            while self._bytes + size > self._limit:
                _, (old, old_grid) = self._cache.popitem(last=False)
                self._bytes -= sum(len(image[6]) for image in old) + (8 * len(old_grid) if old_grid else 0)
            self._cache[key] = cached
            self._bytes += size
        self._cache.move_to_end(key)
        images, grid = cached
        tinted = []
        shading = None
        stroke = None
        for x, y, w, h, kind, color, data in images:
            if kind == STROKE_FACE:
                assert grid is not None
                stroke = FixedStroke(
                    grid, (x, y, w, h, kind, color, data), state.blur * 2 / sqrt(log(256)),
                    node.filled,
                    Vec2(round(state.shadow.x), round(state.shadow.y)),
                    solid_backing,
                )
                continue
            if kind == 4:
                assert node.extrusion is not None and node.extrusion.back_color is not None
                shading = (data, node.extrusion.back_color)
                continue
            if kind == 2:
                if not state.shadow_opacity:
                    continue
                color = round((1 - state.shadow_opacity) * 255)
            elif kind in (0, 1):
                color = round((1 - state.face_opacity) * 255)
            rgb = (
                state.fill
                if kind == 0
                else state.outline
                if kind == 1
                else node.extrusion.color if kind == 3 and node.extrusion is not None
                else Color(0, 0, 0)
            )
            color = rgb.red << 24 | rgb.green << 16 | rgb.blue << 8 | (color & 255)
            tinted.append((x, y, w, h, kind, color, data))
        material = node.material
        return DrawCommand(
            node.id, tuple(tinted), state.transform, state.opacity, material, clip,
            node.shader_paint, node.time_origin, state.border, shading, fixed_stroke=stroke,
            face_opacity=state.face_opacity, material_effects=node.material_effects,
            time_end=node.lifetime.end, solid_backing=solid_backing,
        )
