# Lay out vocal tracks

Turn timed lyrics into positioned vocal streams with automatic row rotation, multi-singer separation, character spacing, and vertical Japanese columns. Control where lines appear, how long they stay on screen, and how each voice behaves.

## Build a scene with Track

A `Track` turns selected lyrics from a `Document` into a positioned stream with its own styles, layout, cues, and effects. Pass one or more tracks to `build_lyric_scene` to create a `LyricScene`, then call `scene.preview()` to see the result in a browser or `scene.export()` to package a playback shader.

```python
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    FadeOut,
    Line,
    LyricHighlights,
    LyricRule,
    ScalePulse,
    StatePatch,
    Style,
    Track,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3500, text=r"{\k80}Sing {\k80}out {\k90}loud")
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.2),
                LyricRule("syllable", "timing", ScalePulse()),
                LyricRule("line", "exit", FadeOut(), duration=0.2),
                LyricHighlights.from_timing(StatePatch(fill=CYAN)),
            ),
        ),
    ),
)
scene.export("output.hook")
```

All times on `Track` are in **seconds**. With default settings:

- **Layout**: Omitting `layout` places two rows near the bottom (`KaraokeRows()`), alternating upper-left then lower-right, with short pages pulled evenly toward the center.
- **Preview and tail**: `preview` requests `5.0` s before the first syllable. `tail=None` (automatic) targets `1.0` s from the end of the last syllable to disappearance—including the exit animation—while preferring at least `0.2` s of hold before the exit begins.
- **Crowded row handoffs**: When two lines share a row closely, the incoming line yields extra preview first, then the outgoing hold shrinks toward zero. If the exit and entry animations alone exceed the gap, both speed up proportionally. A zero gap cuts directly between lines. Passing an explicit numeric `tail` overrides this adaptive shrinking; timed syllables and cue windows never move.

To change fonts or sizes for one track without editing the source `Document`, pass `Track(styles=(Style(...),))`. For imported ASS files, override `Default` and `Default-furigana`—layout measurement uses your track styles so font size changes update row heights and ruby placement automatically.

`build_lyric_scene` returns a `LyricScene`, which is an ordinary `Scene` with two inspection attributes: `scene.lines` (the positioned `LyricLine` objects) and `scene.plans` (each `LyricLinePlan` pairs `track_id`, `source`, `layout_request`, `placement`, and `line`). Add extra shapes or backgrounds with `scene.add(...)` before exporting.

## Separate multiple vocal tracks

Add a separate `Track` for each vocal stream—such as lead, harmony, or translation—with a unique `id`, a `source` filter, and its own placement.

```python
from kara_templater import (
    CYAN,
    PINK,
    Document,
    KaraokeEffects,
    KaraokeRows,
    Line,
    Style,
    Track,
    build_lyric_scene,
)

document = Document.create(
    styles=(
        Style(name="Lead", fontname="DejaVu Sans", fontsize=56, shadow=0),
        Style(name="Harmony", fontname="DejaVu Sans", fontsize=38, shadow=0),
    )
)
document.records.extend(
    (
        Line(start_time=1000, end_time=3500, style="Lead", text=r"{\k120}Hold {\k130}on"),
        Line(start_time=1500, end_time=4000, style="Harmony", text=r"{\k250}Ooh"),
    )
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="lead",
            source=lambda s: s.style == "Lead",
            effects=(KaraokeEffects(after_fill=PINK),),
        ),
        Track(
            id="harmony",
            source=lambda s: s.style == "Harmony",
            layout=KaraokeRows(rows=1, anchor="top"),
            effects=(KaraokeEffects(after_fill=CYAN),),
        ),
    ),
)
scene.export("duet.hook")
```

Each track keeps its own row rotation and page clock. Two tracks can intentionally select the same source line—each creates an independent visual view. To supply structured lyrics directly from Python without ASS dialogue records, pass `LyricSource.from_lyrics(..., chapter=...)` through `build_lyric_scene(..., inputs=...)`.

## Read the editable component catalog

Use [`component_catalog()`](../reference/tracks.md#component_catalog) to get JSON-ready declarations for a component picker. Pass the script height to obtain the same defaults and bounds as `compose_track()`. The catalog links editable components to their preferred preview cards when media is available. Open a card's relative media name with [`component_preview_resource()`](../reference/tracks.md#component_preview_resource). Reading the catalog does not render media.

## Row presets and page timing

Use `KaraokeRows` for standard 1-to-8-row karaoke layouts, or `Layout` when you want fixed coordinates, custom alignments, or your own row-assignment rule.

### KaraokeRows presets

`KaraokeRows` scales margins and row spacing from 1080p to your script height and measures every row with its actual body, ruby, and reserved cues. One row centers; three rows use left/center/right; other counts alternate left and right.

| Option | Default | Effect |
| --- | --- | --- |
| `rows` | `2` | Number of rows (1 to 8) or vertical columns |
| `anchor` | `"bottom"` | Vertical placement in `Track.region`: `"top"`, `"center"`, or `"bottom"` |
| `smart_horizontal` | `"equal_margins"` | Pulls short left/right rows inward as a page; `"center_position"` shifts each row independently; `"none"` keeps rows at the margins |
| `section_gap` | `4.0` | Silence (seconds) that starts a fresh section and row rotation (`0` disables) |
| `lane_gap` | `0.3` | Preferred gap (seconds) before the next line reuses a row |
| `sync_entry` | `True` | Brings all lines on a section's first page on screen together |
| `sync_ending` | `False` | Exits all lines on a section's last page together |
| `sync_each_page` | `False` | Applies enabled synchronization to every page, not just the first/last |
| `fill_section` | `True` | Holds each row until `lane_gap` before its next occupant and aligns final-page tails |
| `reset_on_lead` | `True` | Restarts at the first row on a lead cue or chapter change |

On a lone line, `smart_horizontal` centers the line automatically. In a bottom three-row preset, a two-line page occupies the lower two rows and aligns both lines to the right. To schedule each line's preview and tail completely independently, set `KaraokeRows(sync_entry=False, fill_section=False)`.

To trigger a page or section break from source metadata—such as an actor named `verse-start`—subclass `KaraokeRows` and override `break_before`:

```python
from typing import Literal

from kara_templater import KaraokeRows, LineLayoutRequest, Track


class VerseRows(KaraokeRows):
    def break_before(
        self, previous: LineLayoutRequest, line: LineLayoutRequest
    ) -> Literal["none", "page", "section"]:
        if "verse-start" in line.tags:
            return "section"
        return super().break_before(previous, line)


main = Track(
    id="main",
    layout=VerseRows(),
    tags=lambda source: frozenset((source.actor,)),
)
```

Returning `"section"` starts a fresh first page with synchronized previews; `"page"` restarts row placement inside the current section; `"none"` keeps normal paging.

### Fixed lanes and custom layouts

Use `Layout` when you want explicit coordinates, per-row alignments, or a custom row-assignment algorithm:

```python
from kara_templater import Layout, Vec2

lanes = Layout(
    rows=2,
    position=Vec2(80, 520),
    alignment=("center", "right"),
    offsets=(Vec2(), Vec2(-20, 8)),
    policy="available",
)
```

- **Row spacing**: Omitting `gap` measures the co-visible rows (including ruby) and adds 20% of the largest body font size between them. Passing a numeric `gap` sets a fixed row-origin pitch in script pixels.
- **Row selection**: `policy="strict"` (default) rotates strictly through rows; `policy="available"` picks the next free row. `reset_after` restarts rotation after a silence in seconds; `reset_on_lead=False` keeps rotating across lead cues and chapter changes.
- **Custom allocation**: Subclass `Layout` and override `allocate(lines, context)` when a song needs bespoke rules (such as pulling solo lines out of rotation). Call `self.row_offsets(lines, placements)` to place numbered rows with measured clearances. Pass another track's requests through `Track.references` to read them from `context.other_lines`. See [lyric_orchestration.py](../../examples/lyric_orchestration.py) for a complete working example.

## Combine effects and attach drawings

`Track.effects` accepts a single tuple combining `LyricRule` entries and callable effects (`KaraokeEffects`, `LyricHighlights`, `LyricEcho`, `LyricParticles`, `lyric_effects(...)`, or your own function taking and returning a `LyricLine`).

1. Rules resolve their timing windows once from the source lyrics.
2. Callables run in tuple order on each measured, unpositioned line before layout.
3. Layout reserves every required display interval—from rules, highlight passes, child object lifetimes, and `line.required_display`—then positions the line once. (Objects in `line.independent` keep their own lifetimes and do not block the lyric's row.)
4. Rules attach to the final glyphs and any highlight layers created by callables.

If you write a custom callable effect for `Track.effects`, schedule animations with `line.schedule(...)` so their durations participate in row layout and apply to later highlight layers:

```python
from kara_templater import DriftOut, LyricLine, LyricRule, Transform, Vec2


def drift(line: LyricLine) -> LyricLine:
    return line.schedule(
        LyricRule(
            "character",
            "timing",
            Transform(scale=lambda p: 1 + 0.06 * 16 * p * p * (1 - p) ** 2),
        ),
        LyricRule(
            "character",
            "after_timing",
            DriftOut(offset=Vec2(12, -36)),
            offset=0.14,
            duration=0.56,
        ),
    )
```

Outside `Track.effects` (on an already laid-out line from `scene.lines`), use `line.bind(...)` or `line.animate(...)` instead; direct bindings must fit inside the line's allocated lifetime.

`LyricRule` and `line.query(...)` select targets by role: `"line"`, `"syllable"` (body plus its ruby), `"segment"` (each repeated timing interval), `"character"` (body glyphs only), `"ruby"` (individual reading glyphs), and `"cue"`. Duplicate targets and descendants of selected ancestors are ignored automatically, and empty queries (such as `"ruby"` on a line without readings) are safe no-ops. Group opacity multiplies child opacity. If you want to pulse an entire reading around one center, compute the local pivot from `line.layout.ruby` inside a rule factory.

If a custom callable adds decorations beyond the measured text box, return an updated `line.layout.bounds` in line-local pixels so row layout leaves room for them. See [Built-in karaoke effects](karaoke-effects.md) and [Animation and timing](animation.md) for effect details.

### Attach a drawing to a timed word

After `build_lyric_scene`, iterate over `scene.plans` to position extra scene objects against measured lyric spans:

```python
from kara_templater import (
    PINK,
    Document,
    Lifetime,
    Line,
    PathObject,
    Style,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3000, text=r"{\k100}Star {\k100}light")
)
scene = build_lyric_scene(document, tracks=(Track(id="main"),))

for plan in scene.plans:
    body = plan.line.layout.body
    for index, span in enumerate(body.timing):
        if span.end <= span.start or span.end_offset <= span.start_offset:
            continue
        box = body.range_bounds(span.start_offset, span.end_offset)
        origin = plan.line.state.position + Vec2(box.left, box.top + box.height + 6)
        scene.add(
            PathObject(
                id=f"{plan.line.id}/underline/{index}",
                lifetime=Lifetime(span.start, span.end),
                path=VectorPath.rectangle(box.width, 4),
                state=VisualState(position=origin, fill=PINK),
            )
        )

scene.export("underlines.hook")
```

Skip empty text ranges and zero-length intervals before creating a path. If the lyric line itself moves, add the drawing as a child of the line or follow it with a reference instead of adding a static `position`.

## Character spacing and outline clearance

By default, `KaraokeRows` measures each character cell from its visible ink, side bearings, and primary outline (Studio spacing), unless `palt=True` is set. A plain `Layout` uses native font advances. Override either choice with `Track(studio_spacing=True)` or `False`.

To tune Studio cell spacing, pass `StudioSpacing`:

```python
from kara_templater import StudioSpacing, Track

spaced = Track(
    id="main",
    studio_spacing=StudioSpacing(space_width_percent=50, allow_biting=True),
)
```

- `space_width_percent` sets ASCII space width as a percentage of the font's em (10 to 100; default `20`).
- `allow_biting=True` keeps negative side bearings so italic letters can tuck closer together (default `False`).

After cell measurement, `Track` checks neighboring hard outlines (both in body text and between kana in a reading):

- `min_outline_gap=0` (default) lets adjacent hard outlines touch and inserts space only where they would overlap.
- Set `min_outline_gap=4` to keep at least 4 script pixels between outlines, or `None` to disable outline adjustment.
- Set `reserved_border` to your outer hard stroke radius when custom layers draw a thicker hard border than the style declares. Glow, shadow, and temporary animation strokes do not add spacing.

For horizontal proportional kana spacing, see [Choose and register fonts](fonts.md#enable-proportional-kana-spacing). For right-to-left scripts or reversed karaoke wipes, set `Track(right_to_left=True)` to lay out cells right to left, or `Track(reverse_timing=True)` (also accepts a per-line predicate) to assign timed windows in reverse spatial order.

## Vertical Japanese lyrics

Set `vertical=True` on a `Track` for top-to-bottom karaoke wipes across right-to-left columns:

```python
from kara_templater import Document, KaraokeEffects, KaraokeRows, Line, Style, Track, build_lyric_scene

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=52, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=3500, text=r"{\k80}風|かぜ{\k80}の{\k90}歌|うた")
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            vertical=True,
            layout=KaraokeRows(rows=3, anchor="top"),
            effects=(KaraokeEffects(),),
        ),
    ),
)
scene.export("vertical.hook")
```

Key vertical layout details:

- Omitting `layout` alternates two columns right to left. Pass `KaraokeRows(rows=1)` for one column or `rows=3` for three. `anchor` aligns each column vertically; partial pages start on the right. `break_before` and page timing options work the same as for horizontal tracks.
- Long vowel marks (`ー`) and brackets rotate around their cell center. Ruby sits to the right of its body cells, separated by `ruby_gap` script pixels.
- `highlight="no_wipe"` switches the whole timed unit to the sung color at its onset.
- Whole-column transitions (`fade`, `rise`, `slide_in`, `slide_out`) animate the column including ruby. Character transitions, timing particles, and stroke flashes have no effect in vertical mode, though custom `LyricRule` animations still apply.
- Built-in `SignalCue` lamps and `VolumeCue` columns are horizontal-only. For vertical guide markers, map timed placeholder characters through `Track.guide_symbols`; see [Ruby readings and cues](text-and-cues.md#sing-an-inline-vector-symbol).

## Render a short preview interval

When iterating on one section of a long song, pass `preview_interval=(start, end)` in absolute seconds to `build_lyric_scene`:

```python
from kara_templater import Document, KaraokeEffects, Line, Style, Track, build_lyric_scene

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=54, shadow=0),)
)
document.records.extend(
    (
        Line(start_time=1000, end_time=3000, text=r"{\k200}First"),
        Line(start_time=12000, end_time=15000, text=r"{\k300}Chorus"),
    )
)

scene = build_lyric_scene(
    document,
    tracks=(Track(id="main", effects=(KaraokeEffects(),)),),
    preview_interval=(10.0, 16.0),
)
scene.export("preview.hook", start=10.0, duration=6.0)
```

Keep the full song's lines in `document` (and `inputs`). Track layout preserves row rotation, neighboring handoffs, and co-visible row heights, returning only lines and independent cues that intersect the preview window. Omit `preview_interval` (or pass `None`) for a full export or when your script inspects lyric objects outside the window.

## Next steps

- [Ruby readings and cues](text-and-cues.md)
- [Built-in karaoke effects](karaoke-effects.md)
- [Design a song layout](../tutorials/karaoke-design.md)
- [Track authoring API reference](../reference/tracks.md)
