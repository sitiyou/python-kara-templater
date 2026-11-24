"""Rasterize drawing coverage for Hook and the ASS preview."""

from math import ceil, floor, log, sqrt

import aggdraw  # ty: ignore[import-not-found]  # Extension module without a type stub.
from PIL import Image, ImageChops, ImageFilter

from . import _text_native
from ._native_types import RasterImage
from .geometry import CubicSegment, Vec2, VectorPath
from .path_geometry import path_bounds
from .scene import SceneCompileError
from .scene_animation import VisualState

STROKE_FACE = 5


def cutout_border(state: VisualState, filled: bool) -> bool:
    # libass removes fill coverage from the border when either karaoke fill
    # color is translucent. Fully opaque text uses a solid backing instead.
    return filled and state.border > 0 and round((1 - state.opacity * state.face_opacity) * 255) != 0


def _sweep_mask(mask: Image.Image, offset: Vec2, depth: Image.Image | None = None) -> Image.Image:
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
        previous = result.crop(dest)
        swept = ImageChops.lighter(previous, shifted)
        if depth is not None:
            # Weight newly exposed coverage by its distance along the sweep.
            delta = ImageChops.subtract(swept, previous)
            weighted = delta.point([round(v * (step - 0.5) / steps) for v in range(256)])
            depth.paste(ImageChops.add(depth.crop(dest), weighted), dest)
        result.paste(swept, dest)
    # The face composites over this pass. Solve swept = face + side * (1-face)
    # at the antialiased edge to avoid a background-colored hairline.
    exposed = ImageChops.subtract(result, mask)
    if depth is not None:
        normalized = bytes(min(255, round(255 * total / area)) if area else 0
                           for total, area in zip(depth.tobytes(), exposed.tobytes(), strict=True))
        depth.frombytes(normalized)
    edge = bytes(
        (extra * 255 + (255 - face) // 2) // (255 - face) if extra and face else extra
        for extra, face in zip(exposed.crop(box).tobytes(), mask.crop(box).tobytes(), strict=True)
    )
    exposed.paste(Image.frombytes("L", (r - x, b - y), edge), box)
    return exposed


def path_coverage(
    path: VectorPath, state: VisualState, filled: bool, pixel_budget: int, object_id: str, *,
    sweep: Vec2 | None = None, shaded: bool = False, keep_face: bool = False,
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
    if state.border and (not filled or cutout_border(state, filled)):
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
        depth = Image.new("L", silhouette.size) if shaded else None
        side = _sweep_mask(silhouette, sweep, depth)
        append(side, 3, True)
        if depth is not None and images:
            x, y, w, h, *_ = images[0]
            moment = ImageChops.multiply(side, depth)
            if sigma:
                moment = moment.filter(ImageFilter.GaussianBlur(sigma))
            # Premultiplied depth shares the side mask's crop and bilinear filtering.
            data = moment.crop((x - left, y - top, x - left + w, y - top + h)).tobytes()
            images.append((x, y, w, h, 4, 0, data))
        return tuple(images)

    if (state.shadow.x or state.shadow.y) and (filled or state.border):
        append(backing if filled else border_mask, 2, True, round(state.shadow.x), round(state.shadow.y))
    if state.border:
        append(border_mask, 1, True)
    if filled:
        append(fill, 0, not state.border)
    if keep_face:
        if fill.getbbox() is not None:
            append(fill, STROKE_FACE, False)
        else:
            images.append((left, top, 1, 1, STROKE_FACE, 0, b"\x00"))
    return tuple(images)
