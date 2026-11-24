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
- [Extrusion](#extrusion)
- [GRAY](#gray)
- [GREEN](#green)
- [Glow](#glow)
- [Highlight](#highlight)
- [HighlightArrival](#highlightarrival)
- [HighlightPass](#highlightpass)
- [KaraokeTheme](#karaoketheme)
- [LinearGradient](#lineargradient)
- [LyricGlow](#lyricglow)
- [LyricGradient](#lyricgradient)
- [LyricHighlights](#lyrichighlights)
- [MAGENTA](#magenta)
- [ORANGE](#orange)
- [PINK](#pink)
- [PURPLE](#purple)
- [Paint](#paint)
- [PaintPair](#paintpair)
- [RED](#red)
- [SecondaryOutline](#secondaryoutline)
- [ShaderPaint](#shaderpaint)
- [WHITE](#white)
- [YELLOW](#yellow)
- [paint_pair_from_style](#paint_pair_from_style)

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

[Source](../../kara_templater/composition.py#L13)

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

[Source](../../kara_templater/paint_fields.py#L69)

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

[Source](../../kara_templater/paint_fields.py#L55)

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

## Extrusion

A solid side swept from a drawing's hard silhouette in local script pixels.

Offset is the vector from front to back. The side follows the face's
transforms and opacity, and keeps its own color during a lyric wipe.
back_color shades the side from color at the face to back_color at full depth.
Zero offset gives a flat drawing. Hook output supports this appearance.

[Source](../../kara_templater/paint_fields.py#L19)

```python
Extrusion(
    offset: Vec2,
    color: Color,
    back_color: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `Vec2` | `required` |
| `color` | `Color` | `required` |
| `back_color` | `Color \| None` | `None` |

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

[Source](../../kara_templater/composition.py#L46)

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

### Glow.from_studio

Create a single-pass Karaoke Studio text halo in script pixels.

radius is Studio's Gaussian standard deviation. outline is the distance
the full hard outline extends beyond the glyph, including a secondary rim.
A zero radius hides the halo.

```python
Glow.from_studio(
    color: Color,
    *,
    radius: int,
    outline: float = 0,
    opacity: float = 1,
) -> Self
```

## Highlight

A named paint contribution for one lyric unit, independent of Track streams.

[Source](../../kara_templater/lyrics/highlights.py#L200)

```python
Highlight(
    id: str,
    unit: int,
    passes: tuple[highlights.HighlightPass, ...],
    paint: StatePatch,
    priority: int = 0,
    repeat: Literal['hold', 'reset'] = 'hold',
    end: Literal['hold', 'hide'] = 'hold',
    glow: LyricGlow = None,
    material: LinearGradient | Callable[[LyricLine, LyricTarget], LinearGradient | None] | None | Mapping[str, highlights.LyricGradient] = None,
    secondary_outline: SecondaryOutline | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `unit` | `int` | `required` |
| `passes` | `tuple[highlights.HighlightPass, ...]` | `required` |
| `paint` | `StatePatch` | `required` |
| `priority` | `int` | `0` |
| `repeat` | `Literal['hold', 'reset']` | `'hold'` |
| `end` | `Literal['hold', 'hide']` | `'hold'` |
| `glow` | `LyricGlow` | `None` |
| `material` | `LinearGradient \| Callable[[LyricLine, LyricTarget], LinearGradient \| None] \| None \| Mapping[str, highlights.LyricGradient]` | `None` |
| `secondary_outline` | `SecondaryOutline \| None` | `None` |

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

[Source](../../kara_templater/lyrics/highlights.py#L1077)

```python
HighlightArrival(
    *,
    highlights: tuple[highlights.Highlight, ...] | Callable[[LyricLine], tuple[highlights.Highlight, ...]],
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
| `highlights` | `tuple[highlights.Highlight, ...] \| Callable[[LyricLine], tuple[highlights.Highlight, ...]]` | `required` |
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

One horizontal pass, with absolute seconds and measured line-local x.

reverse starts the front at the right edge and grows ownership to the left.

round identifies repeat groups; reset discards previous rounds. rate receives
normalized progress. Declared breakpoints are seconds from the pass start.
A zero-duration pass reveals its entire region at its start, as ASS k0 does.

[Source](../../kara_templater/lyrics/highlights.py#L132)

```python
HighlightPass(
    time: TimeSpan,
    region: Region,
    round: int = 0,
    rate: Callable[[float], float] = linear_rate,
    breakpoints: tuple[float, ...] = (),
    inverse_rate: Callable[[float], float] | None = None,
    reverse: bool = False,
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
| `reverse` | `bool` | `False` |

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

## KaraokeTheme

Color role overrides shared by catalog effects and their inherited cues.

An omitted role inherits from the outer theme. Ordinary catalog effects
retain source outlines until an outline role is supplied. Duotone supplies
contrasting outlines for both sides of the wipe. Explicit effect colors win.
Before and after refer to the karaoke color transition at each point in
the glyph. With no wipe, the whole unit switches at once.

[Source](../../kara_templater/appearance.py#L21)

```python
KaraokeTheme(
    *,
    after_fill: Color | None = None,
    before_fill: Color | None = None,
    after_outline: Color | None = None,
    before_outline: Color | None = None,
    shine: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `after_fill` | `Color \| None` | `None` |
| `before_fill` | `Color \| None` | `None` |
| `after_outline` | `Color \| None` | `None` |
| `before_outline` | `Color \| None` | `None` |
| `shine` | `Color \| None` | `None` |

### KaraokeTheme.overlay

Override only roles supplied by the inner theme.

```python
KaraokeTheme.overlay(
    inner: KaraokeTheme,
) -> KaraokeTheme
```

## LinearGradient

An x/y gradient for fill, outline, or both; screen coordinates by default.

The hook shades independent fill and outline ramps continuously. Local
space attaches color stops to the untransformed drawing.

[Source](../../kara_templater/paint_fields.py#L95)

```python
LinearGradient(
    *,
    fill: ColorRamp | None = None,
    outline: ColorRamp | None = None,
    axis: Literal['x', 'y'] = 'x',
    space: Literal['screen', 'local'] = 'screen',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorRamp \| None` | `None` |
| `outline` | `ColorRamp \| None` | `None` |
| `axis` | `Literal['x', 'y']` | `'x'` |
| `space` | `Literal['screen', 'local']` | `'screen'` |

### LinearGradient.bounds

The script-space interval covered by the configured color ramps.

Type: `tuple[float, float]`.

## LyricGlow

Public type alias:

```python
type LyricGlow = Glow | Callable[[LyricLine, LyricTarget], Glow | None] | None
```

## LyricGradient

Evenly spaced colors on measured lyrics. Vertical colors span each glyph.
Horizontal colors span all body glyphs sharing an ASS style and their readings.

Pass as material to LyricHighlights.from_timing. Coordinates are derived
from undecorated glyph bounds. This factory produces an
ordinary LinearGradient and inherits its renderer restrictions.

[Source](../../kara_templater/lyrics/highlights.py#L76)

```python
LyricGradient(
    colors: tuple[Color, ...],
    axis: Literal['x', 'y'] = 'y',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `colors` | `tuple[Color, ...]` | `required` |
| `axis` | `Literal['x', 'y']` | `'y'` |

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

Each drawing uses ordinary per-layer alpha, with its glow clipped after blur.
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

[Source](../../kara_templater/lyrics/highlights.py#L621)

```python
LyricHighlights(
    *,
    highlights: tuple[highlights.Highlight, ...] | Callable[[LyricLine], tuple[highlights.Highlight, ...]],
    mode: Literal['union', 'priority', 'layer'] = 'union',
    glow: LyricGlow = None,
    base_paint: StatePatch = StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, face_opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None),
    base_material: LinearGradient | Callable[[LyricLine, LyricTarget], LinearGradient | None] | None | Mapping[str, highlights.LyricGradient] = None,
    hook_feather: float | LengthExpr = 0,
    edge_duration: float = 0.02,
    blend_glow: bool = True,
    front_color: Color | None = None,
    secondary_outline: SecondaryOutline | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `highlights` | `tuple[highlights.Highlight, ...] \| Callable[[LyricLine], tuple[highlights.Highlight, ...]]` | `required` |
| `mode` | `Literal['union', 'priority', 'layer']` | `'union'` |
| `glow` | `LyricGlow` | `None` |
| `base_paint` | `StatePatch` | `StatePatch(position=None, scale=None, rotation=None, skew=None, opacity=None, face_opacity=None, fill=None, outline=None, border=None, blur=None, shadow=None)` |
| `base_material` | `LinearGradient \| Callable[[LyricLine, LyricTarget], LinearGradient \| None] \| None \| Mapping[str, highlights.LyricGradient]` | `None` |
| `hook_feather` | `float \| LengthExpr` | `0` |
| `edge_duration` | `float` | `0.02` |
| `blend_glow` | `bool` | `True` |
| `front_color` | `Color \| None` | `None` |
| `secondary_outline` | `SecondaryOutline \| None` | `None` |

### LyricHighlights.__call__

Return decorated visuals, reserving each target's shifted pass intervals.

Pass times use original source seconds. A copied target's delay shifts
both rendering and required_display; source timing spans stay unchanged.

```python
LyricHighlights.__call__(
    line: LyricLine,
) -> LyricLine
```

### LyricHighlights.from_timing

Sweep source timing across body/ruby without authoring clip geometry.

secondary_outline surrounds both states. after_secondary_outline sets the rim after the transition.
Both can be combined with glow.
With reverse=True, each timed unit fills from its right edge.
With wipe=False, each timed unit switches paint at completion.
Timing progress uses undecorated measured text bounds. For a single
linear interval in clip mode, outline/glow margins are traversed in
separate shoulders before/after timing, reserved automatically. edge_duration
sets their duration in seconds (default 0.02). segment_colors maps
(unit index, reading index) to highlight colors. Mapped segments sweep successive
equal portions of their body, holding their position through rests.
ruby_fill overrides the highlight fill of all readings independently.
blend_glow=False gives each side a clipped halo with its own color.
Contiguous timed readings divide their host wipe equally at reading
checkpoints. With ruby_reading_units=True, visible reading characters instead
receive equal distances and empty readings hold position. Each reading retains its individual timing interval.
Known rectangle keyframes allow continuous native ASS lowering. Repeated
intervals retain the general ownership evaluator. Source timing clocks stay intact.
base_material paints the base drawing. material paints the highlight drawing, leaving the separate glow
color intact. It accepts a LinearGradient or a (line, target) factory called
once during preparation; use LyricGradient for measured vertical colors.
Local gradients currently require a
positive single timing interval and axis-aligned scale/translation.
base_paint changes only the base drawing; highlight layers retain the
original appearance before applying paint. Use base_paint with opacity=0
to reveal text instead of recoloring an already visible baseline.

```python
LyricHighlights.from_timing(
    paint: StatePatch,
    *,
    wipe: bool = True,
    reverse: bool = False,
    ruby_reading_units: bool = False,
    glow: LyricGlow = None,
    base_glow: LyricGlow = None,
    secondary_outline: SecondaryOutline | None = None,
    after_secondary_outline: SecondaryOutline | None = None,
    base_paint: StatePatch | None = None,
    base_material: LinearGradient | Callable[[LyricLine, LyricTarget], LinearGradient | None] | None | Mapping[str, highlights.LyricGradient] = None,
    material: LinearGradient | Callable[[LyricLine, LyricTarget], LinearGradient | None] | None | Mapping[str, highlights.LyricGradient] = None,
    hook_feather: float | LengthExpr = 0,
    segment_colors: Mapping[tuple[int, int], Color] | None = None,
    ruby_fill: Color | None = None,
    edge_duration: float = 0.02,
    blend_glow: bool = True,
    front_color: Color | None = None,
) -> highlights.LyricHighlights
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

[Source](../../kara_templater/composition.py#L105)

```python
Paint(
    fill: Color = Color(red=255, green=255, blue=255),
    outline: Color = Color(red=0, green=0, blue=0),
    border: float = 0,
    opacity: float = 1,
    glow: Glow | None = None,
    secondary_outline: SecondaryOutline | None = None,
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
| `secondary_outline` | `SecondaryOutline \| None` | `None` |

## PaintPair

The Paint values before and after the karaoke transition.

Paint changes do not rewrite the source timing.

[Source](../../kara_templater/appearance.py#L10)

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

## SecondaryOutline

A solid outer lyric stroke. Width adds script pixels beyond the primary outline.

A zero width hides the stroke. Its color is independent of fill, primary outline and glow.

[Source](../../kara_templater/composition.py#L91)

```python
SecondaryOutline(
    color: Color,
    width: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `Color` | `required` |
| `width` | `float` | `required` |

## ShaderPaint

GLSL applied per covered pixel after the normal material and feather.

The body can modify RGB ink and opacity alpha. local and screen are script
pixel coordinates, time is signed seconds from the object clock, coverage
is the native mask, and component is 0 for fill, 1 for outline, 2 for
shadow. Numeric parameters are accessible through item(data + offset).
Optional functions can contain Metashade-generated GLSL definitions.

[Source](../../kara_templater/paint_fields.py#L34)

```python
ShaderPaint(
    source: str,
    parameters: tuple[float, ...] = (),
    functions: str = '',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `str` | `required` |
| `parameters` | `tuple[float, ...]` | `()` |
| `functions` | `str` | `''` |

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

## paint_pair_from_style

Decode the ASS secondary and primary colors as the before and after paints.

[Source](../../kara_templater/appearance.py#L55)

```python
paint_pair_from_style(
    style: Style,
) -> PaintPair
```
