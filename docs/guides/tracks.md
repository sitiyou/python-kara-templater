# Configure lyric Tracks

Track is a reusable lyric declaration: source selection, body/ruby appearance,
highlight overlay, layout, and animations. `prepare_tracks` binds declarations to
a Document and produces Scene content. Scene remains the common composition and
compilation interface.

## Prepare existing lyrics

This script expects `input.ass` with supported karaoke timing:

```python
from kara_templater import (
    CYAN, WHITE, Body, Document, FadeInAnimation, LineMatch, Overlay,
    PaintStyle, Ruby, SingingPulseAnimation, TextStyle, Track, prepare_tracks,
)

source = Document.load("input.ass")
prepared = prepare_tracks(source, tracks=(
    Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=WHITE)),
        ruby=Ruby(),
        overlay=Overlay(style=PaintStyle(fill=CYAN)),
        animations=(FadeInAnimation(duration=400), SingingPulseAnimation(peak=1.1)),
    ),
))
result = prepared.compile()
result.document.save("output.ass")
```

Use `prepared.scene.add(...)` to add independent decorations before compiling.
Each input item can match at most one Track. Unmatched source events survive;
preparing the same owner again replaces its earlier generated content.

## Appearance and layout

Body and Ruby use TextStyle for font/layout-affecting appearance. Overlay accepts
PaintStyle, which cannot change font metrics. Blur groups glow color, width,
radius, and opacity. TextSpan selects body-wide source ranges; RubySpan selects
a reading by unit/segment and an optional range. Their paint overrides do not
split the original singing segment. Range boundaries must align with drawable
clusters.

Omitting layout preserves the source style's position. SingleLine and DoubleLine
allocate explicit rows. TrackGroup shares row allocation across its children;
its layout must have an absolute position and child Tracks must omit layout.
Separate Tracks retain independent source selection and timing.

Use ordinary constructors and factories for reuse. Subclass Track or Animation
when that makes a domain-specific configuration clearer. There is no class-field
constructor transformation. StyleSheet with rule() supports role/class/source
selectors and sung-state appearance when a cascade is useful.

## Output modes

| Choice | Content and evaluation | Limits |
| --- | --- | --- |
| `prepare_tracks(..., mode="editable")` (default) | Editable ObjectGroups; callbacks run at Scene compilation | Uses SceneBudget; supported ordinary text styles; per-drawing-layer opacity |
| `prepare_tracks(..., mode="native")` | Lowered NativeEvents; callbacks run during preparation | Preserves native interpolation and styles; optional OutputSettings/raster |
| `prepare_track_coverage(...)` | Editable material components and explicit coverage bindings | Color-before-blur and scoped opacity; explicit glow bounds and raster cost |

Editable output rejects unsupported Underline, StrikeOut, Angle, or nonordinary
BorderStyle rather than dropping them. Use native mode for those source style
semantics. Native and sampled motion can differ between sample times. Editable
mode uses SceneBudget rather than OutputSettings or native on_estimate.

For native mode, OutputSettings.resolution must equal Document PlayRes, and
Track.sampling controls dynamic property preparation. on_estimate receives a
RenderEstimate before property sampling, allowing cost inspection or cancellation.
It is an estimate before merging and native subdivision, not a final upper bound.
The final Scene compilation still applies whole-document budgets.

## Parallel highlights

Overlay.highlights accepts explicit HighlightTrack values or a typed layout
function returning them. HighlightStyle assigns paint and priority by track ID.
Overlay.overlap chooses union, priority, or layer composition. Explicit highlights
own their progress curves; avoid supplying a conflicting Sweep.progress_curve.

Union merges compatible coverage, priority chooses the highest-priority paint,
and layer retains translucent stacks over the base. Per-range sung appearance
still applies where no explicit highlight paint overrides it. See
[parallel_tracks.py](../../examples/parallel_tracks.py) for all three policies.
Native and editable modes support these declarations. Coverage Track output
currently requires union highlights with a shared paint and rejects the other
policies explicitly.

For independent full-word glows, custom shapes, or new motion, add ordinary Scene
objects rather than depending on generated ASS layers. See [materials](materials.md),
[animation](animation.md), and the [gallery](../examples/README.md).
