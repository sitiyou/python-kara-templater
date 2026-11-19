# Colors, highlights, and materials

Color stores RGB channels. Use Color.hex("#RRGGBB") or named colors such as WHITE,
CYAN, and PINK. Public authoring colors use RGB; ASS BGR and inverse alpha are
encoded at the output boundary. Opacity is 0 through 1.

## Gradient singing colors

Use a measured gradient as the singing highlight material, without searching for
generated nodes or calculating glyph heights:

```python
from kara_templater import Color, LyricGradient, LyricHighlights, StatePatch

highlight = LyricHighlights.from_singing(
    StatePatch(),
    material=LyricGradient((
        Color.hex("#FFE7A0"), Color.hex("#F660A2"), Color.hex("#826AFF"),
    )),
)
# Pass effects=(highlight,) to Track.
```

Colors run vertically through each measured glyph and follow its scale/translation.
Body and ruby resolve their own heights. Use `axis="x"` to spread the colors
across the visible ink of the body line. Readings sample the same horizontal
positions, so adjacent syllables continue the ramp during the wipe. Separate glow retains its configured
color; only the sung drawing receives this material. `step=1` uses one-local-pixel
color bands; increasing it trades gradient resolution for fewer ASS events.

For a duet, use the active ASS style as the singer name. For example,
`{\rLead}` and `{\rReply}` switch roles within a line. Each horizontal ramp
spans all the ink belonging to its role, including later appearances after
another singer intervenes. Ruby follows the style of its associated body text.
The leading inline volume cue takes the first nonblank singer’s palette.
Use `base_material` for the waiting lyric and `material` for the sung lyric.
Each accepts its own gradient or style mapping.

```python
from kara_templater import Color, KaraokeEffects, LyricGradient

duet = KaraokeEffects(base_material=LyricGradient((Color.hex("#FFF1D8"), Color.hex("#ADE4F0"))), material={
    "Lead": LyricGradient((Color.hex("#FF0040"), Color.hex("#0040FF")), axis="x"),
    "Reply": LyricGradient((Color.hex("#FFCC00"), Color.hex("#00EE77")), axis="x"),
})
```

Styles absent from the mapping use the recipe's solid sung paint.
A custom material factory can also read `target.source_style`.

For custom appearance, `material` also accepts a `PaintField` or a factory taking
`(line, target)` and returning a field (or None). The factory runs once per target
and highlight during preparation, not per frame. Explicit `Highlight` declarations
accept the same material parameter.

This uses the local `LinearGradient` backend: currently it requires clip strategy,
a single positive singing interval, and axis-aligned scale/translation. Repeated
singing and coverage-mode material composition are not supported by this backend.
Unsupported combinations raise; inspect compilation reports for band/event cost.

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
With `native_tweens=True`, a static screen-space `LinearGradient` can share native rectangle
clip animation when the clip edges along the gradient axis stay fixed. For
example, vertical color bands support a horizontal karaoke sweep. Geometry and
colors must remain static; eligible opacity fades are supported. Continuous clip
sections share one event per band, while instantaneous resets remain separate.
This keeps event counts independent of sampling FPS for eligible objects without
changing `step`. Inverse clips, animated geometry/colors, custom paint fields,
and screen-space clips crossing color bands use the general sampler. Native clips
retain the compiler's existing integer-coordinate error budget.

Material time, including SoftSweep.start, is local seconds from the owning
object's `time_origin`. Delayed copies retain that local clock. Custom fields
can use signed local times when visibility precedes the origin; see
[animation clocks](animation.md#scene-clips-and-timelines).
LinearGradient uses ColorRamp/ColorStop values along x or y. Fields compile into
bounded ASS color bands; step and max_bands affect precision and cost. PaintField
is the extension protocol for your own spatial paint function.

`LinearGradient(space="local")` uses untransformed drawing coordinates for
color stops and band width. On an unmasked, closed vector path, a fill gradient
rotates with the path. ASS cuts the fixed path into colored pieces once and
transforms them around the original pivot. The standalone hook samples the
gradient continuously. To color the pen, set the gradient’s `outline` ramp and
a positive border radius. ASS clips the original pen into rotated color bands,
including the part that extends beyond the path. A solid face stays in one piece.
Moving outline bands use sampled ASS events. Place shadows and blur on separate drawings.

For text and clipped paths, local gradients follow positive axis-aligned scaling
and translation and require a non-inverse local `RectangleKeyframes` clip without
parent masks. A sweep across stationary geometry uses one native clip event per
band. For a moving or scaling glyph, the compiler can sample the intersections.
Coverage materials do not support local gradients.

Eligible local gradients retain native clip and scale/opacity transforms; a
single position-only linear Tween can share the same event. Multiple moves or
unsupported curves may require more events or sampling. Native clip coordinates
still have the compiler's integer rounding/error contract: attached one-pixel
bands are not a continuous shader texture.

Other scene materials use script-space color coordinates. Group motion changes which
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
Each pass has explicit measured horizontal bounds and absolute seconds.
Use `HighlightPass(time, region, reverse=True)` to sweep that region from right to left.
`HighlightArrival` then triggers when the front reaches the right edge of each
character. The text keeps its original position and reading order. Split a
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

For a normal karaoke sweep, use `LyricHighlights.from_singing(...)` instead
of building clip rectangles or timing decorative margins in the template:

```python
from kara_templater import YELLOW, WHITE, Glow, LyricHighlights, StatePatch

# In a Track factory receiving a LyricLine:
def paint_line(line):
    return LyricHighlights.from_singing(
        StatePatch(fill=YELLOW, outline=WHITE, border=5),
        base_glow=Glow(WHITE, blur=8, border=10),
        glow=Glow(YELLOW, blur=12, border=14),
    )(line)
```

For a single-pass Karaoke Studio text glow, use
`Glow.from_studio(YELLOW, radius=10, outline=5)`. Supply the Studio glow radius
and the total outward reach of the hard outline in script pixels. Here a
10 px Gaussian blurs a pen that extends 10 px beyond the glyph. This models
Studio's low concentration setting. Medium and high concentrations composite
two and three blurred images respectively.

Source singing maps onto undecorated measured text bounds, independently of
outline and glow width. For a single source interval in clip mode, the engine
reserves 20 ms before and after singing to traverse the decorative margins.
At the original singing start the front reaches the body's left edge; at the
original end it reaches the right edge. These shoulders do not consume singing
time or move its clocks. Body, outline, glow and ruby share this rule. Enable
`native_tweens=True` when compiling to lower eligible linear passes into
continuous ASS clip animations, independent of the scene sampling FPS.
Repeated source intervals retain the general ownership path; coverage retains
its color-before-blur behavior without adding clip shoulders. Existing custom
`HighlightPass` regions and clocks remain explicit and unchanged.

The clip strategy creates ordinary before/after layers and optional static glow
layers. Coverage assigns fractional material ownership before blur. Dynamic glow
requires the explicit coverage strategy. Existing masks and materials require
explicit composition rather than silent replacement. The same target mapping
keeps highlight and glow copies synchronized with character animations.
When ownership reaches a unit's outer edge, it includes the glyph's overhang,
outline and glow. A completed whole-unit pass therefore owns the entire drawing;
interior region boundaries remain precise cuts.

During an automatic wipe, halos with matching blur and border blend their
color and opacity across the front. A fully transparent side contributes no
color, so a fading halo keeps its visible hue. The engine approximates
the Gaussian color transition with up to eight narrow moving strips between
the two outer colors. Each strip follows the same singing clock as the text.
A linear wipe can export these as native ASS clip animations. Differences in
halo geometry keep the ordinary clipped layers. Use coverage to
partition actual glyph ink before blurring, including across gaps in a glyph.

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
