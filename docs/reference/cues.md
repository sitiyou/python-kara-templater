# Lyric cues

Typed content factories, reservations, independent placement, and body/ruby binding. Cue lifetimes and trigger values use seconds. See [text and cues](../guides/text-and-cues.md).

[All public symbols](README.md#symbol-index)

## Contents

- [BarsCue](#barscue)
- [CueContent](#cuecontent)
- [CueContext](#cuecontext)
- [CueFactory](#cuefactory)
- [CuePlacement](#cueplacement)
- [CuePreset](#cuepreset)
- [CuedLayout](#cuedlayout)
- [CuedLyrics](#cuedlyrics)
- [SignalCue](#signalcue)
- [TextCue](#textcue)
- [VolumeCue](#volumecue)
- [bind_cues](#bind_cues)
- [bind_lyric_cues](#bind_lyric_cues)

## BarsCue

A CueFactory producing a stepwise bar countdown from vector objects.

Width, height, border, and colors are explicit and the returned content reserves
its own layout dimensions.

[Source](../../kara_templater/cues.py#L99)

```python
BarsCue(
    width: float = 72,
    height: float = 48,
    color: Color = Color(red=0, green=255, blue=255),
    border: float = 2,
    outline: Color = Color(red=255, green=255, blue=255),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `width` | `float` | `72` |
| `height` | `float` | `48` |
| `color` | `Color` | `Color(red=0, green=255, blue=255)` |
| `border` | `float` | `2` |
| `outline` | `Color` | `Color(red=255, green=255, blue=255)` |

### BarsCue.__call__

Create local bar objects and explicit reserved dimensions for the supplied cue clock.

```python
BarsCue.__call__(
    context: CueContext,
) -> CueContent
```

## CueContent

Local objects plus the explicit layout space the author wants to reserve.

[Source](../../kara_templater/cues.py#L42)

```python
CueContent(
    objects: tuple[SceneObject, ...],
    width: float,
    height: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `objects` | `tuple[SceneObject, ...]` | `required` |
| `width` | `float` | `required` |
| `height` | `float` | `required` |

## CueContext

Factory input containing a stable cue ID, absolute seconds lifetime, absolute step boundaries, and source origin.

Factories create local objects for that interval.

[Source](../../kara_templater/cues.py#L29)

```python
CueContext(
    id: str,
    lifetime: Lifetime,
    steps: tuple[float, ...],
    origin: EventOrigin,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `steps` | `tuple[float, ...]` | `required` |
| `origin` | `EventOrigin` | `required` |

## CueFactory

A typed callable that maps CueContext to local CueContent.

Implement it with an ordinary function or callable object to customize cue text,
geometry, and animation.

[Source](../../kara_templater/cues.py#L56)

### CueFactory.__call__

Return custom local objects and reserved dimensions for the supplied cue context.

```python
CueFactory.__call__(
    context: CueContext,
    /,
) -> CueContent
```

## CuePlacement

A bound marker, preset, content, and trigger placement in the lyric layout.

It retains the data needed to reserve or release inline space.

[Source](../../kara_templater/cues.py#L179)

```python
CuePlacement(
    marker: CueMarker,
    content: CueContent,
    preset: CuePreset,
    lifetime: Lifetime,
    position: Vec2,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `marker` | `CueMarker` | `required` |
| `content` | `CueContent` | `required` |
| `preset` | `CuePreset` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `position` | `Vec2` | `required` |

## CuePreset

A cue factory with lead/duration in seconds, normalized step fractions, gap, position, and reservation policy.

An explicit trigger overrides the relevant singing interval default.

[Source](../../kara_templater/cues.py#L68)

```python
CuePreset(
    *,
    factory: CueFactory,
    lead: float = 1,
    duration: float = 1,
    steps: tuple[float, ...] = (0, 0.3333333333333333, 0.6666666666666666, 1),
    gap: float = 12,
    position: Vec2 = Vec2(x=0, y=0),
    keep_space: bool = True,
    trigger: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `factory` | `CueFactory` | `required` |
| `lead` | `float` | `1` |
| `duration` | `float` | `1` |
| `steps` | `tuple[float, ...]` | `(0, 0.3333333333333333, 0.6666666666666666, 1)` |
| `gap` | `float` | `12` |
| `position` | `Vec2` | `Vec2(x=0, y=0)` |
| `keep_space` | `bool` | `True` |
| `trigger` | `float \| None` | `None` |

## CuedLayout

A plain-text layout after cue binding, with inline and independent cue groups.

Its group combines the adjusted text and reserved-space behavior.

[Source](../../kara_templater/cues.py#L193)

```python
CuedLayout(
    text: DocumentLayout,
    cues: tuple[CuePlacement, ...],
    inline: tuple[ObjectGroup, ...],
    independent: tuple[ObjectGroup, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `DocumentLayout` | `required` |
| `cues` | `tuple[CuePlacement, ...]` | `required` |
| `inline` | `tuple[ObjectGroup, ...]` | `required` |
| `independent` | `tuple[ObjectGroup, ...]` | `required` |

### CuedLayout.group

Only inline cues follow this lyric group; independent cues stay separate.

```python
CuedLayout.group(
    *,
    position: Vec2 | None = None,
) -> ObjectGroup
```

## CuedLyrics

Body/ruby with shared cue reservations; independent cues remain separate.

[Source](../../kara_templater/cues.py#L399)

```python
CuedLyrics(
    lyrics: LyricLayout,
    cues: tuple[CuePlacement, ...],
    inline: tuple[ObjectGroup, ...],
    independent: tuple[ObjectGroup, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `lyrics` | `LyricLayout` | `required` |
| `cues` | `tuple[CuePlacement, ...]` | `required` |
| `inline` | `tuple[ObjectGroup, ...]` | `required` |
| `independent` | `tuple[ObjectGroup, ...]` | `required` |

### CuedLyrics.group

Build the adjusted body, readings, and cue content as one editable object hierarchy.

```python
CuedLyrics.group(
    *,
    position: Vec2 | None = None,
) -> ObjectGroup
```

## SignalCue

A row of vector lamps extinguishing on cue steps, right to left by default.

size is the side of a lamp in script pixels. Each lamp fades over the last
transition fraction of its step. Pass a custom path in the unit square to
use a drawn symbol with the same layout and clock.

[Source](../../kara_templater/karaoke_cues.py#L170)

```python
SignalCue(
    *,
    shape: Literal['circle', 'square', 'rounded', 'star', 'note8', 'note16', 'notepair'] | VectorPath = 'circle',
    direction: Literal['left_to_right', 'right_to_left'] = 'right_to_left',
    size: float = 50,
    transition: float = 0.67,
    slide: Vec2 = Vec2(x=0, y=0),
    color: Color = Color(red=255, green=90, blue=111),
    outline: Color = Color(red=34, green=34, blue=34),
    border: float = 2,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `shape` | `Literal['circle', 'square', 'rounded', 'star', 'note8', 'note16', 'notepair'] \| VectorPath` | `'circle'` |
| `direction` | `Literal['left_to_right', 'right_to_left']` | `'right_to_left'` |
| `size` | `float` | `50` |
| `transition` | `float` | `0.67` |
| `slide` | `Vec2` | `Vec2(x=0, y=0)` |
| `color` | `Color` | `Color(red=255, green=90, blue=111)` |
| `outline` | `Color` | `Color(red=34, green=34, blue=34)` |
| `border` | `float` | `2` |

### SignalCue.__call__

Place lamp shapes on their own intervals within the cue lifetime.

```python
SignalCue.__call__(
    context: CueContext,
) -> CueContent
```

## TextCue

A CueFactory displaying configurable countdown text for each step.

It measures the requested font and returns objects plus explicit reserved width
and height.

[Source](../../kara_templater/cues.py#L137)

```python
TextCue(
    labels: tuple[str, ...] = ('3', '2', '1'),
    font: str = 'DejaVu Sans',
    font_size: float = 48,
    color: Color = Color(red=0, green=255, blue=255),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `labels` | `tuple[str, ...]` | `('3', '2', '1')` |
| `font` | `str` | `'DejaVu Sans'` |
| `font_size` | `float` | `48` |
| `color` | `Color` | `Color(red=0, green=255, blue=255)` |

### TextCue.__call__

Create the configured step text objects and measured reserved dimensions for this cue.

```python
TextCue.__call__(
    context: CueContext,
) -> CueContent
```

## VolumeCue

Descending inline columns. Flash together, then fill from left to right.

The cue ends at its declared lifetime. count sets the column count; flashes
sets the number of group pulses before the final fill. Each pulse and the
fill get equal time by default; flash_ratio scales the length of each pulse
relative to the fill. ratio is first-to-last column height and spacing is
additional horizontal space in script pixels. Set countdown in seconds to leave the group visible
and idle before the active portion. height and border use script pixels.

[Source](../../kara_templater/karaoke_cues.py#L29)

```python
VolumeCue(
    *,
    count: int = 4,
    height: float = 50,
    border: float = 4,
    flashes: int = 3,
    flash_ratio: float = 1,
    ratio: float = 3,
    spacing: float = 0,
    countdown: float | None = None,
    sung: Color = Color(red=255, green=90, blue=111),
    unsung: Color = Color(red=255, green=255, blue=255),
    outline: Color = Color(red=34, green=34, blue=34),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `count` | `int` | `4` |
| `height` | `float` | `50` |
| `border` | `float` | `4` |
| `flashes` | `int` | `3` |
| `flash_ratio` | `float` | `1` |
| `ratio` | `float` | `3` |
| `spacing` | `float` | `0` |
| `countdown` | `float \| None` | `None` |
| `sung` | `Color` | `Color(red=255, green=90, blue=111)` |
| `unsung` | `Color` | `Color(red=255, green=255, blue=255)` |
| `outline` | `Color` | `Color(red=34, green=34, blue=34)` |

### VolumeCue.__call__

Build seekable pulses and column fills ending at the cue boundary.

```python
VolumeCue.__call__(
    context: CueContext,
) -> CueContent
```

## bind_cues

Bind input markers or equivalent Python values to the same object model.

Defaults trigger at the first singing interval; there is no inferred beat.
A preset can supply an absolute trigger. Inline reservations are included in
range/background measurements and optionally released after the cue ends.

[Source](../../kara_templater/cues.py#L233)

```python
bind_cues(
    layout: DocumentLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
) -> CuedLayout
```

## bind_lyric_cues

Reserve/release body space and translate associated ruby by the same rule.

Markers use projected body offsets. A reservation inside a body unit moves
its ruby by half the reserved width, keeping its original center offset from
the expanded body box; before a unit it moves ruby by the full width.

[Source](../../kara_templater/cues.py#L425)

```python
bind_lyric_cues(
    layout: LyricLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
) -> CuedLyrics
```
