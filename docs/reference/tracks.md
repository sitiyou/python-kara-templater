# Track authoring

Independent lyric streams, allocation and semantic bindings into one Scene. Singing, display and animation clocks use seconds and stay separate. See [Tracks](../guides/tracks.md).

[All public symbols](README.md#symbol-index)

## Contents

- [KaraokeDecoration](#karaokedecoration)
- [KaraokeEffects](#karaokeeffects)
- [KaraokeEntry](#karaokeentry)
- [KaraokeExit](#karaokeexit)
- [KaraokeItem](#karaokeitem)
- [KaraokeRows](#karaokerows)
- [KaraokeSinging](#karaokesinging)
- [Layout](#layout)
- [LayoutContext](#layoutcontext)
- [LayoutLine](#layoutline)
- [LinePlan](#lineplan)
- [LyricAnchor](#lyricanchor)
- [LyricAnimationContext](#lyricanimationcontext)
- [LyricEcho](#lyricecho)
- [LyricEffect](#lyriceffect)
- [LyricLine](#lyricline)
- [LyricRole](#lyricrole)
- [LyricRule](#lyricrule)
- [LyricScene](#lyricscene)
- [LyricSource](#lyricsource)
- [LyricTarget](#lyrictarget)
- [Placement](#placement)
- [ScatterOut](#scatterout)
- [Track](#track)
- [lyric_effects](#lyric_effects)
- [prepare_tracks](#prepare_tracks)

## KaraokeDecoration

Public type alias:

```python
type KaraokeDecoration = Literal['none', 'twinkle', 'twinkle_classic', 'note', 'ripple', 'petal', 'snow', 'snow_solid']
```

## KaraokeEffects

Compose entry, singing, exit and ornaments as one Track.effects callable.

All durations are seconds, widths are script pixels; particle_size is a
fraction of the shaped font’s em size. Entry/exit duration includes the
full stagger span. Zero disables that transition. `none` singing retains
ordinary wipe; `no_wipe` recolors the whole timed unit at completion. Utopia pulses
within each note; zoom_pulse grows throughout the note and releases over .30 s.
Ornament tails reserve display without altering source singing intervals.
material/glow/base_glow use the same factories as LyricHighlights.
Entry is shortened only when Scene zero leaves insufficient preview time.
Exit starts after singing (including zoom release), reserving needed tail.
Overlapping repeats truncate the preceding zoom release and restart its pulse.

Includes the Studio animation-menu families, independently implemented on
this engine. It is a visual recipe, not an importer or pixel-identical renderer.
Use ordinary LyricRule/custom effects alongside it. Apply once per line, before
another highlight factory; this recipe owns the base/sung appearance and masks.
Decorations use seeded glyph-local trajectories; ruby receives text transitions
and sweeps but not particles or outline flash. max_particles bounds the total
generated ornament objects per line, including entry and exit.

Standard ASS is supported (complex motion is sampled). GPU enhancement uses
the same Scene; dynamic blur can require additional cached native coverage.
No dependency on Manim, Qt, or the reference application is introduced.

[Source](../../kara_templater/karaoke_effects.py#L731)

```python
KaraokeEffects(
    *,
    entry: KaraokeEntry = 'fade',
    exit: KaraokeExit = 'fade',
    singing: KaraokeSinging = 'utopia',
    reverse_wipe: bool = False,
    decoration: KaraokeDecoration = 'none',
    entry_duration: float = 0.3,
    exit_duration: float = 0.3,
    stagger: float = 0.5833333333333334,
    sung: Color = Color(red=255, green=90, blue=111),
    unsung: Color = Color(red=255, green=255, blue=255),
    material: PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None | Mapping[str, LyricGradient] = None,
    base_material: PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None | Mapping[str, LyricGradient] = None,
    glow: LyricGlow = None,
    base_glow: LyricGlow = None,
    particle_color: Color | None = None,
    particle_size: float = 0.4,
    particle_rate: float | None = None,
    max_particles: int = 512,
    seed: int = 0,
    zoom_pulse_curve_level: int = 1,
    scanline_width: float | None = None,
    scanline_softness: float | None = None,
    scanline_mode: Literal['color', 'brighten', 'follow_before', 'follow_after', 'role'] = 'color',
    ruby_scanline: Literal['reading', 'both'] = 'reading',
    scanline_material: PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None | Mapping[str, LyricGradient] = None,
    scanline_brightness: float = 0.6,
    scanline_color: Color = Color(red=255, green=255, blue=255),
    hook_feather: float = 0,
    front_color: Color | None = None,
    unsung_outline: Color | None = None,
    sung_outline: Color | None = None,
    stroke_flash: bool = False,
    id: str = 'karaoke',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `entry` | `KaraokeEntry` | `'fade'` |
| `exit` | `KaraokeExit` | `'fade'` |
| `singing` | `KaraokeSinging` | `'utopia'` |
| `reverse_wipe` | `bool` | `False` |
| `decoration` | `KaraokeDecoration` | `'none'` |
| `entry_duration` | `float` | `0.3` |
| `exit_duration` | `float` | `0.3` |
| `stagger` | `float` | `0.5833333333333334` |
| `sung` | `Color` | `Color(red=255, green=90, blue=111)` |
| `unsung` | `Color` | `Color(red=255, green=255, blue=255)` |
| `material` | `PaintField \| Callable[[LyricLine, LyricTarget], PaintField \| None] \| None \| Mapping[str, LyricGradient]` | `None` |
| `base_material` | `PaintField \| Callable[[LyricLine, LyricTarget], PaintField \| None] \| None \| Mapping[str, LyricGradient]` | `None` |
| `glow` | `LyricGlow` | `None` |
| `base_glow` | `LyricGlow` | `None` |
| `particle_color` | `Color \| None` | `None` |
| `particle_size` | `float` | `0.4` |
| `particle_rate` | `float \| None` | `None` |
| `max_particles` | `int` | `512` |
| `seed` | `int` | `0` |
| `zoom_pulse_curve_level` | `int` | `1` |
| `scanline_width` | `float \| None` | `None` |
| `scanline_softness` | `float \| None` | `None` |
| `scanline_mode` | `Literal['color', 'brighten', 'follow_before', 'follow_after', 'role']` | `'color'` |
| `ruby_scanline` | `Literal['reading', 'both']` | `'reading'` |
| `scanline_material` | `PaintField \| Callable[[LyricLine, LyricTarget], PaintField \| None] \| None \| Mapping[str, LyricGradient]` | `None` |
| `scanline_brightness` | `float` | `0.6` |
| `scanline_color` | `Color` | `Color(red=255, green=255, blue=255)` |
| `hook_feather` | `float` | `0` |
| `front_color` | `Color \| None` | `None` |
| `unsung_outline` | `Color \| None` | `None` |
| `sung_outline` | `Color \| None` | `None` |
| `stroke_flash` | `bool` | `False` |
| `id` | `str` | `'karaoke'` |

### KaraokeEffects.__call__

Prepare appearance and defer text motion through the common lyric rules.

```python
KaraokeEffects.__call__(
    line: LyricLine,
) -> LyricLine
```

### KaraokeEffects.duotone

Wipe between two fill/outline pairs. The moving boundary carries no separate ink.

```python
KaraokeEffects.duotone(
    *,
    unsung: Color = Color(red=40, green=28, blue=38),
    unsung_outline: Color = Color(red=255, green=247, blue=232),
    sung: Color = Color(red=255, green=232, blue=169),
    sung_outline: Color = Color(red=173, green=66, blue=26),
    feather: float = 24,
) -> KaraokeEffects
```

## KaraokeEntry

Public type alias:

```python
type KaraokeEntry = Literal['none', 'fade', 'slide_in', 'rise', 'char_fade', 'char_drip', 'spin_flip', 'utopia', 'tracking_in', 'wave_in', 'stretch_in', 'glow_in', 'assemble_in', 'sparkle', 'ripple', 'note', 'petal', 'snow', 'snow_solid']
```

## KaraokeExit

Public type alias:

```python
type KaraokeExit = Literal['none', 'fade', 'slide_out', 'rise', 'char_fade', 'char_drip', 'spin_flip', 'utopia', 'scatter_out', 'converge_out', 'stretch_out', 'glow_out', 'dissolve_out', 'sparkle', 'ripple', 'note', 'petal', 'snow', 'snow_solid']
```

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

## KaraokeRows

Studio horizontal row presets, scaled from 1080p to the script height.

One row is centered, three use left/center/right, other counts alternate.
Use anchor to place a stream at the top, center or bottom of its region. Row height
follows the body baseline and hard outlines. Top grids reserve reading space
even on pages without ruby. Inline cues retain their horizontal reservation.
smart_horizontal defaults to equal_margins, moving the left and right rows
inward by half the page's spare width. center_position treats each row
independently. none keeps the preset alignments against the region margins.
section_gap starts a new rotation after a longer singing silence (0 disables
splitting). lane_gap reserves seconds between occupants when available.
sync_entry and sync_ending align the first and last pages respectively;
sync_each_page applies enabled synchronization to every page. fill_section
holds each row toward the next same-row preview and aligns final page tails.

[Source](../../kara_templater/lyric_layout.py#L306)

```python
KaraokeRows(
    *,
    rows: int = 2,
    anchor: Literal['top', 'center', 'bottom'] = 'bottom',
    smart_horizontal: Literal['equal_margins', 'center_position', 'none'] = 'equal_margins',
    section_gap: float = 4.0,
    lane_gap: float = 0.3,
    sync_entry: bool = True,
    sync_ending: bool = False,
    sync_each_page: bool = False,
    fill_section: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `rows` | `int` | `2` |
| `anchor` | `Literal['top', 'center', 'bottom']` | `'bottom'` |
| `smart_horizontal` | `Literal['equal_margins', 'center_position', 'none']` | `'equal_margins'` |
| `section_gap` | `float` | `4.0` |
| `lane_gap` | `float` | `0.3` |
| `sync_entry` | `bool` | `True` |
| `sync_ending` | `bool` | `False` |
| `sync_each_page` | `bool` | `False` |
| `fill_section` | `bool` | `True` |

### KaraokeRows.allocate

Paginate the track, resolve handoffs, and align each measured row.

```python
KaraokeRows.allocate(
    lines: tuple[LayoutLine, ...],
    context: LayoutContext,
) -> tuple[Placement, ...]
```

### KaraokeRows.break_before

Choose a boundary before line. Override to use tags, lead or source data.

A page restarts the row sequence. A section also restarts first/last-page
timing. Returning "none" retains automatic paging at row capacity.

```python
KaraokeRows.break_before(
    previous: LayoutLine,
    line: LayoutLine,
) -> Literal['none', 'page', 'section']
```

## KaraokeSinging

Public type alias:

```python
type KaraokeSinging = Literal['none', 'no_wipe', 'utopia', 'scanline', 'utopia_scanline', 'zoom_pulse', 'zoom_pulse_scanline']
```

## Layout

Allocate any positive number of rows, or override allocate entirely.

Strict rotation is the default. 'available' searches from the next row for
capacity. Optional preview/tail is shortened before required singing or
animation could overlap. reset_after resets rotation after a singing gap;
None preserves rotation across pauses. Lead and tags have no built-in meaning.

position is the first row's top-left, defaulting to the context region.
Alignment and offsets can be supplied per row.
Alternating alignment places even rows on the left and odd rows on the right. Bounds already
include ruby and inline cue reservations. gap is row-origin spacing in pixels.

[Source](../../kara_templater/lyric_layout.py#L171)

```python
Layout(
    *,
    rows: int = 1,
    position: Vec2 | None = None,
    gap: float = 120,
    alignment: Literal['left', 'center', 'right'] | Literal['alternating'] | tuple[Literal['left', 'center', 'right'], ...] = 'left',
    offsets: tuple[Vec2, ...] = (),
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
| `alignment` | `Literal['left', 'center', 'right'] \| Literal['alternating'] \| tuple[Literal['left', 'center', 'right'], ...]` | `'left'` |
| `offsets` | `tuple[Vec2, ...]` | `()` |
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

[Source](../../kara_templater/lyric_layout.py#L94)

```python
LayoutContext(
    region: Box,
    other_lines: tuple[LayoutLine, ...] = (),
    script_height: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `region` | `Box` | `required` |
| `other_lines` | `tuple[LayoutLine, ...]` | `()` |
| `script_height` | `float \| None` | `None` |

## LayoutLine

Immutable measured input, with original singing and desired visibility.

entrance/exit are required animation durations in seconds, outside singing.
display includes optional preview/tail and any explicitly reserved cue time.
tags and cue markers carry source data; their layout meaning is user-defined.
bounds includes body, ruby and reserved inline decorations in local pixels.

[Source](../../kara_templater/lyric_layout.py#L26)

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
    em_size: float | None = None,
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
| `em_size` | `float \| None` | `None` |

### LayoutLine.required

The minimum interval containing singing and entrance/exit animation.

Type: `TimeSpan`.

## LinePlan

Inspectable source/view association and final layout/animation binding.

[Source](../../kara_templater/orchestration.py#L165)

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
type LyricAnchor = Literal['enter', 'exit', 'singing', 'after_singing']
```

## LyricAnimationContext

Measured target and current timing request for an animation factory.

interval contains absolute seconds, including a visual copy's delay, before
rule offset/stagger. It is None for display-relative enter/exit, whose final
times depend on allocation. target retains all original singing spans.
requested_duration is the rule's optional explicit override. Factories run
once per resolved interval (once per target for display anchors), never per
rendered frame. Return an ordinary StateAnimation or AnimationSequence.

[Source](../../kara_templater/lyric_line.py#L77)

```python
LyricAnimationContext(
    line: LyricLine,
    target: LyricTarget,
    interval: TimeSpan | None,
    requested_duration: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `line` | `LyricLine` | `required` |
| `target` | `LyricTarget` | `required` |
| `interval` | `TimeSpan \| None` | `required` |
| `requested_duration` | `float \| None` | `None` |

### LyricAnimationContext.duration

Requested seconds, or the current interval's length including zero.

Raises ValueError for a display anchor without an explicit duration.
Such a factory can return an authored sequence without reading duration.
This value excludes gaps between repeated singing intervals.

Type: `float`.

## LyricEcho

Emit offset, fading copies at each character/ruby singing onset.

Copies use the selected glyph's prepared static appearance, optionally
overridden by paint. They deliberately show the full glyph, without its
sweep mask, material, reference or existing animation; this is an onset echo,
not a historical motion trail. Parent line/syllable transforms still apply.
Ordinary lyric rules continue to target the original glyph, not its echoes.

spacing/duration are seconds; offset is the parent-space distance between
successive copies. opacity multiplies original opacity, then decay reduces
each later copy. animation uses the common animation protocol, with the
measured target center as default pivot, and is stretched to duration.
The default is a linear fade, using native ASS where available. delay shifts
all copy births relative to the onset; negative values allow approaching
copies before singing, but no copy may precede Scene zero. Required display
is extended without changing singing times.

[Source](../../kara_templater/lyric_effects.py#L77)

```python
LyricEcho(
    *,
    id: str = 'echo',
    target: Literal['character', 'ruby'] = 'character',
    count: int = 3,
    spacing: float = 0.06,
    duration: float = 0.45,
    offset: Vec2 = Vec2(x=0, y=-8),
    opacity: float = 0.35,
    decay: float = 0.65,
    paint: StatePatch = StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None),
    max_copies: int = 256,
    animation: StateAnimation = FadeOut(rate=linear_rate),
    delay: float = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `'echo'` |
| `target` | `Literal['character', 'ruby']` | `'character'` |
| `count` | `int` | `3` |
| `spacing` | `float` | `0.06` |
| `duration` | `float` | `0.45` |
| `offset` | `Vec2` | `Vec2(x=0, y=-8)` |
| `opacity` | `float` | `0.35` |
| `decay` | `float` | `0.65` |
| `paint` | `StatePatch` | `StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None)` |
| `max_copies` | `int` | `256` |
| `animation` | `StateAnimation` | `FadeOut(rate=linear_rate)` |
| `delay` | `float` | `0` |

### LyricEcho.__call__

Expand a bounded onset schedule into copies under the glyph's parent.

```python
LyricEcho.__call__(
    line: LyricLine,
) -> LyricLine
```

## LyricEffect

Public type alias:

```python
type LyricEffect = LyricRule | Callable[[LyricLine], LyricLine]
```

## LyricLine

An editable lyric line, with the same animate method as any visual node.

Body and ruby belong to syllable groups, so whole-line and syllable animation
compose through the ordinary Scene hierarchy. track_index counts lines in
singing order within the selected track, starting at zero. query is a logical selection;
it never reparents objects. The original measured layout remains available.
required_display declares absolute-seconds visual intervals for allocation;
it does not move the original singing clocks or create animation events.

[Source](../../kara_templater/lyric_line.py#L261)

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
    track_index: int = 0,
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
| `track_index` | `int` | `0` |
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
    track_index: int = 0,
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

### LyricLine.schedule

Declare animations inside a Track effect, returning a new line.

Factories resolve once per interval against this measured line. Track preparation
reserves their time before layout and attaches clips after decoration
and allocation, including any subsequently added material aliases.
Display-relative enter/exit anchors use the final allocated lifetime.
This method does not attach clips immediately; use bind for an already
allocated line used directly in a Scene.

```python
LyricLine.schedule(
    *rules: LyricRule,
) -> LyricLine
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
after_singing starts at the selected target's last singing end and requires
a duration or sequence length. Select segment to trigger after each repeat,
character to trigger only after that character's final singing interval.
A factory receives a LyricAnimationContext once per resolved interval,
before layout, and returns the same animation protocol as direct authoring.
Repeated singing intervals can therefore choose different amplitudes/curves.
offset is relative seconds; display-anchor factories must return a sequence
when duration is omitted.
stagger adds nonnegative seconds between targets in selection order. For
exit, the last target ends at the display end (plus offset); earlier targets
finish earlier. Other anchors shift later targets forward from their own
anchor, so singing with stagger deliberately offsets original singing clocks.
A callable anchor receives the measured line and target and returns absolute
second intervals, before layout occupancy is allocated. This permits custom
arrival clocks without adding another animation evaluator. Returned intervals
already include any visual copy delay.
No state interpolation or ASS encoding occurs in this declaration.
target accepts a role, a queried semantic target, or a tuple of targets.
Explicit targets must belong to the receiving line; current aliases are
resolved at binding. Duplicate selections and selected descendants are
suppressed. Role/tag queries and empty tuples may select nothing.

[Source](../../kara_templater/lyric_line.py#L109)

```python
LyricRule(
    target: LyricRole | LyricTarget | tuple[LyricTarget, ...],
    anchor: LyricAnchor | LyricTarget | Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]],
    animation: StateAnimation | Callable[[LyricAnimationContext], StateAnimation],
    duration: float | None = None,
    offset: float = 0,
    hold: bool = True,
    tags: frozenset[str] = frozenset({}),
    stagger: float = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `LyricRole \| LyricTarget \| tuple[LyricTarget, ...]` | `required` |
| `anchor` | `LyricAnchor \| LyricTarget \| Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]]` | `required` |
| `animation` | `StateAnimation \| Callable[[LyricAnimationContext], StateAnimation]` | `required` |
| `duration` | `float \| None` | `None` |
| `offset` | `float` | `0` |
| `hold` | `bool` | `True` |
| `tags` | `frozenset[str]` | `frozenset({})` |
| `stagger` | `float` | `0` |

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

[Source](../../kara_templater/orchestration.py#L176)

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

### LyricScene.enhance

Attach sampled GPU effects to an explicit ordinary-ASS fallback.

Returns a new Document with versioned private Comment records. Ordinary
players display fallback unchanged; render_enhanced replaces its visual
presentation with this complete Scene. Resolution must match. Existing
Python callbacks run at export only; portable data stores reusable glyph
masks and numeric draws at integer fps (1..240), not executable code.
This initial backend supports text/static paths, affine animation, normal
local/screen rectangle clips and continuous LinearGradient. Unsupported
materials, native events, coverage groups, inherited/vector/inverse clips
and deformed paths raise. Export has bounded frame/mask/payload budgets.

```python
LyricScene.enhance(
    fallback: Document,
    *,
    fps: int = 60,
) -> Document
```

### LyricScene.evaluator

Construct a seekable world-space evaluator for this scene hierarchy and its references.

```python
LyricScene.evaluator() -> SceneEvaluator
```

### LyricScene.export_compact_ass

Save a playback ASS with native karaoke timing, line fades and cues.

For simple KaraokeEffects lines this approximates motion and materials with
native sweep and fade tags. Duotone readings use measured ruby layouts and
their own clocks. Complex timings and internal inline cue reservations
use ordinary ASS compilation. budget controls compiler resource limits.

```python
LyricScene.export_compact_ass(
    path: str | pathlib.Path,
    *,
    budget: SceneBudget | None = None,
) -> None
```

### LyricScene.export_hook

Write a standalone libplacebo .hook for a constant-frame-rate video.

Export animation parameters and sample unsupported intervals on the fps grid.
Start is frame-aligned in seconds. mpv uses media PTS;
the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
subsequent frames pass through. Render at the exported fps on an opaque
SDR video with matching aspect ratio. Includes glyph masks and effects.

```python
LyricScene.export_hook(
    path: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
) -> None
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

[Source](../../kara_templater/orchestration.py#L50)

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
center is the undecorated measured center in the node's local coordinates.
Line/syllable centers use body text, so ruby/glow do not shift the pivot.
source_style is the body cluster's active ASS style, inherited by its readings.
A factory changing a target's local coordinate origin must update center too.

[Source](../../kara_templater/lyric_line.py#L45)

```python
LyricTarget(
    id: str,
    node_id: str,
    role: LyricRole,
    singing: tuple[SingingSpan, ...] = (),
    tags: frozenset[str] = frozenset({}),
    delay: float = 0,
    aliases: tuple[str, ...] = (),
    center: Vec2 = Vec2(x=0, y=0),
    baseline: float | None = None,
    em_size: float | None = None,
    source_style: str | None = None,
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
| `center` | `Vec2` | `Vec2(x=0, y=0)` |
| `baseline` | `float \| None` | `None` |
| `em_size` | `float \| None` | `None` |
| `source_style` | `str \| None` | `None` |

## Placement

A visual origin and absolute display interval for one stable line id.

row is optional metadata; free-form layouts do not need numbered slots.
adjustments explains deliberate changes to desired visibility.

[Source](../../kara_templater/lyric_layout.py#L116)

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

## ScatterOut

A seeded lyric animation factory for rotating, drifting glyph exits.

Pass to LyricRule.animation with an exit/after_singing anchor. spread is the
horizontal displacement range, rise the upward displacement, rotation the
maximum added angle; units are script pixels/degrees. No timing is hidden in
this factory: duration, pause and stagger belong to the rule.

[Source](../../kara_templater/lyric_effects.py#L42)

```python
ScatterOut(
    *,
    spread: float = 24,
    rise: float = 36,
    rotation: float = 30,
    scale: float = 0.85,
    seed: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `spread` | `float` | `24` |
| `rise` | `float` | `36` |
| `rotation` | `float` | `30` |
| `scale` | `float` | `0.85` |
| `seed` | `int` | `0` |

### ScatterOut.__call__

Resolve deterministic per-target variation into a common animation.

```python
ScatterOut.__call__(
    timing: LyricAnimationContext,
) -> Transform
```

## Track

An independent lyric stream with selection, placement and composable effects.

With layout omitted, two bottom rows alternate left and right in the region.
All times use seconds. preview/tail are desired, reducible display padding;
rule durations and inline cue visibility are mandatory occupancy. The visual
effects receive the measured, unpositioned line once before allocation.
LyricRule entries declare timing; callable entries decorate the line in order.
Rule factories resolve once before decoration and bind to final target aliases.
Authored visual intervals join occupancy; rule binding follows allocation.
min_outline_gap is the minimum script-pixel clearance between hard strokes;
None disables extra clearance. studio_spacing selects Studio ink-based cells
for both body and readings. By default KaraokeRows uses Studio cells and
Layout uses native advances. reserved_border declares the outer hard radius
of custom or shared visual layers. Glow and motion do not reserve space.
ruby_gap sets the visual gap in script pixels between hard outlines of
the reading group and its body at rest. Negative values allow overlap.
right_to_left places shaped lyric cells from right to left, including readings.
reverse_timing assigns the first authored window to the last timed lyric unit
and reverses the built-in wipe. A predicate selects individual source lines.
All animation evaluation and output belong to Scene.

[Source](../../kara_templater/orchestration.py#L110)

```python
Track(
    *,
    id: str,
    source: Callable[[LyricSource], bool] = _all_sources,
    layout: Layout | KaraokeRows | None = None,
    region: Box | None = None,
    preview: float = 1.8,
    tail: float = 1.0,
    effects: tuple[LyricEffect, ...] = (),
    cues: Mapping[str, CuePreset] = _HAS_DEFAULT_FACTORY_CLASS(),
    guide_symbols: Mapping[str, VectorGuide] = _HAS_DEFAULT_FACTORY_CLASS(),
    tags: frozenset[str] | Callable[[LyricSource], frozenset[str]] = frozenset({}),
    styles: tuple[Style, ...] = (),
    references: tuple[LayoutLine, ...] = (),
    min_outline_gap: float | None = 2,
    reserved_border: float = 0,
    ruby_gap: float = 6,
    studio_spacing: bool | StudioSpacing | None = None,
    right_to_left: bool = False,
    reverse_timing: bool | Callable[[LyricSource], bool] = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `source` | `Callable[[LyricSource], bool]` | `_all_sources` |
| `layout` | `Layout \| KaraokeRows \| None` | `None` |
| `region` | `Box \| None` | `None` |
| `preview` | `float` | `1.8` |
| `tail` | `float` | `1.0` |
| `effects` | `tuple[LyricEffect, ...]` | `()` |
| `cues` | `Mapping[str, CuePreset]` | `dict()` |
| `guide_symbols` | `Mapping[str, VectorGuide]` | `dict()` |
| `tags` | `frozenset[str] \| Callable[[LyricSource], frozenset[str]]` | `frozenset({})` |
| `styles` | `tuple[Style, ...]` | `()` |
| `references` | `tuple[LayoutLine, ...]` | `()` |
| `min_outline_gap` | `float \| None` | `2` |
| `reserved_border` | `float` | `0` |
| `ruby_gap` | `float` | `6` |
| `studio_spacing` | `bool \| StudioSpacing \| None` | `None` |
| `right_to_left` | `bool` | `False` |
| `reverse_timing` | `bool \| Callable[[LyricSource], bool]` | `False` |

## lyric_effects

Compose built-in or custom lyric factories in the supplied order.

Pass the result as an entry in Track.effects. Each factory runs once on the prepared
line; it must retain its identity. Timing/animation evaluation stays in Scene.

[Source](../../kara_templater/lyric_effects.py#L23)

```python
lyric_effects(
    *effects: Callable[[LyricLine], LyricLine],
) -> Callable[[LyricLine], LyricLine]
```

## prepare_tracks

Measure, allocate and bind independent tracks into one ordinary Scene.

Same-source views are allowed and have distinct visual identities. Original
records are retained once as owner-marked comments. Re-preparing owned output
removes only that owner's generated events and regenerates from its sources.
inputs adds structured LyricSource values alongside parsed ASS sources.
These have no ASS record ownership and must be supplied again to regenerate
them. The caller's Document and reusable declarations are not mutated.

[Source](../../kara_templater/orchestration.py#L415)

```python
prepare_tracks(
    document: Document,
    *,
    tracks: tuple[Track, ...],
    owner: str = 'karaoke',
    inputs: tuple[LyricSource, ...] = (),
) -> LyricScene
```
