# Colors and appearance

RGB colors, typed appearance, spatial fields, and material animation. Pixel distances and opacity in 0..1 are authoring values; ASS encodings are output details. See [materials](../guides/materials.md).

[All public symbols](README.md#symbol-index)

## Contents

- [BLACK](#black)
- [BLUE](#blue)
- [CYAN](#cyan)
- [Color](#color)
- [ColorRamp](#colorramp)
- [ColorStop](#colorstop)
- [GRAY](#gray)
- [GREEN](#green)
- [Glow](#glow)
- [Highlight](#highlight)
- [HighlightArrival](#highlightarrival)
- [HighlightPass](#highlightpass)
- [LinearGradient](#lineargradient)
- [LyricGlow](#lyricglow)
- [LyricGradient](#lyricgradient)
- [LyricHighlights](#lyrichighlights)
- [LyricSweep](#lyricsweep)
- [MAGENTA](#magenta)
- [ORANGE](#orange)
- [PINK](#pink)
- [PURPLE](#purple)
- [Paint](#paint)
- [PaintActivity](#paintactivity)
- [PaintBand](#paintband)
- [PaintField](#paintfield)
- [PaintPair](#paintpair)
- [RED](#red)
- [SoftSweep](#softsweep)
- [WHITE](#white)
- [YELLOW](#yellow)

## BLACK

Public constant:

```python
BLACK = Color(red=0, green=0, blue=0)
```

## BLUE

Public constant:

```python
BLUE = Color(red=0, green=0, blue=255)
```

## CYAN

Public constant:

```python
CYAN = Color(red=0, green=255, blue=255)
```

## Color

An immutable RGB color with integer channels in 0 through 255.

hex accepts exactly #RRGGBB; ASS BGR conversion is performed at serialization
boundaries.

[Source](../../kara_templater/composition.py#L10)

```python
Color(
    red: int,
    green: int,
    blue: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `red` | `int` | `required` |
| `green` | `int` | `required` |
| `blue` | `int` | `required` |

### Color.hex

Parse exactly #RRGGBB into validated integer RGB channels; reject malformed strings.

```python
Color.hex(
    value: str,
) -> Self
```

## ColorRamp

Piecewise linear colors at absolute script coordinates; ends clamp.

[Source](../../kara_templater/paint_fields.py#L100)

```python
ColorRamp(
    stops: tuple[ColorStop, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `stops` | `tuple[ColorStop, ...]` | `required` |

### ColorRamp.at

Evaluate the RGB ramp at a script-space position, extending endpoint colors outside its stops.

```python
ColorRamp.at(
    position: float,
) -> Color
```

## ColorStop

An RGB color at a finite script-space position along a paint field axis.

ColorRamp requires ordered stops.

[Source](../../kara_templater/paint_fields.py#L86)

```python
ColorStop(
    position: float,
    color: Color,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `position` | `float` | `required` |
| `color` | `Color` | `required` |

## GRAY

Public constant:

```python
GRAY = Color(red=128, green=128, blue=128)
```

## GREEN

Public constant:

```python
GREEN = Color(red=0, green=255, blue=0)
```

## Glow

A paint glow with RGB color, nonnegative blur/border in script pixels, and opacity in 0 through 1.

It is separate from the body fill and outline.

[Source](../../kara_templater/composition.py#L43)

```python
Glow(
    color: Color = Color(red=255, green=255, blue=255),
    blur: float = 0,
    border: float = 0,
    opacity: float = 1,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `Color` | `Color(red=255, green=255, blue=255)` |
| `blur` | `float` | `0` |
| `border` | `float` | `0` |
| `opacity` | `float` | `1` |

## Highlight

A named paint contribution for one lyric unit, independent of Track streams.

[Source](../../kara_templater/lyric_highlights.py#L146)

```python
Highlight(
    id: str,
    unit: int,
    passes: tuple[HighlightPass, ...],
    paint: StatePatch,
    priority: int = 0,
    repeat: Literal['hold', 'reset'] = 'hold',
    end: Literal['hold', 'hide'] = 'hold',
    glow: LyricGlow = None,
    material: PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `unit` | `int` | `required` |
| `passes` | `tuple[HighlightPass, ...]` | `required` |
| `paint` | `StatePatch` | `required` |
| `priority` | `int` | `0` |
| `repeat` | `Literal['hold', 'reset']` | `'hold'` |
| `end` | `Literal['hold', 'hide']` | `'hold'` |
| `glow` | `LyricGlow` | `None` |
| `material` | `PaintField \| Callable[[LyricLine, LyricTarget], PaintField \| None] \| None` | `None` |

### Highlight.regions

Resolve owned regions at absolute seconds, applying repeat/end policy.

```python
Highlight.regions(
    time: float,
) -> tuple[Region, ...]
```

## HighlightArrival

Bind common animations to measured character crossings before allocation.

Use as LyricRule.anchor. first selects the earliest highlight per repeat round;
each keeps every highlight, and names restricts either selection explicitly.
Thresholds use original measured geometry, independent of animation and paint
priority. The interval length is full character traversal. A partial traversal
requires duration here; LyricRule.duration may further override that length.
Nonlinear passes require a declared inverse_rate. No runtime state is retained.

[Source](../../kara_templater/lyric_highlights.py#L880)

```python
HighlightArrival(
    *,
    highlights: tuple[Highlight, ...] | Callable[[LyricLine], tuple[Highlight, ...]],
    threshold: Literal['enter', 'center', 'complete'] = 'enter',
    selection: Literal['first', 'each'] = 'first',
    names: frozenset[str] = frozenset({}),
    retrigger: bool = True,
    duration: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `highlights` | `tuple[Highlight, ...] \| Callable[[LyricLine], tuple[Highlight, ...]]` | `required` |
| `threshold` | `Literal['enter', 'center', 'complete']` | `'enter'` |
| `selection` | `Literal['first', 'each']` | `'first'` |
| `names` | `frozenset[str]` | `frozenset({})` |
| `retrigger` | `bool` | `True` |
| `duration` | `float \| None` | `None` |

### HighlightArrival.__call__

Resolve this target's selected crossings and durations in absolute seconds.

```python
HighlightArrival.__call__(
    line: LyricLine,
    target: LyricTarget,
) -> tuple[TimeSpan, ...]
```

## HighlightPass

One left-to-right pass, with absolute seconds and measured line-local x.

round identifies repeat groups; reset discards previous rounds. rate receives
normalized progress. Declared breakpoints are seconds from the pass start.
A zero-duration pass reveals its entire region at its start, as ASS k0 does.

[Source](../../kara_templater/lyric_highlights.py#L84)

```python
HighlightPass(
    time: TimeSpan,
    region: Region,
    round: int = 0,
    rate: Callable[[float], float] = linear_rate,
    breakpoints: tuple[float, ...] = (),
    inverse_rate: Callable[[float], float] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `time` | `TimeSpan` | `required` |
| `region` | `Region` | `required` |
| `round` | `int` | `0` |
| `rate` | `Callable[[float], float]` | `linear_rate` |
| `breakpoints` | `tuple[float, ...]` | `()` |
| `inverse_rate` | `Callable[[float], float] \| None` | `None` |

### HighlightPass.arrival

Return an exact crossing clock using a declared monotone inverse.

Arbitrary forward callbacks cannot be reliably inverted by sampling.
A nonlinear rate therefore needs inverse_rate for arrival bindings.

```python
HighlightPass.arrival(
    x: float,
) -> float | None
```

### HighlightPass.front

Return the line-local front coordinate at absolute Scene seconds.

```python
HighlightPass.front(
    time: float,
) -> float
```

## LinearGradient

An x/y gradient for fill, outline, or both; screen coordinates by default.

Integer step controls color band width and the declared maximum band count.
Local space attaches colors to the drawing during scale/translation. It
currently requires an ordinary positive axis-aligned drawing with a local,
non-inverse RectangleKeyframes clip fixed along the color axis, no parent
masks, and no coverage material composition. Unsupported combinations raise
instead of silently changing coordinate spaces. With native_tweens, eligible
scale/opacity curves and a single move share native band events.

[Source](../../kara_templater/paint_fields.py#L153)

```python
LinearGradient(
    *,
    fill: ColorRamp | None = None,
    outline: ColorRamp | None = None,
    axis: Literal['x', 'y'] = 'x',
    step: int = 1,
    space: Literal['screen', 'local'] = 'screen',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorRamp \| None` | `None` |
| `outline` | `ColorRamp \| None` | `None` |
| `axis` | `Literal['x', 'y']` | `'x'` |
| `step` | `int` | `1` |
| `space` | `Literal['screen', 'local']` | `'screen'` |

### LinearGradient.bands

Resolve fill/outline colors into bounded integer bands for the evaluated drawing state.

```python
LinearGradient.bands(
    start: int,
    end: int,
    time: float,
    base: VisualState,
) -> tuple[PaintBand, ...]
```

### LinearGradient.bounds

The script-space interval covered by the configured color ramps.

Type: `tuple[float, float]`.

### LinearGradient.breakpoints

Time boundaries required by this field; a static gradient has none.

Type: `tuple[float, ...]`.

### LinearGradient.max_bands

Declared upper bound on emitted color bands at the configured step.

Type: `int`.

## LyricGlow

Public type alias:

```python
type LyricGlow = Glow | GlowFunction | Callable[[LyricLine, LyricTarget], Glow | GlowFunction | None] | None
```

## LyricGradient

Evenly spaced vertical colors attached to each measured body/ruby glyph.

Pass as material to LyricHighlights.from_singing. Coordinates are derived
from undecorated glyph bounds, independent of glow/outline;
step is color-band width in local script pixels. This factory produces an
ordinary LinearGradient and inherits its renderer restrictions.

[Source](../../kara_templater/lyric_highlights.py#L40)

```python
LyricGradient(
    colors: tuple[Color, ...],
    step: int = 1,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `colors` | `tuple[Color, ...]` | `required` |
| `step` | `int` | `1` |

### LyricGradient.__call__

Resolve a local fill gradient once during lyric preparation.

```python
LyricGradient.__call__(
    line: LyricLine,
    target: LyricTarget,
) -> LinearGradient
```

## LyricHighlights

Build named union/priority/layer highlights with common visual objects.

Clip mode clips completed drawing layers (including separate static glow).
Its glow uses ordinary per-layer alpha and is cut after blur. Coverage mode
assigns fractional material ownership before blur and closes component alpha;
it rejects intentional layered overlap, which has different compositing.
Existing masks/materials must be composed explicitly instead of overwritten.
Ownership reaching a unit's outer edges includes its overhang, outline and
glow, so a completed full-unit highlight owns the complete drawing. Interior
region edges remain exact cuts. Clip uses disjoint rectangular strips so
axis-aligned world-space edges share ASS integer pixel boundaries, avoiding
antialiased vector-mask seams between translucent layers. Rotated/sheared
masks still use vector clipping. Clip masks use local ±65536 outer bounds;
use explicit custom masks for drawings outside that range.
Glow factories receive the line and target once during construction, allowing
distinct body/ruby geometry without invoking author selection on each frame.

[Source](../../kara_templater/lyric_highlights.py#L425)

```python
LyricHighlights(
    *,
    highlights: tuple[Highlight, ...] | Callable[[LyricLine], tuple[Highlight, ...]],
    mode: Literal['union', 'priority', 'layer'] = 'union',
    strategy: Literal['clip', 'coverage'] = 'clip',
    glow: LyricGlow = None,
    settings: RasterSettings = RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128),
    base_paint: StatePatch = StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None),
    hook_feather: float = 0,
    front_color: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `highlights` | `tuple[Highlight, ...] \| Callable[[LyricLine], tuple[Highlight, ...]]` | `required` |
| `mode` | `Literal['union', 'priority', 'layer']` | `'union'` |
| `strategy` | `Literal['clip', 'coverage']` | `'clip'` |
| `glow` | `LyricGlow` | `None` |
| `settings` | `RasterSettings` | `RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128)` |
| `base_paint` | `StatePatch` | `StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None)` |
| `hook_feather` | `float` | `0` |
| `front_color` | `Color \| None` | `None` |

### LyricHighlights.__call__

Return decorated visuals, reserving each target's shifted pass intervals.

Pass times use original source seconds. A copied target's delay shifts
both rendering and required_display; source singing spans stay unchanged.

```python
LyricHighlights.__call__(
    line: LyricLine,
) -> LyricLine
```

### LyricHighlights.from_singing

Sweep source singing across body/ruby without authoring clip geometry.

Singing progress uses undecorated measured text bounds. For a single
linear interval in clip mode, outline/glow margins are traversed in
separate 20 ms shoulders before/after singing, reserved automatically.
Known rectangle keyframes allow continuous native ASS lowering. Repeated
intervals retain the general ownership evaluator; coverage keeps its
color-before-blur semantics. Source singing clocks never change.
material applies only to the sung drawing, leaving the separate glow
color intact. It accepts a PaintField or a (line, target) factory called
once during preparation; use LyricGradient for measured vertical colors.
Materials require clip strategy. Local gradients currently require a
positive single singing interval and axis-aligned scale/translation.
base_paint changes only the unsung drawing; sung layers retain the
original appearance before applying paint. Use base_paint with opacity=0
to reveal text instead of recoloring an already visible baseline.

```python
LyricHighlights.from_singing(
    paint: StatePatch,
    *,
    glow: LyricGlow = None,
    base_glow: LyricGlow = None,
    base_paint: StatePatch | None = None,
    material: PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None = None,
    strategy: Literal['clip', 'coverage'] = 'clip',
    hook_feather: float = 0,
    front_color: Color | None = None,
    settings: RasterSettings | None = None,
) -> LyricHighlights
```

## LyricSweep

Apply per-syllable singing sweeps to body and ruby, using Scene paint fields.

Widths are soft-front widths in screen pixels; zero is a hard edge. Repeated
singing restarts the sweep for the new interval. Zero-duration singing
changes to the sung color at its exact start without reserving animation time. Translation and positive
horizontal scaling follow the actual evaluated state; rotated/sheared fronts
require an explicit custom material and raise instead of silently changing
the effect. This is color replacement, not translucent overlay composition.
Fill/outline may be factories receiving the measured line and semantic target;
they resolve once per target when applying the sweep, not on every frame.
A factory may return None to preserve that target's animated channel. If both
channels are omitted, the target is left untouched, including its material.

[Source](../../kara_templater/lyric_paint.py#L81)

```python
LyricSweep(
    *,
    fill: Color | Callable[[LyricLine, LyricTarget], Color | None] | None = None,
    outline: Color | Callable[[LyricLine, LyricTarget], Color | None] | None = None,
    width: float = 12,
    outline_width: float | None = None,
    step: int = 1,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `Color \| Callable[[LyricLine, LyricTarget], Color \| None] \| None` | `None` |
| `outline` | `Color \| Callable[[LyricLine, LyricTarget], Color \| None] \| None` | `None` |
| `width` | `float` | `12` |
| `outline_width` | `float \| None` | `None` |
| `step` | `int` | `1` |

### LyricSweep.__call__

Bind paint to measured clusters without splitting text or singing spans.

```python
LyricSweep.__call__(
    line: LyricLine,
) -> LyricLine
```

## MAGENTA

Public constant:

```python
MAGENTA = Color(red=255, green=0, blue=255)
```

## ORANGE

Public constant:

```python
ORANGE = Color(red=255, green=165, blue=0)
```

## PINK

Public constant:

```python
PINK = Color(red=255, green=192, blue=203)
```

## PURPLE

Public constant:

```python
PURPLE = Color(red=128, green=0, blue=128)
```

## Paint

Resolved fill, outline, border width, opacity, and optional glow for one drawing.

Distances use script pixels and opacity uses 0 through 1.

[Source](../../kara_templater/composition.py#L71)

```python
Paint(
    fill: Color = Color(red=255, green=255, blue=255),
    outline: Color = Color(red=0, green=0, blue=0),
    border: float = 0,
    opacity: float = 1,
    glow: Glow | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `Color` | `Color(red=255, green=255, blue=255)` |
| `outline` | `Color` | `Color(red=0, green=0, blue=0)` |
| `border` | `float` | `0` |
| `opacity` | `float` | `1` |
| `glow` | `Glow \| None` | `None` |

## PaintActivity

Optional promise that a paint field is time-constant outside these spans.

Intervals use signed local seconds, and their endpoints must also be breakpoints.
Changes to the incoming VisualState are sampled independently. Omit this
protocol when an arbitrary callback cannot make the constancy guarantee;
the compiler then samples its complete visible lifetime.

[Source](../../kara_templater/paint_fields.py#L70)

### PaintActivity.active_intervals

Finite positive-duration local intervals where time changes the field.

Type: `tuple[TimeSpan, ...]`.

## PaintBand

A half-open integer interval with resolved fill and outline colors.

Paint fields return these bounded bands for standard ASS compilation.

[Source](../../kara_templater/paint_fields.py#L26)

```python
PaintBand(
    start: int,
    end: int,
    fill: Color,
    outline: Color,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `int` | `required` |
| `end` | `int` | `required` |
| `fill` | `Color` | `required` |
| `outline` | `Color` | `required` |

## PaintField

Pure local-time field. Bands must exactly partition the requested domain.

Breakpoints delimit temporal discontinuities and changes of motion. An empty
tuple declares a static field. max_bands bounds every invocation.
Times are signed seconds from the owning object's clock origin; absolute
breakpoints cannot precede Scene zero or exceed the object's display end.

[Source](../../kara_templater/paint_fields.py#L39)

### PaintField.axis

The x or y script-space axis along which bands are encoded.

Type: `Literal['x', 'y']`.

### PaintField.bands

Evaluate bounded colored bands for the supplied visual state and seconds time.

```python
PaintField.bands(
    start: int,
    end: int,
    time: float,
    base: VisualState,
) -> tuple[PaintBand, ...]
```

### PaintField.breakpoints

Declared seconds boundaries required for deterministic material sampling.

Type: `tuple[float, ...]`.

### PaintField.max_bands

The maximum band count promised by this paint field for preflight.

Type: `int`.

## PaintPair

The unsung and sung Paint values for one visual target.

Paint changes do not rewrite its source singing clock.

[Source](../../kara_templater/appearance.py#L8)

```python
PaintPair(
    before: Paint = _HAS_DEFAULT_FACTORY_CLASS(),
    after: Paint = _HAS_DEFAULT_FACTORY_CLASS(),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `before` | `Paint` | `Paint()` |
| `after` | `Paint` | `Paint()` |

## RED

Public constant:

```python
RED = Color(red=255, green=0, blue=0)
```

## SoftSweep

Left-to-right (or top-to-bottom) sweep; pairs are (unsung, sung).

Widths are script pixels. The front travels past both ends so the declared
span is completely unsung at start and completely sung at start+duration.
start and duration are local seconds from the owning object's clock origin.

[Source](../../kara_templater/paint_fields.py#L216)

```python
SoftSweep(
    *,
    left: float,
    right: float,
    start: float,
    duration: float,
    fill: tuple[Color, Color] | None = None,
    outline: tuple[Color, Color] | None = None,
    width: float = 24,
    outline_width: float | None = None,
    axis: Literal['x', 'y'] = 'x',
    step: int = 1,
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `left` | `float` | `required` |
| `right` | `float` | `required` |
| `start` | `float` | `required` |
| `duration` | `float` | `required` |
| `fill` | `tuple[Color, Color] \| None` | `None` |
| `outline` | `tuple[Color, Color] \| None` | `None` |
| `width` | `float` | `24` |
| `outline_width` | `float \| None` | `None` |
| `axis` | `Literal['x', 'y']` | `'x'` |
| `step` | `int` | `1` |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### SoftSweep.active_intervals

Only the sweep interval changes with time; both endpoints clamp.

Type: `tuple[TimeSpan, ...]`.

### SoftSweep.bands

Evaluate the independent fill/outline fronts into integer color bands at seconds time.

```python
SoftSweep.bands(
    start: int,
    end: int,
    time: float,
    base: VisualState,
) -> tuple[PaintBand, ...]
```

### SoftSweep.breakpoints

The local start and end seconds required by material sampling.

Type: `tuple[float, ...]`.

### SoftSweep.effective_outline_width

The explicit outline front width or the fill width when none was supplied.

Type: `float`.

### SoftSweep.front_at

Transition center in script pixels at field-local seconds.

It travels half the largest transition width beyond each endpoint and
clamps outside the singing interval, matching the color field's timing.

```python
SoftSweep.front_at(
    time: float,
) -> float
```

### SoftSweep.max_bands

Declared worst-case color-band count at the selected spatial step.

Type: `int`.

### SoftSweep.max_width

The larger fill/outline transition width used to cover both sweep endpoints.

Type: `float`.

## WHITE

Public constant:

```python
WHITE = Color(red=255, green=255, blue=255)
```

## YELLOW

Public constant:

```python
YELLOW = Color(red=255, green=255, blue=0)
```
