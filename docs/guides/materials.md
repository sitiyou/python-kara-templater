# Colors, highlights, and materials

Color stores RGB channels. Use Color.hex("#RRGGBB") or named colors such as WHITE,
CYAN, and PINK. Public authoring colors use RGB; ASS BGR and inverse alpha are
encoded at the output boundary. Opacity is 0 through 1.

## Paint separate visual roles

VisualState controls an object's fill, outline, border, blur, and opacity. Use
separate Scene objects when fill, outline, and glow need independent lifetimes,
color fronts, or animation. The glow in scene_sweep remains a constant color
while fill and outline sweep independently.

SoftSweep is a spatial color field with (unsung, sung) fill/outline pairs,
independent front widths, a script-space range, start, duration, and rate.
Material time, including SoftSweep.start, is local seconds from the owning
object's birth. Delayed copies retain that local clock.
LinearGradient uses ColorRamp/ColorStop values along x or y. Fields compile into
bounded ASS color bands; step and max_bands affect precision and cost. PaintField
is the extension protocol for your own spatial paint function.

Scene materials use script-space color coordinates. Group motion changes which
parts of the object encounter a field; for a different attachment rule, author
the field or object transformation explicitly. Fill and outline bands are
independent of a separately drawn constant glow.

## Track paint and animation

TextStyle contains layout and paint declarations; PaintStyle is restricted to
paint. Blur configures glow color, radius, width, and opacity. Overlay combines
a sung paint with a reveal policy, while spans can override selected ranges.
Animate can change supported material properties, including color, border, and
blur. Declare PaintBounds for unbounded material callbacks that require explicit
maximum geometry/blur values.

Native clipping occurs after a drawing is rendered. A clipped blur does not
spread newly colored pixels across the clip front. Select an explicit coverage
or raster exit when color-before-blur or post-composite group alpha is required.

## Explicit composition choices

| Choice | Meaning | Cost and constraints |
| --- | --- | --- |
| Ordinary Scene groups | Each drawing layer receives inherited opacity and clips | Efficient ASS objects; no isolated offscreen group buffer |
| `rasterize_group` | Bake a group's completed RGBA image into ASS rectangles | Explicit spatial/temporal bounds and output budget |
| `compile_coverage` | Color source coverage, apply glow/material scopes, then encode ASS | Explicit components, partitions, glow bounds, and scoped opacity |
| `prepare_track_coverage` | Bind lyric geometry and coverage materials before evaluation | Editable group plus ID-keyed bindings; compile with explicit limits |
| Native Track with raster settings | Evaluate Track material frames before standard ASS encoding | Track sampling, RasterSettings, and final SceneBudget apply |

Raster and coverage results remain standard ASS, but can contain thousands of
pixel rectangles per frame. Whole-group RGBA and component coverage have
different compositing contracts and are explicit choices. Binding dictionaries
and ScopeOpacity owners use object IDs; remap them when copying or renaming.

For side-by-side sweep expressions, run scene_sweep_strategies with
`--strategy bands`, `layers`, `raster`, or `diffused`. Diffused color-before-blur
has different semantics from a crisp banded front. RGB/full-resolution chroma
subtitle compositing is required for pixel-level material comparisons; YUV420
can create rectangle-dependent color edges. See [compilation](compilation.md).
