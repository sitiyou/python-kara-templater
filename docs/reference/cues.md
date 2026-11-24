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

Automatic height follows the authored host font size (48 script pixels without a host).
Automatic width is 1.5 times the height. Dimensions include the hard outline.

[Source](../../kara_templater/cues.py#L182)

```python
BarsCue(
    width: float | None = None,
    height: float | None = None,
    color: Color | None = None,
    border: float = 2,
    outline: Color | None = None,
    direction: Literal['left_to_right', 'right_to_left'] = 'left_to_right',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `width` | `float \| None` | `None` |
| `height` | `float \| None` | `None` |
| `color` | `Color \| None` | `None` |
| `border` | `float` | `2` |
| `outline` | `Color \| None` | `None` |
| `direction` | `Literal['left_to_right', 'right_to_left']` | `'left_to_right'` |

### BarsCue.__call__

Create local bar objects and explicit reserved dimensions for the supplied cue clock.

```python
BarsCue.__call__(
    context: CueContext,
) -> CueContent
```

## CueContent

Local objects plus the explicit layout space the author wants to reserve.

[Source](../../kara_templater/cues.py#L59)

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

Factories create local objects for that interval. host is the measured text
cluster at the marker (the final cluster for an end marker), when available. colors supplies the before/after paint for the first nonblank role.
role_font_size is its authored size for decoration scaling; role_em is its measured em in script pixels. base_gradient and gradient supply its base and highlight fill ramps.
zoom_pulse_curve_level selects the lyric zoom curve for cue steps, or None for steady size.

[Source](../../kara_templater/cues.py#L34)

```python
CueContext(
    id: str,
    lifetime: Lifetime,
    steps: tuple[float, ...],
    origin: EventOrigin,
    host: TextObject | None = None,
    host_em: float | None = None,
    colors: PaintPair = PaintPair(before=Paint(fill=Color(red=255, green=255, blue=255), outline=Color(red=34, green=34, blue=34), border=0, opacity=1, glow=None, secondary_outline=None), after=Paint(fill=Color(red=255, green=90, blue=111), outline=Color(red=34, green=34, blue=34), border=0, opacity=1, glow=None, secondary_outline=None)),
    zoom_pulse_curve_level: int | None = None,
    role_em: float | None = None,
    gradient: highlights.LyricGradient | None = None,
    base_gradient: highlights.LyricGradient | None = None,
    host_height: float | None = None,
    role_font_size: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `steps` | `tuple[float, ...]` | `required` |
| `origin` | `EventOrigin` | `required` |
| `host` | `TextObject \| None` | `None` |
| `host_em` | `float \| None` | `None` |
| `colors` | `PaintPair` | `PaintPair(before=Paint(fill=Color(red=255, green=255, blue=255), outline=Color(red=34, green=34, blue=34), border=0, opacity=1, glow=None, secondary_outline=None), after=Paint(fill=Color(red=255, green=90, blue=111), outline=Color(red=34, green=34, blue=34), border=0, opacity=1, glow=None, secondary_outline=None))` |
| `zoom_pulse_curve_level` | `int \| None` | `None` |
| `role_em` | `float \| None` | `None` |
| `gradient` | `highlights.LyricGradient \| None` | `None` |
| `base_gradient` | `highlights.LyricGradient \| None` | `None` |
| `host_height` | `float \| None` | `None` |
| `role_font_size` | `float \| None` | `None` |

## CueFactory

A typed callable that maps CueContext to local CueContent.

Implement it with an ordinary function or callable object to customize cue text,
geometry, and animation.

[Source](../../kara_templater/cues.py#L81)

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

[Source](../../kara_templater/cues.py#L276)

```python
CuePlacement(
    marker: CueMarker,
    content: CueContent,
    preset: CuePreset,
    lifetime: Lifetime,
    position: Vec2,
    host_height: float | None = None,
    host_font_size: float | None = None,
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
| `host_height` | `float \| None` | `None` |
| `host_font_size` | `float \| None` | `None` |

### CuePlacement.gap

Resolved clearance from the cue to its host, in script pixels.

Type: `float`.

## CuePreset

A cue factory with lead/duration in seconds, normalized step fractions, gap, position, and reservation policy.

On a Track, line_edge places an independent cue above or below the measured
lyric row (including ruby), reserves its dimensions and applies gap in pixels.
Automatic gap is one eighth of the authored host font size (12 script pixels without a host).
With no line_edge, independent cues use absolute position.
An explicit trigger overrides the relevant timing interval default. colors fixes
the cue fill and outline pair across hosts. Omit it to follow the lyric palette.

[Source](../../kara_templater/cues.py#L93)

```python
CuePreset(
    *,
    factory: CueFactory,
    lead: float | None = None,
    duration: float | None = None,
    steps: tuple[float, ...] = (0, 0.3333333333333333, 0.6666666666666666, 1),
    gap: float | None = None,
    position: Vec2 = Vec2(x=0, y=0),
    line_edge: Literal['above', 'below'] | None = None,
    keep_space: bool = True,
    trigger: float | None = None,
    colors: PaintPair | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `factory` | `CueFactory` | `required` |
| `lead` | `float \| None` | `None` |
| `duration` | `float \| None` | `None` |
| `steps` | `tuple[float, ...]` | `(0, 0.3333333333333333, 0.6666666666666666, 1)` |
| `gap` | `float \| None` | `None` |
| `position` | `Vec2` | `Vec2(x=0, y=0)` |
| `line_edge` | `Literal['above', 'below'] \| None` | `None` |
| `keep_space` | `bool` | `True` |
| `trigger` | `float \| None` | `None` |
| `colors` | `PaintPair \| None` | `None` |

### CuePreset.resolve_timing

Return (lead, duration) in seconds for a fixed song tempo.

Without BPM, each omitted field defaults to one second. With BPM,
omitted lead follows duration. VolumeCue budgets a beat for the final fill
and flash_ratio beats for each flash. Other cues budget four beats
per step, halved at 1800 ms or longer, then applies the step fractions
when binding the cue. Explicit seconds always take precedence.

```python
CuePreset.resolve_timing(
    *,
    bpm: float | None = None,
) -> tuple[float, float]
```

## CuedLayout

A plain-text layout after cue binding, with inline and independent cue groups.

Its group combines the adjusted text and reserved-space behavior.

[Source](../../kara_templater/cues.py#L303)

```python
CuedLayout(
    text: layout.TextLayout,
    cues: tuple[CuePlacement, ...],
    inline: tuple[ObjectGroup, ...],
    independent: tuple[ObjectGroup, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `layout.TextLayout` | `required` |
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

[Source](../../kara_templater/cues.py#L540)

```python
CuedLyrics(
    lyrics: layout.LyricLayout,
    cues: tuple[CuePlacement, ...],
    inline: tuple[ObjectGroup, ...],
    independent: tuple[ObjectGroup, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `lyrics` | `layout.LyricLayout` | `required` |
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

size is the side of a lamp in script pixels, defaulting to size_ratio times the authored font size at the marker. Each lamp fades over the last
transition fraction of its step. Pass a custom path in the unit square to
use a drawn symbol with the same layout and clock. spacing adds script pixels between lamps.
Set countdown in seconds to keep all lamps lit before the active steps.

[Source](../../kara_templater/karaoke_cues.py#L371)

```python
SignalCue(
    *,
    shape: Literal['circle', 'square', 'rounded', 'star', 'note8', 'note16', 'notepair'] | VectorPath = 'circle',
    direction: Literal['left_to_right', 'right_to_left'] = 'right_to_left',
    size: float | None = None,
    size_ratio: float = 0.5,
    spacing: float = 0,
    countdown: float | None = None,
    transition: float = 0.67,
    slide: Vec2 = Vec2(x=0, y=0),
    color: Color | None = None,
    outline: Color | None = None,
    border: float | None = None,
    edge_brightness: float = 0.6,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `shape` | `Literal['circle', 'square', 'rounded', 'star', 'note8', 'note16', 'notepair'] \| VectorPath` | `'circle'` |
| `direction` | `Literal['left_to_right', 'right_to_left']` | `'right_to_left'` |
| `size` | `float \| None` | `None` |
| `size_ratio` | `float` | `0.5` |
| `spacing` | `float` | `0` |
| `countdown` | `float \| None` | `None` |
| `transition` | `float` | `0.67` |
| `slide` | `Vec2` | `Vec2(x=0, y=0)` |
| `color` | `Color \| None` | `None` |
| `outline` | `Color \| None` | `None` |
| `border` | `float \| None` | `None` |
| `edge_brightness` | `float` | `0.6` |

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

[Source](../../kara_templater/cues.py#L231)

```python
TextCue(
    labels: tuple[str, ...] = ('3', '2', '1'),
    font: str = 'DejaVu Sans',
    font_size: float | None = None,
    color: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `labels` | `tuple[str, ...]` | `('3', '2', '1')` |
| `font` | `str` | `'DejaVu Sans'` |
| `font_size` | `float \| None` | `None` |
| `color` | `Color \| None` | `None` |

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
relative to the fill. transition controls the softness of each flash from 0
(hard blink) to 1. ratio is first-to-last column height and spacing is
additional horizontal space in script pixels. Set countdown in seconds to leave the group visible
and idle before the active portion. height and border use script pixels. Omit height to use size_ratio times the authored font size at the marker. column_width_ratio sets the width relative to height.
align aligns the column tops, centers or bottoms.
An omitted border scales the host outline, capped at a quarter of the column width.

[Source](../../kara_templater/karaoke_cues.py#L159)

```python
VolumeCue(
    *,
    count: int = 4,
    height: float | None = None,
    size_ratio: float = 0.5,
    column_width_ratio: float = 0.25,
    align: Literal['top', 'center', 'bottom'] = 'center',
    border: float | None = None,
    flashes: int = 3,
    flash_ratio: float = 1,
    transition: float = 0.67,
    ratio: float = 3,
    spacing: float = 0,
    countdown: float | None = None,
    after: Color | None = None,
    before: Color | None = None,
    outline: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `count` | `int` | `4` |
| `height` | `float \| None` | `None` |
| `size_ratio` | `float` | `0.5` |
| `column_width_ratio` | `float` | `0.25` |
| `align` | `Literal['top', 'center', 'bottom']` | `'center'` |
| `border` | `float \| None` | `None` |
| `flashes` | `int` | `3` |
| `flash_ratio` | `float` | `1` |
| `transition` | `float` | `0.67` |
| `ratio` | `float` | `3` |
| `spacing` | `float` | `0` |
| `countdown` | `float \| None` | `None` |
| `after` | `Color \| None` | `None` |
| `before` | `Color \| None` | `None` |
| `outline` | `Color \| None` | `None` |

### VolumeCue.__call__

Build seekable pulses and column fills ending at the cue boundary.

```python
VolumeCue.__call__(
    context: CueContext,
) -> CueContent
```

## bind_cues

Bind input markers or equivalent Python values to the same object model.

Defaults trigger at the first timing interval. Optional BPM sets automatic cue timing.
A preset can supply an absolute trigger. Inline reservations are included in
range/background measurements and optionally released after the cue ends.

[Source](../../kara_templater/cues.py#L343)

```python
bind_cues(
    layout: layout.TextLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
    bpm: float | None = None,
) -> CuedLayout
```

## bind_lyric_cues

Reserve/release body space and translate associated ruby by the same rule.

Markers use projected body offsets. A reservation inside a body unit moves
its ruby by half the reserved width, keeping its original center offset from
the expanded body box; before a unit it moves ruby by the full width.

[Source](../../kara_templater/cues.py#L566)

```python
bind_lyric_cues(
    layout: layout.LyricLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
    bpm: float | None = None,
) -> CuedLyrics
```
