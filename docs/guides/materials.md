# Colors, highlights, and materials

Color stores RGB channels. Use Color.hex("#RRGGBB") or named colors such as WHITE,
CYAN, and PINK. Public authoring colors use RGB; ASS BGR and inverse alpha are
encoded at the output boundary. Opacity is 0 through 1.

## Gradient highlight colors

Use a measured gradient as the highlight material, without searching for
generated nodes or calculating glyph heights:

```python
from kara_templater import Color, LyricGradient, LyricHighlights, StatePatch

highlight = LyricHighlights.from_timing(
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
color; only the highlight drawing receives this material. Export gradients with the GPU hook.

For a duet, use the active ASS style as the singer name. For example,
`{\rLead}` and `{\rReply}` switch roles within a line. Each horizontal ramp
spans all the ink belonging to its role, including later appearances after
another singer intervenes. Ruby follows the style of its associated body text.
The leading inline volume cue takes the first nonblank singer’s palette.
Use `base_material` for the base text and `material` for the highlighted text.
Each accepts its own gradient or style mapping.

```python
from kara_templater import Color, KaraokeEffects, LyricGradient

duet = KaraokeEffects(base_material=LyricGradient((Color.hex("#FFF1D8"), Color.hex("#ADE4F0"))), material={
    "Lead": LyricGradient((Color.hex("#FF0040"), Color.hex("#0040FF")), axis="x"),
    "Reply": LyricGradient((Color.hex("#FFCC00"), Color.hex("#00EE77")), axis="x"),
})
```

Styles absent from the mapping use the recipe's solid highlight paint.
A custom material factory can also read `target.source_style`.

A material factory takes `(line, target)` and returns a LinearGradient or None.
The factory runs once per target and highlight during preparation. Explicit
Highlight declarations accept the same parameter. Export gradients with Hook.

## Paint separate visual roles

VisualState controls an object's fill, outline, border, blur, and opacity. Use
separate Scene objects when fill, outline, and glow need independent lifetimes,
color fronts, or animation. A constant-color glow can use a separate layer
while fill and outline sweep independently.
Border and blur widths are script pixels. Geometry scaling does not implicitly
animate those channels; animate border/blur alongside scale when their widths
should grow with the text.

LinearGradient uses ColorRamp and ColorStop along either axis. Hook evaluates
the fill and outline ramps independently. Set `space="local"` to move the
gradient with its drawing. The default screen-space gradient stays fixed.

## Lyric paint and animation

LyricHighlights binds named HighlightPass regions with union, priority or layered
ownership. A Highlight carries a StatePatch and optional Glow; body/ruby glow
factories may return different widths and colors.
Each pass has explicit measured horizontal bounds and absolute seconds.
Use `HighlightPass(time, region, reverse=True)` to sweep that region from right to left.
`HighlightArrival` then triggers when the front reaches the right edge of each
character. The text keeps its original position and reading order. Split a
body region across several passes to keep a pause between adjacent portions, or
reuse the whole region for a repeated traversal. A new `round` with `repeat="reset"`
discards the previous round's coverage; `repeat="hold"` keeps completed regions.
Use measured reading bounds as Regions to choose custom body partitions. For nonlinear speed with exact character
arrival times, pass `ProgressCurve.at` as the rate and its `arrival` method as
`inverse_rate`, and declare the curve's time knots as pass-local breakpoints.

Priority selects one contribution in an overlap. Layer mode composites each
contribution in order: two half-opacity layers produce about 0.75 alpha, rather
than an implicitly opaque base. Add a separate base drawing if that is desired.

For a normal karaoke sweep, use `LyricHighlights.from_timing(...)` instead
of building clip rectangles or timing decorative margins in the template:

```python
from kara_templater import YELLOW, WHITE, Glow, LyricHighlights, StatePatch

# In a Track factory receiving a LyricLine:
def paint_line(line):
    return LyricHighlights.from_timing(
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

Source timing maps onto undecorated measured text bounds, independently of
outline and glow width. For a single source interval in clip mode, the engine
reserves 20 ms before and after timing to traverse the decorative margins.
At the original timing start the front reaches the body's left edge; at the
original end it reaches the right edge. These shoulders do not consume the timed interval
time or move its clocks. Body, outline, glow and ruby share this rule. Enable
`native_tweens=True` when compiling to lower eligible linear passes into
continuous ASS clip animations, independent of the scene sampling FPS.
Repeated source intervals use the general ownership evaluator. Custom
HighlightPass regions and clocks remain explicit. The same target mapping
keeps highlight and glow copies synchronized with character animations.
When ownership reaches a unit's outer edge, it includes the glyph's overhang,
outline and glow. A completed whole-unit pass therefore owns the entire drawing;
interior region boundaries remain precise cuts.

During an automatic wipe, halos with matching blur and border blend their
color and opacity across the front. A fully transparent side contributes no
color, so a fading halo keeps its visible hue. One blurred glyph mask supplies
coverage while the WGSL material evaluates the Gaussian color transition on
the text's timing clock. Blended halos require Hook export. For ASS, choose
separate halos with `blend_glow=False`. Distinct halo geometry uses separate
clipped layers.
