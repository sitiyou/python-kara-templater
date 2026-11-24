"""Native shaped text to source-preserving cubic paths, including fallback faces."""

from dataclasses import dataclass

from . import _metrics
from .characters import FontFace
from .geometry import (
    Box,
    Contour,
    CubicSegment,
    LineSegment,
    Segment2D,
    Vec2,
    VectorPath,
)
from .path_geometry import GeometryError
from .scene import PathObject, TextObject


@dataclass(frozen=True)
class TextOutline:
    """Measured text geometry with layout bounds and actual font faces.

    path can be None for whitespace or empty ink; layout advance remains meaningful.
    """

    path: VectorPath | None
    layout_bounds: Box
    fonts: tuple[FontFace, ...]


@dataclass(frozen=True, kw_only=True)
class _VectorGuideText(TextObject):
    """Timed glyph kept as a lyric target until Scene lowers its drawing."""

    outline: TextOutline


def outline_text(node: TextObject, *, max_points: int = 4096) -> TextOutline:
    """Shape at the source font's nominal scale; object transforms stay independent."""
    if type(max_points) is not int or max_points < 1:
        raise ValueError("outline point budget must be a positive integer")
    if isinstance(node, _VectorGuideText):
        if node.outline.path is not None and node.outline.path.point_count > max_points:
            raise GeometryError("guide outline point budget exceeded")
        return node.outline
    width, height, _, baseline, outlines = _metrics.text_shape(
        node.font,
        node.font_size,
        int(node.bold),
        int(node.italic),
        100,
        100,
        node.spacing,
        node.encoding,
        # The native metrics API retains legacy ASS escape semantics. Scene
        # text is literal, so protect backslashes at this frontend boundary;
        # the native measurer already escapes braces itself.
        node.text.replace("\\", "\\\u2060"),
        0,
    )
    contours: list[Contour] = []
    faces: list[FontFace] = []
    count = 0
    # Text alignment applies to the advance box, not the ink bounding box.
    horizontal = (node.alignment - 1) % 3
    vertical = (node.alignment - 1) // 3
    offset = Vec2(-width * horizontal / 2, -height * (2 - vertical) / 2)
    for points, orders, _, face in outlines:
        faces.append(FontFace(face[0], face[1], face[3]))
        if not points:
            continue
        values = tuple(Vec2(x, y + baseline) + offset for x, y in points)
        cursor = first = 0
        segments: list[Segment2D] = []
        for code in orders:
            order, closed = code & 3, bool(code & 4)
            if order not in (1, 2, 3) or cursor + order > len(values):
                raise GeometryError("invalid native glyph outline segment")
            end_index = first if closed else cursor + order
            if end_index >= len(values):
                raise GeometryError("native contour is not closed")
            start, end = values[cursor], values[end_index]
            if order == 1:
                segments.append(LineSegment(end))
                count += 1
            elif order == 2:
                control = values[cursor + 1]
                segments.append(
                    CubicSegment(
                        start.lerp(control, 2 / 3), end.lerp(control, 2 / 3), end
                    )
                )
                count += 3
            else:
                segments.append(
                    CubicSegment(values[cursor + 1], values[cursor + 2], end)
                )
                count += 3
            if count + len(contours) + 1 > max_points:
                raise GeometryError("text outline point budget exceeded")
            cursor += order
            if closed:
                contours.append(Contour(values[first], tuple(segments)))
                segments = []
                first = cursor
        if cursor != len(values) or segments:
            raise GeometryError("native outline contains unconsumed points")
    path = VectorPath(tuple(contours)) if contours else None
    return TextOutline(
        path, Box(offset.x, offset.y, width, height), tuple(dict.fromkeys(faces))
    )


def text_to_path(
    node: TextObject, *, id: str | None = None, path: VectorPath | None = None, max_points: int = 4096
) -> PathObject:
    """Use the shaped outline or a supplied path in the text object's local coordinates.

    Preserve visibility, animation and clip clocks, fill mode, and source identity.
    max_points limits native glyph extraction when path is omitted.
    """
    if path is None:
        path = outline_text(node, max_points=max_points).path
    if path is None:
        raise GeometryError(
            "text has no visible outline; preserve its layout space instead"
        )
    return PathObject(
        id=node.id if id is None else id,
        lifetime=node.lifetime,
        clock_start=node.clock_start,
        path=path,
        filled=node.filled,
        extrusion=node.extrusion,
        scale_border=node.scale_border,
        state=node.state,
        animations=node.animations,
        layer=node.layer,
        origin=node.origin,
        clip=node.clip,
        material=node.material,
        reference=node.reference,
    )
