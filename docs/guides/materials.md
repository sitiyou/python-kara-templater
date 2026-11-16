# Colors, highlights, and materials

Color stores RGB channels. Use Color.hex("#RRGGBB") or named colors such as WHITE,
CYAN, and PINK. Public authoring colors use RGB; ASS BGR and inverse alpha are
encoded at the output boundary. Opacity is 0 through 1.

## Paint separate visual roles

VisualState controls an object's fill, outline, border, blur, and opacity. Use
separate Scene objects when fill, outline, and glow need independent lifetimes,
color fronts, or animation. The glow in scene_sweep remains a constant color
while fill and outline sweep independently.
Border and blur widths are script pixels. Geometry scaling does not implicitly
animate those channels; animate border/blur alongside scale when their widths
should grow with the text.

SoftSweep is a spatial color field with (unsung, sung) fill/outline pairs,
independent front widths, a script-space range, start, duration, and rate.
Material time, including SoftSweep.start, is local seconds from the owning
object's `time_origin`. Delayed copies retain that local clock. Custom fields
can use signed local times when visibility precedes the origin; see
[animation clocks](animation.md#scene-clips-and-timelines).
LinearGradient uses ColorRamp/ColorStop values along x or y. Fields compile into
bounded ASS color bands; step and max_bands affect precision and cost. PaintField
is the extension protocol for your own spatial paint function.

Scene materials use script-space color coordinates. Group motion changes which
parts of the object encounter a field; for a different attachment rule, author
the field or object transformation explicitly. Fill and outline bands are
independent of a separately drawn constant glow.

## Lyric paint and animation

LyricSweep binds soft fill/outline fronts to measured lyric targets. Its color
factories receive a LyricLine and LyricTarget once during construction.
Object animations evaluate before the paint field. LyricSweep uses that evaluated
fill/outline as the unsung color and its configured colors as the sung endpoint;
an omitted channel retains the evaluated color everywhere. Binding the animation
before or after applying the sweep gives the same result. To animate the sung
endpoint itself, supply a custom PaintField that resolves both colors from time
and the incoming state. Color factories return Color or None and are checked when
the sweep is applied to a line. Returning None retains that target's animated
channel; if both fill and outline are omitted, its existing material is untouched.
For example, `LyricSweep(fill=lambda line, target: PINK if target.role == "character" else None)`
sweeps the body while leaving ruby unchanged.
Body and ruby colors are chosen explicitly by target; mixed body colors do not
implicitly choose a ruby color. A factory may inspect the target role, source
range or tags and return the desired color. Selection changes paint without
splitting lyric units, reshaping clusters or retiming their singing spans.
Zero-duration singing (`\k0`) switches to the sung color at its start; it does
not acquire an artificial animation duration. Delayed copies shift that switch
with their visual clock.
LyricHighlights binds named HighlightPass regions with union, priority or layered
ownership. A Highlight carries a StatePatch and optional Glow; body/ruby glow
factories may return different widths, colors or dynamic GlowFunction values.
Each pass has explicit measured horizontal bounds and absolute seconds. Split a
body region across several passes to keep a pause between adjacent portions, or
reuse the whole region for a repeated traversal. A new `round` with `repeat="reset"`
discards the previous round's coverage; `repeat="hold"` keeps completed regions.
Ruby-weighted body partitions are an author choice: compute those bounds from
measured readings and pass them as Regions. LyricSweep instead traverses the
whole unit for each source interval. For nonlinear speed with exact character
arrival times, pass `ProgressCurve.at` as the rate and its `arrival` method as
`inverse_rate`, and declare the curve's time knots as pass-local breakpoints.

Priority selects one contribution in an overlap. Layer mode composites each
contribution in order: two half-opacity layers produce about 0.75 alpha, rather
than an implicitly opaque base. Add a separate base drawing if that is desired.

The clip strategy creates ordinary before/after layers and optional static glow
layers. Coverage assigns fractional material ownership before blur. Dynamic glow
requires the explicit coverage strategy. Existing masks and materials require
explicit composition rather than silent replacement. The same target mapping
keeps highlight and glow copies synchronized with character animations.
When ownership reaches a unit's outer edge, it includes the glyph's overhang,
outline and glow. A completed whole-unit pass therefore owns the entire drawing;
interior region boundaries remain precise cuts.

Native clipping occurs after a drawing is rendered. A clipped blur does not
spread newly colored pixels across the clip front. Select an explicit coverage
or raster exit when color-before-blur or post-composite group alpha is required.

GlowFunction.from_animation reuses the common animation evaluator and infers
spatial bounds for linear Tweens and nested sequences:

```python
from kara_templater import (
    RED, Glow, GlowFunction, StatePatch, Timeline, Tween,
)

sequence = (
    Timeline()
    .play(Tween(StatePatch(fill=RED, blur=10)), duration=0.1)
    .wait(0.7)
    .play(Tween(StatePatch(blur=2)), duration=0.2)
    .animation
)

glow = GlowFunction.from_animation(sequence, base=Glow(blur=2))

```

Use this field in Coverage.glows or a coverage LyricHighlights configuration.
Its time is local to the visual leaf's `time_origin`; the example starts there.
Use start and duration to place or stretch it, and hold=False to restore the base
glow after it ends. fill maps to glow color; blur, border and opacity map directly.
Other channels are rejected. Custom spatial animations or easing callbacks need
explicit max_blur/max_border; inference never samples user code. Explicit bounds
must also cover the base and any known targets. World scaling is not implicit;
use a GlowFunction callback for geometry-dependent glow sizes.
The field does not extend that leaf's lifetime or reserve a layout row. Arrange
display time explicitly when a glow continues after singing. Bounds include all
callback results, including any geometry-dependent scaling the callback adds.

## Explicit composition choices

| Choice | Meaning | Cost and constraints |
| --- | --- | --- |
| Ordinary Scene groups | Each drawing layer receives inherited opacity and clips | Efficient ASS objects; no isolated offscreen group buffer |
| `rasterize_group` | Bake a group's completed RGBA image into ASS rectangles | Explicit spatial/temporal bounds and output budget |
| `ObjectGroup(coverage=Coverage(...))` | Color source coverage, apply glow/material scopes, then encode ASS | Explicit components, partitions, glow bounds, and scoped opacity |

Raster and coverage results remain standard ASS, but can contain thousands of
pixel rectangles per frame. Whole-group RGBA and component coverage have
different compositing contracts and are explicit choices. Binding dictionaries
and ScopeOpacity owners use object IDs; copying a configured ObjectGroup remaps
its internal ownership IDs.

A coverage group may be inside ordinary groups. Parent transforms, masks,
opacity and lifetimes apply to that branch; sibling drawings remain separate.
Clipping a display window does not restart animation clocks. Geometry references
can address objects elsewhere in the same Scene. Nested coverage declarations
and opacity-writing references currently raise explicit ownership errors.

For side-by-side sweep expressions, run scene_sweep_strategies with
`--strategy bands`, `layers`, `raster`, or `diffused`. Diffused color-before-blur
has different semantics from a crisp banded front. RGB/full-resolution chroma
subtitle compositing is required for pixel-level material comparisons; YUV420
can create rectangle-dependent color edges. See [compilation](compilation.md).
