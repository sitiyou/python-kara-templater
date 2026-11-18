# Configure lyric Tracks

Track declares an independent lyric stream: source selection, layout, display
padding, cue content and effects. `prepare_tracks`
returns a LyricScene containing ordinary objects. Add decorations with
`scene.add(...)` and compile with the same Scene compiler used for direct authoring.
All authoring times below are seconds.

With layout omitted, Track alternates two bottom rows, upper left then lower
right. It requests 1.8 s preview and 1.0 s tail. To place lyrics at a fixed
origin or use another row count, pass an explicit `Layout`. See the
[karaoke layout tutorial](../tutorials/karaoke-design.md) for margins and spacing.

Use `KaraokeRows(rows=3)` for a measured left/center/right rotation or
`KaraokeRows(rows=2, anchor="top")` for upper harmony. The one-to-eight-row
presets scale margins and inter-row space to script height. For explicit lanes,
`Layout(rows=2, alignment=("center", "right"), offsets=(Vec2(), Vec2(-20, 8)))`
adjusts each row inside the track region. Source singing clocks remain the same.

## One effect entry point

`Track.effects` combines built-ins and custom authoring in one tuple:

- A `LyricRule` selects lyric targets and declares their animation clocks.
- A callable receives a measured `LyricLine` and returns its decorated replacement.
  `LyricHighlights`, `LyricSweep`, `LyricEcho` and `LyricParticles` are callable
  built-ins; an ordinary Python function has the same contract.

Timing rules resolve once from the source before decoration. Callable effects
run once in tuple order. The engine collects all required visibility, allocates
layout once, then binds rules to the final glyphs and their highlight aliases.
Interleaving a rule with callables does not turn it into an immediate animation
or a second evaluator. Overlapping animation channels retain Scene's conflict
rules. Effects must preserve the line's identity; source text/timing stay intact.
For simple custom motion, place a `Transform` in a `LyricRule`; no custom class
or iteration over individual characters is required. For a reusable composition
of decoration functions, `lyric_effects(...)` returns an ordinary callable effect.

## Prepare existing lyrics

This script expects `input.ass` with supported karaoke timing:

```python
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    FadeOut,
    Layout,
    LyricRule,
    LyricSweep,
    ScalePulse,
    Track,
    Vec2,
    prepare_tracks,
)

scene = prepare_tracks(
    Document.load("input.ass"),
    tracks=(
        Track(
            id="main",
            layout=Layout(rows=2, position=Vec2(80, 280), gap=80),
            preview=0.6,
            tail=0.3,
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("syllable", "singing", ScalePulse()),
                LyricRule("line", "exit", FadeOut(), duration=0.2),
                LyricSweep(fill=CYAN, width=0),
            ),
        ),
    ),
)
scene.compile().document.save("output.ass")
```

A rule selects targets and binds a common animation to an anchor. It does not
have its own evaluator. Line fades compose with syllable pulses through the
visual hierarchy. For direct control, a LyricLine supports `animate(...)` just
like a text object or group. Animation factories receive a `LyricAnimationContext` for each resolved interval
before layout, so their durations participate in occupancy. The context exposes
`line`, `target`, `interval` and `duration`; see [duration-aware animation](animation.md#change-parameters-for-each-singing-interval).

After preparation, `line.bind(LyricRule(line.query("ruby"), "singing", Jump()))`
binds a queried collection without a manual target loop. A single LyricTarget is
also accepted. Explicit targets must belong to that line; targets from another
line or a differently identified copy raise before animation factories run. Targets selected
before adding highlight layers resolve to the current visual contributions.
Duplicate targets and descendants of selected ancestors are suppressed, without
reparenting objects. Role/tag queries and empty collections may select nothing,
so a shared ruby rule can safely apply to lines without readings. Unknown roles
raise rather than silently selecting nothing. Direct binding must fit the existing
line lifetime. Inside a Track callable, use `line.schedule(...)` instead to
reserve animation time automatically:

```python
from kara_templater import DriftOut, LyricLine, LyricRule, Transform, Vec2

def drift(line: LyricLine) -> LyricLine:
    return line.schedule(
        LyricRule("character", "singing", Transform(
            scale=lambda p: 1 + 0.06 * 16 * p * p * (1 - p) ** 2,
        )),
        LyricRule("character", "after_singing", DriftOut(offset=Vec2(12, -36)),
                  offset=0.14, duration=0.56),
    )
```

Pass `drift` in `Track.effects`. Scheduling returns a new line; retain or return
that value. Factories resolve once per interval when scheduled, while clip attachment waits
until all decorations and the single layout allocation are complete. Later
highlight layers receive the scheduled animation too. Enter/exit use the final
display window. Calling `schedule` outside Track preparation only records work;
use `bind` for immediate animation on an already allocated Scene line.

## Independent streams and source ownership

Add another Track with its own `id`, source predicate and layout for harmony or
translation. For example, `source=lambda source: source.style == "Harmony"`
selects that style. Tracks allocate independently; two tracks may intentionally
show the same source. Their view IDs remain distinct from the original record's
replacement ownership.

Unmatched events survive. Preparing the same owner again replaces that owner's
generated events; changing selection restores its unselected sources. Inspect
`scene.plans` for source associations, placements and bound lines. `scene.lines`
provides the lyric objects. `LyricSource.from_lyrics(...)` supplies structured
DocumentLyrics through `prepare_tracks(..., inputs=...)` without creating fake
ASS records. Supply those Python inputs again when regenerating.

### Attach a drawing after layout

For a drawing that follows a sung word, iterate over `scene.plans` after
`prepare_tracks`. Each nonempty span in `plan.line.layout.body.singing` gives
absolute song times and decoded text offsets. Pass those offsets to
`body.range_bounds` to get a rectangle in line-local coordinates, including
reserved inline cue space. For a separately added Scene object, add the placed
line's position to that local point. For example, with a stationary lyric line:

```python
body = plan.line.layout.body
box = body.range_bounds(span.start_offset, span.end_offset)
start = plan.line.state.position + Vec2(box.left, box.top + box.height)
life = Lifetime(span.start, span.end)
```

A path born at `life.start` can use `animate(..., at=0, duration=span.end - span.start)`
on its local clock. Skip empty text ranges and zero-length time intervals before
constructing the path. For an animated parent, add the drawing as a child or
use a world-space reference to inherit its motion.

## Allocation is the layout extension point

`Layout(rows=1)`, `Layout(rows=2)` and `Layout(rows=3)` use the same allocator.
The default is strict rotation; `policy="available"` chooses a free row.
Optional preview and tail may shrink to fit, while singing and required animation
occupancy are preserved. Insufficient capacity raises an error.

For a custom policy, override one batch function. This example places lead cues
on their own row, resets rotation, and puts a tagged exception at a fixed point:

```python
from kara_templater import Layout, LayoutContext, LayoutLine, Placement, Vec2

class CustomLayout(Layout):
    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        row = 0
        result = []
        for line in lines:
            if line.lead:
                row = 0
                position = Vec2(80, 180)
            elif "solo" in line.tags:
                position = Vec2(80, 240)
            else:
                position = Vec2(80, 300 + 70 * row)
                row = (row + 1) % 2
            result.append(Placement(line.id, position, line.display))
        return tuple(result)
```

This example deliberately permits overlap and leaves display windows unchanged.
An allocator that needs collision handling can read all measured bounds and
required intervals, then choose its own policy. The engine validates complete
identity mapping and required visibility; it does not run the default allocator
first or overwrite the returned positions. lead and tags are input data, with no
control events, reset hooks or persistent state protocol. Cross-track information
is explicit through Track.references and LayoutContext.other_lines.

The complete [lyric orchestration example](../../examples/lyric_orchestration.py)
uses one song and the same animation declarations for these configurations:

```sh
uv run python -m examples.lyric_orchestration build/layout-one.ass --rows 1
uv run python -m examples.lyric_orchestration build/layout-two.ass --rows 2
uv run python -m examples.lyric_orchestration build/layout-three.ass --rows 3
uv run python -m examples.lyric_orchestration build/layout-custom.ass --custom
uv run python -m examples.lyric_orchestration build/layout-continue.ass --custom --keep-rotation --advance-solo
```

Its `SongLayout.allocate` keeps the cursor and occupancy in ordinary local
variables. `reset_on_lead` and `advance_solo` are choices made by that example's
function, with no engine hooks. The separate harmony Track stays at the top.
In Python, pass your allocator to `build(layout=...)`; the lyric rules remain
unchanged. Add `--dense` to demonstrate overlapping singing: one row reports
insufficient capacity, while two or three rows can accommodate it.

## Semantic targets and appearance

`Track.styles` supplies named ASS styles before text measurement. A style with
an existing name overrides that name for this Track; the source Document remains
unchanged. Font size changes therefore affect the bounds passed to the allocator,
including ruby measurement. Use source style runs for different fonts within a
line. Visual factories run once after measurement, before allocation, on an
unpositioned line. Changing a glyph's font there does not request another text
measurement pass. Layout placement is applied after the factory returns.
For additional geometry, a factory can return an updated `line.layout.bounds`
in line-local pixels to declare its layout footprint. The allocator receives
that box together with reserved inline cue bounds. Dynamic geometry callbacks
are not sampled to guess a footprint; declare a box covering the intended motion.

Appearance composition uses explicit Python factories and immutable replacements.
Apply base role or range appearance first, then select singing colors with
LyricSweep's target factory. Unspecified paint channels retain their base values;
returning `None` skips that target. There is no separate CSS selector cascade.

LyricLine exposes line, syllable, segment, character, ruby and cue targets.
`line.query(...)` selects existing targets without reparenting. Ancestor/descendant
selections are deduplicated. A shared visual pivot can use an explicit group or
an animation factory that converts the same center to each target’s local
coordinates; ordinary whole-line animations need no manually constructed Group.

Syllable targets include their body and ruby children. Use `character` to animate
only body glyphs, or `ruby` for readings. For example,
`LyricRule("character", "singing", FadeOut())` fades the body during its singing
interval while readings keep their local opacity. Both still inherit whole-line
motion and opacity. These rules share the ordinary object hierarchy; selecting
body glyphs does not detach readings or change the source's syllable grouping.
Group opacity multiplies each child's opacity, so a line at 0.6 and a body glyph
at 0.25 produce body opacity 0.15 while an unchanged reading remains at 0.6.

Ruby targets identify shaped glyphs, not a parent group for the entire reading.
To pulse a reading around its center while coloring its glyphs independently,
a rule factory can locate the target in `line.layout.ruby`, take that reading's
`layout.bounds` center, and subtract the glyph's original
`object.state.position`. Pass that local point as `ScalePulse(pivot=..., peak=...)`.
Bind the factory with `LyricRule("ruby", "singing", factory)`. Each glyph retains
the reading's singing clock; LyricSweep also uses the full reading bounds for its
sweep. This changes neither parentage nor the body animation.

LyricSweep provides per-syllable soft color transitions. LyricHighlights provides
named passes with union, priority or layered ownership; HighlightArrival binds
animations to measured character crossings. Factories may choose colors or glow
by target. Python styles and factories construct appearance without embedding
custom runtime tags in the output. See [materials](materials.md),
[animation](animation.md), and [parallel_tracks.py](../../examples/parallel_tracks.py).

All paths compile through Scene. Clip layers, coverage and whole-group RGBA
composition have different blur/alpha semantics and explicit costs. Unsupported
source styles are diagnosed rather than silently discarded; there is no Track
native/editable mode switch. See [compilation](compilation.md) for sampling,
continuous native tween eligibility and budgets.

Visual factories can reserve authored time before allocation. LyricHighlights
adds its absolute pass intervals; GlowFunction.from_animation declares its
local animation interval. Existing object animations and explicit
`line.required_display` intervals also participate. Unknown callback duration
is not inferred by sampling it or by treating every breakpoint as a visibility
requirement; a custom glow can declare `required_interval`, or the factory can
return a line with explicit absolute `required_display` intervals.

Attached decorations with their own lifetimes reserve their visible intervals,
including any time restrictions imposed by independently timed parent groups.
Children sharing the lyric window follow its allocated visibility instead.
Objects in `line.independent` keep their own display windows and do not reserve
the lyric's row; coordinate them explicitly in a custom allocator if needed.

A required effect tail cannot be trimmed to accommodate another lyric. Optional
preview/tail can still shrink. `LyricLine.with_display` preserves existing local
clock origins while changing shared lyric visibility, so trimming preview does
not restart the factory's materials or masks. The factory is not rerun after
allocation; semantic animation rules then bind to its current target aliases.
An early highlighter or attached decoration can also extend the display start.
Existing animation clocks remain fixed, so custom callbacks may receive negative
local seconds before their original origin. Highlight masks and partitions use
their absolute pass times even in that early window.

## Spacing outlined lyrics

Track layout leaves at least 2 script pixels between neighboring horizontal ink
bounds after allowing for the hard outlines. Only pairs that need clearance
move apart. Font spacing, shaping clusters, and existing word spaces are
preserved. The positions stay fixed during pulses. Ruby and inline cues use the
adjusted positions. The singing front skips the added distance.

Set `Track(min_outline_gap=4, ...)` for more separation, or use `None` to keep
the font's original spacing, including overlapping outlines. Zero lets hard
outlines touch. Style outlines and static highlight paint borders contribute to
clearance. Glow, shadow and temporary animation strokes can overlap. For a
custom effect or multiple views drawing the same letters, set
`reserved_border` to the outer hard stroke radius on every view.
