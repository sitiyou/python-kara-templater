# Geometry, outlines, and masks

VectorPath contains contours made from LineSegment and CubicSegment values.
Use rectangle, circle, polygon, or explicitly authored contours to build shapes.
PathObject adds a lifetime, state, animation, and optional geometric deformation.
Vec2 and Affine2D provide typed coordinate operations.

## Measure, arrange, and split

path_bounds measures path geometry. flatten converts curves with an explicit
tolerance, and resample_path produces compatible sampled contours. layout_path
arranges PathItem values along a path with spacing and tangent orientation.
Text outlines come from outline_text or text_to_path using the measured font.
Whitespace can have layout advance without an extractable visible contour.

split_path creates geometric pieces for independent animation. merge_geometry
combines selected objects' evaluated geometry, allowing a shared silhouette,
outline, or glow. See the fragment, curved-text, and shared-word-glow examples
in the [gallery](../examples/README.md).

## Deformation, writing, and morphing

PathFunction evaluates path deformation at local seconds with declared
breakpoints and a maximum point count. Return None for an empty path when the
protocol permits it. The point bound allows resource checks before callbacks.

MorphPath and morph interpolate matching contours and segment topology. Supply
or resample compatible paths explicitly; the engine does not infer arbitrary
shape correspondence. WritingStroke and WritePath reveal authored stroke paths.
They do not infer a font's pen order. A separate object/reference can represent
the pen, including lift intervals and an independent appearance.

## Masks and spaces

RectangleClip and VectorClip can use screen or local coordinates and normal or
inverse coverage. Local clips are anchored to the object and transformed with
its hierarchy. A RectangleFunction or geometry animation changes a mask using
local seconds. Empty normal masks hide; empty inverse masks reveal.

A group mask applies in its shared coordinate space. Nested masks compose and
may require polygon/boolean lowering. path_boolean supports intersection, union,
difference, and xor with an explicit work limit. Stroke expansion, flattening,
and near-degenerate geometry can increase path cost; inspect reports rather than
assuming every composition remains a single native ASS clip.

Mirroring, skew, and zero scale are explicit geometry cases. Text can lower to
paths to preserve transforms; unsupported/degenerate combinations raise
GeometryError or SceneCompileError with object/source context. Native ASS has
no general shader, arbitrary blend stack, or 3D camera; see
[ASS and playback](../ass-and-playback.md).
