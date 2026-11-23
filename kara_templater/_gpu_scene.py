"""Resolve the shared Scene into owner-specific GPU draws, without ASS banding.

This first adapter supports ordinary text/static paths, affine state, normal
rectangle clips and LinearGradient. Unsupported composition fails explicitly.
It does not serialize author callbacks or invent a second animation evaluator.
"""

from collections import OrderedDict
from dataclasses import dataclass, replace
from math import ceil, floor, log, sqrt

import aggdraw  # ty: ignore[import-not-found]  # Extension module without a type stub.
from PIL import Image, ImageChops, ImageFilter

from . import _text_native
from ._contour_stroke import ContourStroke
from ._native_types import RasterImage
from .composition import Color
from .geometry import Affine2D, CubicSegment, Vec2, VectorPath, finite
from .paint_fields import LinearGradient, ShaderPaint
from .path_geometry import path_bounds
from .scene import PathObject, RectangleClip, Scene, TextObject, _LyricPaintClip
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
    shader_paint: ShaderPaint | None = None
    time_origin: float = 0
    border: float = 0


class _ExtrusionSide(_Leaf):
    """A second paint pass sharing the face's scene identity and animation clock."""


def _shape_key(leaf: _Leaf, state: VisualState) -> tuple[object, ...]:
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
        return ("extrusion", *shape, node.filled, state.border, state.blur, node.extrusion.offset)
    if isinstance(node.shader_paint, ContourStroke):
        return ("stroke", node.shader_paint.bounds)
    return (*shape, node.filled, state.border, state.blur, state.shadow, _cutout_border(node, state))


def _cutout_border(node: TextObject | PathObject, state: VisualState) -> bool:
    # libass removes fill coverage from the border when either karaoke fill
    # color is translucent. Fully opaque text uses a solid backing instead.
    return node.filled and state.border > 0 and round((1 - state.opacity) * 255) != 0


def _coverage(
    leaf: _Leaf, state: VisualState, pixel_budget: int
) -> tuple[RasterImage, ...]:
    node = leaf.node
    if isinstance(node.shader_paint, ContourStroke):
        # Coverage is evaluated from geometry by the fragment shader.
        return ((*node.shader_paint.bounds, 1, 0, b""),)
    path = (
        outline_text(node, max_points=200_000).path
        if isinstance(node, TextObject)
        else node.path
    )
    if path is None:
        return ()
    offset = node.extrusion.offset if isinstance(leaf, _ExtrusionSide) and node.extrusion else None
    return path_coverage(path, state, node.filled, pixel_budget, node.id, sweep=offset)


def _sweep_mask(mask: Image.Image, offset: Vec2) -> Image.Image:
    # Grayscale dilation by a line segment. Every sample comes from the
    # original antialiased silhouette, so coverage never accumulates opacity.
    result = mask.copy()
    box = mask.getbbox()
    if box is None:
        return result
    # Retain one transparent texel for bilinear interpolation on every edge.
    x, y, r, b = box
    source = mask.crop((x - 1, y - 1, r + 1, b + 1))
    steps = ceil(max(abs(offset.x), abs(offset.y)))
    for step in range(1, steps + 1):
        dx, dy = offset.x * (step / steps), offset.y * (step / steps)
        ix, iy = floor(dx), floor(dy)
        shifted = source
        if dx != ix or dy != iy:
            shifted = source.transform(source.size, Image.Transform.AFFINE,
                                       (1, 0, ix - dx, 0, 1, iy - dy), Image.Resampling.BILINEAR)
        dest = (x - 1 + ix, y - 1 + iy, r + 1 + ix, b + 1 + iy)
        result.paste(ImageChops.lighter(result.crop(dest), shifted), dest)
    # The face composites over this pass. Solve swept = face + side * (1-face)
    # at the antialiased edge to avoid a background-colored hairline.
    exposed = ImageChops.subtract(result, mask)
    edge = bytes(
        (extra * 255 + (255 - face) // 2) // (255 - face) if extra and face else extra
        for extra, face in zip(exposed.crop(box).tobytes(), mask.crop(box).tobytes(), strict=True)
    )
    exposed.paste(Image.frombytes("L", (r - x, b - y), edge), box)
    return exposed


def path_coverage(
    path: VectorPath, state: VisualState, filled: bool, pixel_budget: int, object_id: str, *,
    sweep: Vec2 | None = None,
) -> tuple[RasterImage, ...]:
    bounds = path_bounds(path)
    if not 0 <= state.blur <= 100:
        raise ValueError("Blur radius must be in 0..100 ASS pixels")
    sigma = state.blur * 2 / sqrt(log(256))
    padding = ceil(state.border + 4 * sigma) + 2
    left, top = floor(bounds.left) - padding, floor(bounds.top) - padding
    width = ceil(bounds.right) + padding - left
    height = ceil(bounds.top + bounds.height) + padding - top
    if sweep is not None:
        left += min(0, floor(sweep.x))
        top += min(0, floor(sweep.y))
        width += ceil(abs(sweep.x))
        height += ceil(abs(sweep.y))
    if width * height > pixel_budget:
        raise SceneCompileError("GPU glyph raster pixel budget exceeded", object_id=object_id)

    drawing = aggdraw.Path()
    strokes: list[list[tuple[float, ...]]] = []
    for contour in path.contours:
        x, y = contour.start.x - left, contour.start.y - top
        drawing.moveto(x, y)
        segments: list[tuple[float, ...]] = [(x, height - y)] if state.border else []
        for segment in contour.segments:
            x, y = segment.end.x - left, segment.end.y - top
            if isinstance(segment, CubicSegment):
                x1, y1 = segment.control1.x - left, segment.control1.y - top
                x2, y2 = segment.control2.x - left, segment.control2.y - top
                drawing.curveto(x1, y1, x2, y2, x, y)
                if state.border:
                    segments.append((x1, height - y1, x2, height - y2, x, height - y))
            else:
                drawing.lineto(x, y)
                if state.border:
                    segments.append((x, height - y))
        drawing.close()
        if len(segments) > 1:
            strokes.append(segments)

    fill = Image.new("L", (width, height))
    canvas = aggdraw.Draw(fill)
    canvas.path(drawing, aggdraw.Brush("white"))
    canvas.flush()
    backing = fill
    if strokes:
        stroke = _text_native.round_stroke(width, height, state.border, strokes)
        backing = ImageChops.lighter(fill, Image.frombytes("L", fill.size, stroke))
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

    if sweep is not None:
        silhouette = backing if filled else border_mask
        append(_sweep_mask(silhouette, sweep), 3, True)
        return tuple(images)

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
        if native:
            event = native[0]
            raise SceneCompileError(
                f"hook cannot compile native events at {event.event.start_time / 1000:g}s",
                object_id=event.id, origin=event.origin,
            )
        if coverage:
            group = coverage[0]
            raise SceneCompileError(
                f"hook cannot compile coverage groups at {group.lifetime.start:g}s",
                object_id=group.id, origin=group.origin,
            )
        for leaf in leaves:
            node = leaf.node
            reason = None
            if isinstance(node, PathObject) and node.deform is not None:
                reason = "deformed paths"
            elif node.material is not None and not isinstance(
                node.material, LinearGradient
            ):
                reason = f"paint field {type(node.material).__name__}"
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
                    f"hook cannot compile {reason} at {leaf.start:g}s",
                    object_id=node.id, origin=node.origin,
                )
        passes = list(leaves)
        for leaf in leaves:
            node = leaf.node
            if node.extrusion is None or node.extrusion.offset == Vec2():
                continue
            # Only a singing-color partition is face-specific. User clip masks
            # still cut the entire extruded object.
            side = replace(node, material=None, shader_paint=None,
                           clip=None if isinstance(node.clip, _LyricPaintClip) else node.clip)
            passes.append(_ExtrusionSide(side, leaf.parents, leaf.start, leaf.end, leaf.evaluator))
        self.leaves = tuple(sorted(passes, key=lambda leaf: (
            leaf.node.layer + sum(p.layer for p in leaf.parents),
            0 if isinstance(leaf, _ExtrusionSide) else 1,
        )))
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
        key = _shape_key(leaf, state)
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
                else node.extrusion.color if kind == 3 and node.extrusion is not None
                else Color(0, 0, 0)
            )
            color = rgb.red << 24 | rgb.green << 16 | rgb.blue << 8 | (color & 255)
            tinted.append((x, y, w, h, kind, color, data))
        material = node.material
        assert material is None or isinstance(material, LinearGradient)
        return DrawCommand(
            node.id, tuple(tinted), state.transform, state.opacity, material, clip, node.shader_paint, node.time_origin, state.border
        )
