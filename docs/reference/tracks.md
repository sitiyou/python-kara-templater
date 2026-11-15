# Track authoring

Reusable lyric configuration prepared as editable or native Scene content. Singing and display source clocks stay separate. See [Tracks](../guides/tracks.md).

[All public symbols](README.md#symbol-index)

## Contents

- [DoubleLine](#doubleline)
- [HighlightStyle](#highlightstyle)
- [KaraokeItem](#karaokeitem)
- [Layout](#layout)
- [LineMatch](#linematch)
- [Overlay](#overlay)
- [PreparedTracks](#preparedtracks)
- [RenderEstimate](#renderestimate)
- [SingleLine](#singleline)
- [SourceMatch](#sourcematch)
- [Sweep](#sweep)
- [Track](#track)
- [TrackGroup](#trackgroup)
- [prepare_tracks](#prepare_tracks)

## DoubleLine

Allocate two alternating lyric rows with explicit position and gap.

TrackGroup can share this allocation across independently selected children.

[Source](../../kara_templater/track_layout.py#L100)

```python
DoubleLine(
    *,
    position: tuple[float, float] | None = None,
    gap: float = 120,
)
```

### DoubleLine.allocate

Assign source items to rows without modifying their lyric text or singing clocks.

```python
DoubleLine.allocate(
    items: tuple[KaraokeItem, ...],
) -> dict[str, int]
```

### DoubleLine.place

Apply the configured row placement to a measured lyric line.

```python
DoubleLine.place(
    layout: LaidOutLine,
    row: int,
) -> LaidOutLine
```

## HighlightStyle

Paint and priority for one explicitly named HighlightTrack.

``after=None`` uses the lyric's sung paint. Larger priority wins when an
Overlay uses priority composition; layer composition retains stack order.

[Source](../../kara_templater/karaoke.py#L59)

```python
HighlightStyle(
    track_id: str,
    after: Paint | None = None,
    priority: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `track_id` | `str` | `required` |
| `after` | `Paint \| None` | `None` |
| `priority` | `int` | `0` |

## KaraokeItem

Structured lyrics with a stable identity and a millisecond display window.

``style`` names a Document style. ``ruby_style`` selects an explicit reading
style; otherwise the frontend uses or creates ``style + '-ruby'``. Positive
``margins`` override left, right, and vertical source margins respectively.

[Source](../../kara_templater/karaoke.py#L11)

```python
KaraokeItem(
    id: str,
    source: KaraokeLine,
    style: str,
    window: DisplayWindow,
    ruby_style: str | None = None,
    margins: tuple[int, int, int] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `source` | `KaraokeLine` | `required` |
| `style` | `str` | `required` |
| `window` | `DisplayWindow` | `required` |
| `ruby_style` | `str \| None` | `None` |
| `margins` | `tuple[int, int, int] \| None` | `None` |

## Layout

Base interface for reusable lyric row allocation and placement.

Explicit layouts operate on measured lines without changing source text or
singing clocks.

[Source](../../kara_templater/track_layout.py#L10)

```python
Layout(
    *,
    rows: int = 1,
    position: tuple[float, float] | None = None,
    gap: float = 120,
)
```

### Layout.allocate

Assign source items to rows without modifying their lyric text or singing clocks.

```python
Layout.allocate(
    items: tuple[KaraokeItem, ...],
) -> dict[str, int]
```

### Layout.place

Apply the configured row placement to a measured lyric line.

```python
Layout.place(
    layout: LaidOutLine,
    row: int,
) -> LaidOutLine
```

## LineMatch

Select lyric items by optional exact source style and body text.

Both specified criteria must match.

[Source](../../kara_templater/matching.py#L22)

```python
LineMatch(
    *,
    style: str | None = None,
    text: str | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `style` | `str \| None` | `None` |
| `text` | `str \| None` | `None` |

### LineMatch.__call__

Whether the source item satisfies all supplied exact style/text criteria.

```python
LineMatch.__call__(
    item: KaraokeItem,
) -> bool
```

## Overlay

A sung paint/reveal declaration for Body and Ruby roles.

Optional named highlights, styles, and overlap policy provide explicit parallel
composition.

[Source](../../kara_templater/track.py#L28)

```python
Overlay(
    *,
    style: PaintStyle = PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET),
    reveal: Sweep = Sweep(progress_curve=ProgressCurve(knots=((0, 0), (1, 1))), edges=EdgeSweep(padding_px=0, lead_ms=0, tail_ms=0), completion='release'),
    targets: tuple[type[Body] | type[Ruby], ...] | None = None,
    body: PaintStyle | None | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    ruby: PaintStyle | None | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    highlights: tuple[HighlightTrack, ...] | Callable[[LaidOutLine], tuple[HighlightTrack, ...]] | None = None,
    styles: tuple[HighlightStyle, ...] = (),
    overlap: Literal['union', 'priority', 'layer'] = 'union',
)
```

### Overlay.enabled

Whether this overlay applies to the requested Body or Ruby role.

```python
Overlay.enabled(
    role: type[Body] | type[Ruby],
) -> bool
```

### Overlay.resolve

Resolve shared and role-specific sung paint against the selected base Paint.

```python
Overlay.resolve(
    role: type[Body] | type[Ruby],
    base: Paint,
) -> Paint
```

## PreparedTracks

A composable Scene with Track preparation diagnostics and layer count.

Native preparation lowers callbacks before returning. Editable preparation
defers their evaluation until Scene compilation. Both retain source records
and support adding independent Scene objects before compilation.

[Source](../../kara_templater/render.py#L58)

```python
PreparedTracks(
    scene: Scene,
    diagnostics: tuple[str, ...],
    layer_count: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `scene` | `Scene` | `required` |
| `diagnostics` | `tuple[str, ...]` | `required` |
| `layer_count` | `int` | `required` |

### PreparedTracks.compile

Compile through Scene, including frontend diagnostics in the result.

```python
PreparedTracks.compile(
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
) -> SceneResult
```

## RenderEstimate

Document cost before property callbacks; sampling counts precede merging.

Native curve subdivision can increase the final count. This is neither an
exact total nor an upper bound; the compiler enforces the final event limit.

[Source](../../kara_templater/render.py#L25)

```python
RenderEstimate(
    static_events: int,
    sampling: tuple[SamplingEstimate, ...],
    event_limit: int,
    raster: tuple[RasterEstimate, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `static_events` | `int` | `required` |
| `sampling` | `tuple[SamplingEstimate, ...]` | `required` |
| `event_limit` | `int` | `required` |
| `raster` | `tuple[RasterEstimate, ...]` | `()` |

### RenderEstimate.estimated_events

Sum static, sampled, and raster estimates before merging and native subdivision.

This is not a final upper bound.

Type: `int`.

### RenderEstimate.target_samples

Total declared target samples across native dynamic and raster preparations.

Type: `int`.

## SingleLine

Place selected lyric lines on one configured row.

Omitted position retains source positioning; explicit offsets and layout
settings affect presentation only.

[Source](../../kara_templater/track_layout.py#L89)

```python
SingleLine(
    *,
    position: tuple[float, float] | None = None,
)
```

### SingleLine.allocate

Assign source items to rows without modifying their lyric text or singing clocks.

```python
SingleLine.allocate(
    items: tuple[KaraokeItem, ...],
) -> dict[str, int]
```

### SingleLine.place

Apply the configured row placement to a measured lyric line.

```python
SingleLine.place(
    layout: LaidOutLine,
    row: int,
) -> LaidOutLine
```

## SourceMatch

A callable predicate selecting a KaraokeItem.

Ordinary typed functions can provide domain-specific selection.

[Source](../../kara_templater/matching.py#L11)

### SourceMatch.__call__

Whether this source item is selected by the predicate.

```python
SourceMatch.__call__(
    item: KaraokeItem,
    /,
) -> bool
```

## Sweep

Highlight progress and completion behavior.

A progress curve maps singing time to a horizontal cursor. ``release``
removes a completed sweep's clip after the singing interval, exposing the
full sung decoration. ``clip`` retains clipping through the display window. Edge
compensation is for low-level spans; Track overlays use uncompensated edges.

[Source](../../kara_templater/karaoke.py#L36)

```python
Sweep(
    progress_curve: ProgressCurve = ProgressCurve(knots=((0, 0), (1, 1))),
    edges: EdgeSweep = EdgeSweep(padding_px=0, lead_ms=0, tail_ms=0),
    completion: Literal['release', 'clip'] = 'release',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `progress_curve` | `ProgressCurve` | `ProgressCurve(knots=((0, 0), (1, 1)))` |
| `edges` | `EdgeSweep` | `EdgeSweep(padding_px=0, lead_ms=0, tail_ms=0)` |
| `completion` | `Literal['release', 'clip']` | `'release'` |

## Track

Reusable lyric selection, body/ruby appearance, overlay, layout, and animation declarations.

prepare_tracks binds a fresh configuration per source and produces composable
Scene content.

[Source](../../kara_templater/track.py#L89)

```python
Track(
    *,
    source: SourceMatch,
    body: Body | None = None,
    ruby: Ruby | None = None,
    overlay: Overlay | None = None,
    layout: Layout | None = None,
    animations: Iterable[Animation] = (),
    sampling: SamplingSettings = SamplingSettings(step_ms=40, max_samples=100000),
    styles: StyleSheet | None = None,
)
```

### Track.bind

Bind fresh Track configurations to structured source items for internal/backend inspection.

Use prepare_tracks for normal Document authoring.

```python
Track.bind(
    items: tuple[KaraokeItem, ...],
) -> dict[str, BoundTrack]
```

## TrackGroup

Explicit shared row allocation for independently configured tracks.

Children keep their source selectors, styles and animations. The group owns
placement; children must omit layout. A shared absolute origin is required
so different input style positions cannot move the allocated rows apart.

[Source](../../kara_templater/track.py#L131)

```python
TrackGroup(
    *tracks: Track,
    layout: Layout,
)
```

### TrackGroup.bind

Bind child configurations with shared row allocation for internal/backend inspection.

```python
TrackGroup.bind(
    items: tuple[KaraokeItem, ...],
) -> dict[str, BoundTrack]
```

## prepare_tracks

Bind lyric configurations to a Scene while preserving unselected records.

``editable`` produces ObjectGroups whose callbacks run during compilation;
SceneBudget controls sampling. ``native`` lowers to NativeEvents, retains
native interpolation/style semantics, and uses Track.sampling for callbacks.
Explicit raster settings require native mode; material coverage is exposed
separately by prepare_track_coverage. Source times and margins use milliseconds.

[Source](../../kara_templater/render.py#L81)

```python
prepare_tracks(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    tracks: tuple[Track | TrackGroup, ...],
    mode: Literal['editable', 'native'] = 'editable',
    owner: str = 'default',
    settings: OutputSettings | None = None,
    import_settings: ImportSettings | None = None,
    on_estimate: Callable[[RenderEstimate], None] | None = None,
    max_objects: int = 25000,
) -> PreparedTracks
```
