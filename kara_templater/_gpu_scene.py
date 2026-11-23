"""Resolve the shared Scene into owner-specific GPU draws, without ASS banding.

This first adapter supports ordinary text/static paths, affine state, normal
rectangle clips and LinearGradient. Unsupported composition fails explicitly.
It does not serialize author callbacks or invent a second animation evaluator.
"""

from collections import OrderedDict
from dataclasses import dataclass
from math import ceil, floor, log, sqrt

import aggdraw  # ty: ignore[import-not-found]  # Extension module without a type stub.
from PIL import Image, ImageChops, ImageFilter

from ._native_types import RasterImage
from .composition import Color
from .geometry import Affine2D, CubicSegment, VectorPath, finite
from .paint_fields import LinearGradient
from .path_geometry import path_bounds
from .scene import PathObject, RectangleClip, Scene, TextObject
from .scene_animation import VisualState, local_seconds
from .scene_output import SceneCompileError, _Leaf, _leaves
from .text_geometry import outline_text


@dataclass(frozen=True)
class GpuClip:
    bounds: tuple[float, float, float, float]
    local: bool = False

    def __post_init__(self) -> None:
        finite(*self.bounds)
        left, top, right, bottom = self.bounds
        if left > right or top > bottom:
            raise ValueError("GPU clip bounds cannot be inverted")


@dataclass(frozen=True)
class DrawCommand:
    object_id: str
    images: tuple[RasterImage, ...]
    transform: Affine2D
    opacity: float
    gradient: LinearGradient | None
    clip: GpuClip | None


def _shape_key(node: TextObject | PathObject, state: VisualState) -> tuple[object, ...]:
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
    return (*shape, node.filled, state.border, state.blur, state.shadow, _cutout_border(node, state))


def _cutout_border(node: TextObject | PathObject, state: VisualState) -> bool:
    # libass removes fill coverage from the border when either karaoke fill
    # color is translucent. Fully opaque text uses a solid backing instead.
    return node.filled and state.border > 0 and round((1 - state.opacity) * 255) != 0


def _coverage(
    leaf: _Leaf, state: VisualState, pixel_budget: int
) -> tuple[RasterImage, ...]:
    node = leaf.node
    path = (
        outline_text(node, max_points=200_000).path
        if isinstance(node, TextObject)
        else node.path
    )
    if path is None:
        return ()
    return path_coverage(path, state, node.filled, pixel_budget, node.id)


def path_coverage(
    path: VectorPath, state: VisualState, filled: bool, pixel_budget: int, object_id: str,
) -> tuple[RasterImage, ...]:
    bounds = path_bounds(path)
    if not 0 <= state.blur <= 100:
        raise ValueError("Blur radius must be in 0..100 ASS pixels")
    sigma = state.blur * 2 / sqrt(log(256))
    padding = ceil(state.border + 4 * sigma) + 2
    left, top = floor(bounds.left) - padding, floor(bounds.top) - padding
    width = ceil(bounds.right) + padding - left
    height = ceil(bounds.top + bounds.height) + padding - top
    if width * height > pixel_budget:
        raise SceneCompileError("GPU glyph raster pixel budget exceeded", object_id=object_id)

    drawing = aggdraw.Path()
    for contour in path.contours:
        drawing.moveto(contour.start.x - left, contour.start.y - top)
        for segment in contour.segments:
            if isinstance(segment, CubicSegment):
                drawing.curveto(
                    segment.control1.x - left, segment.control1.y - top,
                    segment.control2.x - left, segment.control2.y - top,
                    segment.end.x - left, segment.end.y - top,
                )
            else:
                drawing.lineto(segment.end.x - left, segment.end.y - top)
        drawing.close()

    def mask(border: float) -> Image.Image:
        plane = Image.new("L", (width, height))
        canvas = aggdraw.Draw(plane)
        pen = aggdraw.Pen("white", 2 * border) if border else None
        canvas.path(drawing, aggdraw.Brush("white"), pen)
        canvas.flush()
        return plane

    fill = mask(0)
    backing = mask(state.border) if state.border else fill
    border_mask = backing
    if state.border and (round((1 - state.opacity) * 255) != 0 or not filled):
        border_mask = ImageChops.subtract(backing, fill)

    images: list[RasterImage] = []

    def append(plane: Image.Image, kind: int, blur: bool, dx: int = 0, dy: int = 0) -> None:
        if sigma and blur:
            plane = plane.filter(ImageFilter.GaussianBlur(sigma))
        box = plane.getbbox()
        if box is not None:
            ink = plane.crop(box)
            images.append((left + box[0] + dx, top + box[1] + dy, ink.width, ink.height,
                           kind, 0xffffff00, ink.tobytes()))

    if (state.shadow.x or state.shadow.y) and (filled or state.border):
        append(backing if filled else border_mask, 2, True, round(state.shadow.x), round(state.shadow.y))
    if state.border:
        append(border_mask, 1, True)
    if filled:
        append(fill, 0, not state.border)
    return tuple(images)


class SceneFrames:
    """Seekable draws using SceneEvaluator and bounded, reusable native coverage."""

    def __init__(self, scene: Scene, *, cache_bytes: int = 64 * 1024 * 1024) -> None:
        if type(cache_bytes) is not int or cache_bytes < 1:
            raise ValueError("GPU scene cache budget must be a positive integer")
        self._evaluator = scene.evaluator()
        # Hook export traverses simultaneous leaves from the same group.
        # Reuse their world poses within this immutable snapshot only.
        self._states: dict[tuple[str, float], VisualState] = {}
        leaves, native, coverage, _ = _leaves(scene, self._evaluator)
        if native or coverage:
            raise ValueError(
                "GPU Scene adapter does not yet support native events or coverage groups"
            )
        for leaf in leaves:
            node = leaf.node
            reason = None
            if isinstance(node, PathObject) and node.deform is not None:
                reason = "deformed paths"
            elif node.material is not None and not isinstance(
                node.material, LinearGradient
            ):
                reason = "this paint field"
            elif node.clip is not None and (
                not isinstance(node.clip, RectangleClip) or node.clip.inverse
            ):
                reason = "vector/inverse clips"
            elif any(parent.clip is not None for parent in leaf.parents):
                reason = "inherited clips"
            if isinstance(node.material, LinearGradient) and any(
                ramp is not None and len(ramp.stops) > 16
                for ramp in (node.material.fill, node.material.outline)
            ):
                reason = "gradients with more than 16 stops"
            if reason:
                raise SceneCompileError(
                    f"GPU Scene adapter does not yet support {reason}",
                    object_id=node.id,
                )
        self.leaves = tuple(
            sorted(
                leaves,
                key=lambda leaf: leaf.node.layer + sum(p.layer for p in leaf.parents),
            )
        )
        self._cache: OrderedDict[tuple[object, ...], tuple[RasterImage, ...]] = (
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

    def draw_at(self, leaf: _Leaf, time: float) -> DrawCommand | None:
        if len(self._states) >= 4096:
            self._states.clear()
        state = self._evaluator._at(leaf.node.id, time, self._states)
        if state.opacity == 0 or state.singular:
            return None
        node = leaf.node
        clip = None
        if isinstance(node.clip, RectangleClip):
            rectangle = node.clip
            bounds = (
                rectangle.left,
                rectangle.top,
                rectangle.right,
                rectangle.bottom,
            )
            if rectangle.deform is not None:
                sampled = rectangle.deform.sample(local_seconds(time, node.time_origin))
                if sampled is None:
                    return None
                bounds = sampled
            if bounds[0] == bounds[2] or bounds[1] == bounds[3]:
                return None
            clip = GpuClip(bounds, local=rectangle.space == "local")
        return self.draw_state(leaf, state, clip)

    def draw_state(
        self, leaf: _Leaf, state: VisualState, clip: GpuClip | None
    ) -> DrawCommand:
        node = leaf.node
        key = _shape_key(node, state)
        images = self._cache.get(key)
        if images is None:
            images = _coverage(leaf, state, self._limit)
            size = sum(len(image[6]) for image in images)
            if size > self._limit:
                raise SceneCompileError(
                    "GPU glyph coverage exceeds cache budget", object_id=node.id
                )
            while self._bytes + size > self._limit:
                _, old = self._cache.popitem(last=False)
                self._bytes -= sum(len(image[6]) for image in old)
            self._cache[key] = images
            self._bytes += size
        self._cache.move_to_end(key)
        tinted = []
        for x, y, w, h, kind, color, data in images:
            rgb = (
                state.fill
                if kind == 0
                else state.outline
                if kind == 1
                else Color(0, 0, 0)
            )
            color = rgb.red << 24 | rgb.green << 16 | rgb.blue << 8 | (color & 255)
            tinted.append((x, y, w, h, kind, color, data))
        material = node.material
        assert material is None or isinstance(material, LinearGradient)
        return DrawCommand(
            node.id, tuple(tinted), state.transform, state.opacity, material, clip
        )
