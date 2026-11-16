# Track authoring

Independent lyric streams, allocation and semantic bindings into one Scene. Singing, display and animation clocks use seconds and stay separate. See [Tracks](../guides/tracks.md).

[All public symbols](README.md#symbol-index)

## Contents

- [KaraokeItem](#karaokeitem)
- [Layout](#layout)
- [LayoutContext](#layoutcontext)
- [LayoutLine](#layoutline)
- [LinePlan](#lineplan)
- [LyricAnchor](#lyricanchor)
- [LyricLine](#lyricline)
- [LyricRole](#lyricrole)
- [LyricRule](#lyricrule)
- [LyricScene](#lyricscene)
- [LyricSource](#lyricsource)
- [LyricTarget](#lyrictarget)
- [Placement](#placement)
- [Track](#track)
- [prepare_tracks](#prepare_tracks)

## KaraokeItem

Structured lyrics with a stable identity and a millisecond display window.

``style`` names a Document style. ``ruby_style`` selects an explicit reading
style; otherwise the frontend uses or creates ``style + '-ruby'``. Positive
``margins`` override left, right, and vertical source margins respectively.

[Source](../../kara_templater/karaoke.py#L9)

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

Allocate any positive number of rows, or override allocate entirely.

Strict rotation is the default. 'available' searches from the next row for
capacity. Optional preview/tail is shortened before required singing or
animation could overlap. reset_after resets rotation after a singing gap;
None preserves rotation across pauses. Lead and tags have no built-in meaning.

position is the first row's top-left, defaulting to the context region.
alignment controls horizontal alignment within that region. Bounds already
include ruby and inline cue reservations. gap is row-origin spacing in pixels.

[Source](../../kara_templater/lyric_layout.py#L149)

```python
Layout(
    *,
    rows: int = 1,
    position: Vec2 | None = None,
    gap: float = 120,
    alignment: Literal['left', 'center', 'right'] = 'left',
    policy: Literal['strict', 'available'] = 'strict',
    reset_after: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `rows` | `int` | `1` |
| `position` | `Vec2 \| None` | `None` |
| `gap` | `float` | `120` |
| `alignment` | `Literal['left', 'center', 'right']` | `'left'` |
| `policy` | `Literal['strict', 'available']` | `'strict'` |
| `reset_after` | `float \| None` | `None` |

### Layout.allocate

Plan the complete batch once, without modifying singing or input order.

Chronological input is required; equal starts retain input order. For a
handoff, shorten the prior tail first, then the next preview. Required
intervals that cannot fit raise with both line identities and the row.

```python
Layout.allocate(
    lines: tuple[LayoutLine, ...],
    context: LayoutContext,
) -> tuple[Placement, ...]
```

## LayoutContext

Read-only placement region and explicitly supplied cross-track references.

Other tracks are information for overrides, never implicitly allocated by the
built-in algorithm. Coordinates and measurements use script pixels.

[Source](../../kara_templater/lyric_layout.py#L80)

```python
LayoutContext(
    region: Box,
    other_lines: tuple[LayoutLine, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `region` | `Box` | `required` |
| `other_lines` | `tuple[LayoutLine, ...]` | `()` |

## LayoutLine

Immutable measured input, with original singing and desired visibility.

entrance/exit are required animation durations in seconds, outside singing.
display includes optional preview/tail and any explicitly reserved cue time.
tags and cue markers carry source data; their layout meaning is user-defined.
bounds includes body, ruby and reserved inline decorations in local pixels.

[Source](../../kara_templater/lyric_layout.py#L18)

```python
LayoutLine(
    *,
    id: str,
    singing: TimeSpan,
    display: Lifetime,
    bounds: Box,
    entrance: float = 0,
    exit: float = 0,
    sources: tuple[SourceRef, ...] = (),
    tags: frozenset[str] = frozenset({}),
    cues: tuple[CueMarker, ...] = (),
    lead: bool = False,
    reserved: Lifetime | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `singing` | `TimeSpan` | `required` |
| `display` | `Lifetime` | `required` |
| `bounds` | `Box` | `required` |
| `entrance` | `float` | `0` |
| `exit` | `float` | `0` |
| `sources` | `tuple[SourceRef, ...]` | `()` |
| `tags` | `frozenset[str]` | `frozenset({})` |
| `cues` | `tuple[CueMarker, ...]` | `()` |
| `lead` | `bool` | `False` |
| `reserved` | `Lifetime \| None` | `None` |

### LayoutLine.required

The minimum interval containing singing and entrance/exit animation.

Type: `TimeSpan`.

## LinePlan

Inspectable source/view association and final layout/animation binding.

[Source](../../kara_templater/orchestration.py#L125)

```python
LinePlan(
    track_id: str,
    source: LyricSource,
    input: LayoutLine,
    placement: Placement,
    line: LyricLine,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `track_id` | `str` | `required` |
| `source` | `LyricSource` | `required` |
| `input` | `LayoutLine` | `required` |
| `placement` | `Placement` | `required` |
| `line` | `LyricLine` | `required` |

## LyricAnchor

Public type alias:

```python
type LyricAnchor = Literal['enter', 'exit', 'singing']
```

## LyricLine

An editable lyric line, with the same animate method as any visual node.

Body and ruby belong to syllable groups, so whole-line and syllable animation
compose through the ordinary Scene hierarchy. query is a logical selection;
it never reparents objects. The original measured layout remains available.
required_display declares absolute-seconds visual intervals for allocation;
it does not move the original singing clocks or create animation events.

[Source](../../kara_templater/lyric_line.py#L153)

```python
LyricLine(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    children: tuple[SceneObject, ...],
    coverage: Coverage | None = None,
    layout: LyricLayout,
    targets: tuple[LyricTarget, ...],
    independent: tuple[ObjectGroup, ...] = (),
    required_display: tuple[TimeSpan, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `children` | `tuple[SceneObject, ...]` | `required` |
| `coverage` | `Coverage \| None` | `None` |
| `layout` | `LyricLayout` | `required` |
| `targets` | `tuple[LyricTarget, ...]` | `required` |
| `independent` | `tuple[ObjectGroup, ...]` | `()` |
| `required_display` | `tuple[TimeSpan, ...]` | `()` |

### LyricLine.animate

Return a new node with an animation bound at local seconds from birth.

The same operation works on text, paths and groups. Existing clips are
preserved; conflicting channels or a clip beyond the lifetime raise
before changing anything. Use a timeline for longer schedules.

```python
LyricLine.animate(
    animation: StateAnimation,
    *,
    duration: float,
    at: float = 0,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Self
```

### LyricLine.at

Evaluate this object at absolute seconds using its local animation clock.

Use SceneEvaluator for parent transforms and references.

```python
LyricLine.at(
    time: float,
) -> VisualState
```

### LyricLine.bind

Resolve factories and semantic clocks into ordinary immutable clips.

Sequences retain their authored seconds length unless duration overrides
it. Unspecified pure animations use the singing interval length. Missing
targets and zero-duration intervals do not invent animation time.

```python
LyricLine.bind(
    *rules: LyricRule,
) -> LyricLine
```

### LyricLine.copy

Copy visuals and retarget semantic identities, retaining original source.

delay shifts visual anchors and lifetimes, never edits the source singing
spans. offset moves the lyric group; independently positioned cues retain
their own positions. Already-bound animations retain their local clocks.

```python
LyricLine.copy(
    *,
    id: str,
    offset: Vec2 | None = None,
    delay: float = 0,
) -> Self
```

### LyricLine.from_layout

Build a line from shaped text, retaining repeat and ruby associations.

Independent syllable animation requires boundaries that do not split a
shaping cluster. Such boundaries fail explicitly, never split codepoints.

```python
LyricLine.from_layout(
    layout: LyricLayout,
    *,
    tags: frozenset[str] = frozenset({}),
    inline: tuple[ObjectGroup, ...] = (),
    independent: tuple[ObjectGroup, ...] = (),
) -> LyricLine
```

### LyricLine.objects

The line and its independently positioned cues for Scene.add.

Type: `tuple[ObjectGroup, ...]`.

### LyricLine.query

Select roles/tags without changing hierarchy; ancestors win over children.

Multiple segment identities sharing one node are retained for their
separate clocks. An explicitly selected ancestor suppresses descendants
so a bulk transform cannot be applied twice through parent inheritance.

```python
LyricLine.query(
    *roles: LyricRole,
    tags: frozenset[str] = frozenset({}),
) -> tuple[LyricTarget, ...]
```

### LyricLine.time_origin

Absolute seconds origin for local animation, geometry and paint clocks.

Type: `float`.

### LyricLine.with_display

Change shared lyric visibility while preserving all existing local clocks.

Nodes with this line's original window follow the change. Independently
timed decorations and independent cues retain their own windows.

```python
LyricLine.with_display(
    display: Lifetime,
) -> LyricLine
```

## LyricRole

Public type alias:

```python
type LyricRole = Literal['line', 'syllable', 'segment', 'character', 'ruby', 'cue']
```

## LyricRule

Bind a common animation to selected lyric nodes at a semantic anchor.

enter/exit use the node's display start/end; exit ends at the anchor.
singing binds each selected singing interval. An omitted duration uses a
sequence's authored length, or otherwise the singing interval's length.
A factory receives the measured line and selected semantic target once,
before layout, and returns the same animation protocol as direct authoring.
offset is relative seconds; display-anchor factories must return a sequence
when duration is omitted.
A callable anchor receives the measured line and target and returns absolute
second intervals, before layout occupancy is allocated. This permits custom
arrival clocks without adding another animation evaluator. Returned intervals
already include any visual copy delay.
No state interpolation or ASS encoding occurs in this declaration.
target accepts a role, a queried semantic target, or a tuple of targets.
Explicit targets must belong to the receiving line; current aliases are
resolved at binding. Duplicate selections and selected descendants are
suppressed. Role/tag queries and empty tuples may select nothing.

[Source](../../kara_templater/lyric_line.py#L46)

```python
LyricRule(
    target: LyricRole | LyricTarget | tuple[LyricTarget, ...],
    anchor: LyricAnchor | LyricTarget | Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]],
    animation: StateAnimation | Callable[[LyricLine, LyricTarget], StateAnimation],
    duration: float | None = None,
    offset: float = 0,
    hold: bool = True,
    tags: frozenset[str] = frozenset({}),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `LyricRole \| LyricTarget \| tuple[LyricTarget, ...]` | `required` |
| `anchor` | `LyricAnchor \| LyricTarget \| Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]]` | `required` |
| `animation` | `StateAnimation \| Callable[[LyricLine, LyricTarget], StateAnimation]` | `required` |
| `duration` | `float \| None` | `None` |
| `offset` | `float` | `0` |
| `hold` | `bool` | `True` |
| `tags` | `frozenset[str]` | `frozenset({})` |

### LyricRule.singing_intervals

Resolve source clocks, optionally from an explicit other-track target.

A referenced target is an immutable snapshot of its source singing and
visual delay, independent of input ordering or runtime evaluation order.
Display anchors are resolved separately from the actual target lifetime.

```python
LyricRule.singing_intervals(
    target: LyricTarget,
) -> tuple[TimeSpan, ...]
```

## LyricScene

A normal Scene with immutable lyric arrangement snapshots for inspection.

[Source](../../kara_templater/orchestration.py#L136)

```python
LyricScene(
    document: Document,
    objects: list[SceneObject | NativeEvent] = _HAS_DEFAULT_FACTORY_CLASS(),
    replace_records: set[int] = _HAS_DEFAULT_FACTORY_CLASS(),
    owner: str = 'scene',
    plans: tuple[LinePlan, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `document` | `Document` | `required` |
| `objects` | `list[SceneObject \| NativeEvent]` | `list()` |
| `replace_records` | `set[int]` | `set()` |
| `owner` | `str` | `'scene'` |
| `plans` | `tuple[LinePlan, ...]` | `()` |

### LyricScene.add

Append typed visual/native objects and return this Scene for composition.

```python
LyricScene.add(
    *objects: SceneObject | NativeEvent,
) -> Self
```

### LyricScene.compile

Compile a new ASS Document and reports under explicit Scene budgets.

Eligible continuous Tween lowering is opt-in.
on_estimate runs after preflight and before frame callbacks; raising
cancels compilation without changing the scene or source document.

```python
LyricScene.compile(
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
    on_estimate: Callable[[SceneEstimate], None] | None = None,
) -> SceneResult
```

### LyricScene.evaluator

Construct a seekable world-space evaluator for this scene hierarchy and its references.

```python
LyricScene.evaluator() -> SceneEvaluator
```

### LyricScene.lines

The bound lyric lines in track/source order.

Type: `tuple[LyricLine, ...]`.

### LyricScene.replace_source

Mark a valid source event record for retention as a Comment during compilation.

```python
LyricScene.replace_source(
    record_index: int,
) -> None
```

## LyricSource

An immutable source view used by Track predicates and metadata functions.

id identifies source content independently of its track/view. Original
singing intervals remain in lyrics; display is the original ASS visibility.

[Source](../../kara_templater/orchestration.py#L36)

```python
LyricSource(
    id: str,
    record_index: int | None,
    style: str,
    actor: str,
    effect: str,
    display: Lifetime,
    text_data: DocumentText,
    projection: DocumentLyrics | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `record_index` | `int \| None` | `required` |
| `style` | `str` | `required` |
| `actor` | `str` | `required` |
| `effect` | `str` | `required` |
| `display` | `Lifetime` | `required` |
| `text_data` | `DocumentText` | `required` |
| `projection` | `DocumentLyrics \| None` | `None` |

### LyricSource.from_lyrics

Create a structured source without synthesizing or replacing ASS records.

The projection retains full-precision singing, appearance runs, ruby and
cues. Regeneration requires supplying this source again; ASS output does
not embed Python data or private serialization.

```python
LyricSource.from_lyrics(
    id: str,
    lyrics: DocumentLyrics,
    *,
    display: Lifetime,
    style: str = 'Default',
    actor: str = '',
    effect: str = '',
) -> LyricSource
```

### LyricSource.lyrics

Project selected lyrics lazily; unselected raw events need no support.

Type: `DocumentLyrics`.

### LyricSource.text

Decoded body text, excluding ruby and custom markup.

Type: `str`.

## LyricTarget

Stable semantic identity referring to an existing visual node.

Several repeated singing segments may refer to the same body node. Selecting
them never creates copies or changes visual parentage. singing retains the
original absolute seconds and decoded text offsets.

[Source](../../kara_templater/lyric_line.py#L28)

```python
LyricTarget(
    id: str,
    node_id: str,
    role: LyricRole,
    singing: tuple[SingingSpan, ...] = (),
    tags: frozenset[str] = frozenset({}),
    delay: float = 0,
    aliases: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `node_id` | `str` | `required` |
| `role` | `LyricRole` | `required` |
| `singing` | `tuple[SingingSpan, ...]` | `()` |
| `tags` | `frozenset[str]` | `frozenset({})` |
| `delay` | `float` | `0` |
| `aliases` | `tuple[str, ...]` | `()` |

## Placement

A visual origin and absolute display interval for one stable line id.

row is optional metadata; free-form layouts do not need numbered slots.
adjustments explains deliberate changes to desired visibility.

[Source](../../kara_templater/lyric_layout.py#L97)

```python
Placement(
    id: str,
    position: Vec2,
    display: Lifetime,
    row: int | None = None,
    adjustments: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `position` | `Vec2` | `required` |
| `display` | `Lifetime` | `required` |
| `row` | `int \| None` | `None` |
| `adjustments` | `tuple[str, ...]` | `()` |

## Track

An independent lyric stream with selection, placement and binding rules.

All times use seconds. preview/tail are desired, reducible display padding;
rule durations and inline cue visibility are mandatory occupancy. The visual
factory receives the measured, unpositioned line once before allocation.
Authored visual intervals join occupancy; rule binding follows allocation.
All animation evaluation and output belong to Scene.

[Source](../../kara_templater/orchestration.py#L93)

```python
Track(
    *,
    id: str,
    source: Callable[[LyricSource], bool] = _all_sources,
    layout: Layout = Layout(rows=1, position=None, gap=120, alignment='left', policy='strict', reset_after=None),
    region: Box | None = None,
    preview: float = 0.6,
    tail: float = 0.3,
    animations: tuple[LyricRule, ...] = (),
    cues: Mapping[str, CuePreset] = _HAS_DEFAULT_FACTORY_CLASS(),
    tags: frozenset[str] | Callable[[LyricSource], frozenset[str]] = frozenset({}),
    styles: tuple[Style, ...] = (),
    factory: Callable[[LyricLine], LyricLine] | None = None,
    references: tuple[LayoutLine, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `source` | `Callable[[LyricSource], bool]` | `_all_sources` |
| `layout` | `Layout` | `Layout(rows=1, position=None, gap=120, alignment='left', policy='strict', reset_after=None)` |
| `region` | `Box \| None` | `None` |
| `preview` | `float` | `0.6` |
| `tail` | `float` | `0.3` |
| `animations` | `tuple[LyricRule, ...]` | `()` |
| `cues` | `Mapping[str, CuePreset]` | `dict()` |
| `tags` | `frozenset[str] \| Callable[[LyricSource], frozenset[str]]` | `frozenset({})` |
| `styles` | `tuple[Style, ...]` | `()` |
| `factory` | `Callable[[LyricLine], LyricLine] \| None` | `None` |
| `references` | `tuple[LayoutLine, ...]` | `()` |

## prepare_tracks

Measure, allocate and bind independent tracks into one ordinary Scene.

Same-source views are allowed and have distinct visual identities. Original
records are retained once as owner-marked comments. Re-preparing owned output
removes only that owner's generated events and regenerates from its sources.
inputs adds structured LyricSource values alongside parsed ASS sources.
These have no ASS record ownership and must be supplied again to regenerate
them. The caller's Document and reusable declarations are not mutated.

[Source](../../kara_templater/orchestration.py#L325)

```python
prepare_tracks(
    document: Document,
    *,
    tracks: tuple[Track, ...],
    owner: str = 'karaoke',
    inputs: tuple[LyricSource, ...] = (),
) -> LyricScene
```
