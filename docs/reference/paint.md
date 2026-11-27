# Colors and appearance

RGB colors, fills, outlines, spatial paint fields, WGSL materials, and lyric highlight styles.

Related guides: [Colour and materials](../guides/materials.md) · [All public symbols](README.md#symbol-index)

## Contents

**Classes:** [`Color`](#color) · [`ColorRamp`](#colorramp) · [`ColorStop`](#colorstop) · [`Extrusion`](#extrusion) · [`Glow`](#glow) · [`Highlight`](#highlight) · [`HighlightArrival`](#highlightarrival) · [`HighlightPass`](#highlightpass) · [`KaraokeTheme`](#karaoketheme) · [`LinearGradient`](#lineargradient) · [`LyricGradient`](#lyricgradient) · [`LyricHighlights`](#lyrichighlights) · [`LyricSweep`](#lyricsweep) · [`MaterialClip`](#materialclip) · [`MaterialEffect`](#materialeffect) · [`Paint`](#paint) · [`PaintControl`](#paintcontrol) · [`PaintInput`](#paintinput) · [`PaintPair`](#paintpair) · [`SecondaryOutline`](#secondaryoutline) · [`ShaderPaint`](#shaderpaint)

**Functions:** [`paint_pair_from_style`](#paint_pair_from_style)

**Types & constants:** [`BLACK`](#black) · [`BLUE`](#blue) · [`CYAN`](#cyan) · [`GRAY`](#gray) · [`GREEN`](#green) · [`LyricGlow`](#lyricglow) · [`MAGENTA`](#magenta) · [`ORANGE`](#orange) · [`PINK`](#pink) · [`PURPLE`](#purple) · [`PaintValue`](#paintvalue) · [`RED`](#red) · [`WHITE`](#white) · [`YELLOW`](#yellow)

## BLACK

*constant*

```python
BLACK = Color(red=0, green=0, blue=0)
```

## BLUE

*constant*

```python
BLUE = Color(red=0, green=0, blue=255)
```

## CYAN

*constant*

```python
CYAN = Color(red=0, green=255, blue=255)
```

## Color

*dataclass* · [Source](../../kara_templater/composition.py#L13)

An immutable RGB color with integer channels in 0 through 255.

hex accepts exactly #RRGGBB; ASS BGR conversion is performed at serialization
boundaries.

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

*dataclass* · [Source](../../kara_templater/paint_fields.py#L184)

Piecewise linear colors at absolute script coordinates; ends clamp.

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

*dataclass* · [Source](../../kara_templater/paint_fields.py#L170)

An RGB color at a finite script-space position along a paint field axis.

ColorRamp requires ordered stops.

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

*dataclass* · [Source](../../kara_templater/paint_fields.py#L19)

A solid side swept from a drawing's hard silhouette in local script pixels.

Offset is the vector from front to back. The side follows the face's
transforms and opacity, and keeps its own color during a lyric wipe.
back_color shades the side from color at the face to back_color at full depth.
Zero offset gives a flat drawing. Browser preview and playback shaders support this appearance.

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

*constant*

```python
GRAY = Color(red=128, green=128, blue=128)
```

## GREEN

*constant*

```python
GREEN = Color(red=0, green=255, blue=0)
```

## Glow

*dataclass* · [Source](../../kara_templater/composition.py#L46)

A paint glow with RGB color, nonnegative blur/border in script pixels, and opacity in 0 through 1.

It is separate from the body fill and outline.

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

*dataclass* · [Source](../../kara_templater/lyrics/highlights.py#L207)

A named paint contribution for one lyric unit, independent of Track streams.

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

*dataclass* · [Source](../../kara_templater/lyrics/highlights.py#L1207)

Bind common animations to measured character crossings before allocation.

Use as LyricRule.anchor. first selects the earliest highlight per repeat round;
each keeps every highlight, and names restricts either selection explicitly.
Thresholds use original measured geometry, independent of animation and paint
priority. The interval length is full character traversal. A partial traversal
requires duration here; LyricRule.duration may further override that length.
Nonlinear passes require a declared inverse_rate. No runtime state is retained.

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

*dataclass* · [Source](../../kara_templater/lyrics/highlights.py#L139)

One horizontal pass, with absolute seconds and measured line-local x.

reverse starts the front at the right edge and grows ownership to the left.

round identifies repeat groups; reset discards previous rounds. rate receives
normalized progress. Declared breakpoints are seconds from the pass start.
A zero-duration pass reveals its entire region at its start, as ASS k0 does.

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

*dataclass* · [Source](../../kara_templater/appearance.py#L21)

Color role overrides shared by catalog effects and their inherited cues.

An omitted role inherits from the outer theme. Ordinary catalog effects
retain source outlines until an outline role is supplied. Duotone supplies
contrasting outlines for both sides of the wipe. Explicit effect colors win.
Before and after refer to the karaoke color transition at each point in
the glyph. With no wipe, the whole unit switches at once.

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

*dataclass* · [Source](../../kara_templater/paint_fields.py#L210)

An x/y gradient for fill, outline, or both; screen coordinates by default.

The scene shader shades independent fill and outline ramps continuously. Local
space attaches color stops to the untransformed drawing.

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

*type alias*

```python
type LyricGlow = Glow | Callable[[LyricLine, LyricTarget], Glow | None] | None
```

## LyricGradient

*dataclass* · [Source](../../kara_templater/lyrics/highlights.py#L83)

Evenly spaced colors on measured lyrics. Vertical colors span each glyph.
Horizontal colors span all body glyphs sharing an ASS style and their readings.

Pass as material to LyricHighlights.from_timing. Coordinates are derived
from undecorated glyph bounds. This factory produces an
ordinary LinearGradient and inherits its renderer restrictions.

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

*dataclass* · [Source](../../kara_templater/lyrics/highlights.py#L646)

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
    sweep_angle: float | None = None,
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
| `sweep_angle` | `float \| None` | `None` |

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
With wipe=False, each timed unit switches paint at its onset.
Horizontal sweeps follow the font style by default: italic or oblique
text uses a slanted front. Set sweep_angle to override its angle in
degrees, or use 0 for a straight front. Positive angles tilt its top
to the right, independent of the sweep direction.
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
    sweep_angle: float | None = None,
) -> highlights.LyricHighlights
```

## LyricSweep

*dataclass* · [Source](../../kara_templater/lyrics/sweep.py#L91)

A measured lyric sweep that can paint either version of a glyph run.

Get it from `KaraokeEffects.sweep()`. Its absolute clock includes note
checkpoints and rests. Apply it independently to the old and new layouts,
then animate those drawings under ordinary scene groups.

```python
LyricSweep()
```

### LyricSweep.interval

The first entrance and last completion in absolute scene seconds.

Type: `TimeSpan`.

### LyricSweep.paint

Return the measured drawings with the shared sweep on their fill.

Supply clusters from one measured horizontal run in their original
coordinate space. The ink bounds define the new sweep extent and the
run's first glyph size resolves relative brush widths. After binding,
drawings can use different lifetimes and parent transforms. Their
explicit clock origins preserve the sweep on a late-appearing drawing.
The material is supported by browser and Hook output.

```python
LyricSweep.paint(
    glyphs: tuple[layout.PositionedText, ...],
) -> tuple[TextObject, ...]
```

## MAGENTA

*constant*

```python
MAGENTA = Color(red=255, green=0, blue=255)
```

## MaterialClip

*dataclass* · [Source](../../kara_templater/paint_fields.py#L147)

Apply a WGSL effect to one or all coverage planes over a local interval.

Start is relative to the object's clock, and an omitted duration extends
to the end of its lifetime. Effects on a plane run in declaration order.

```python
MaterialClip(
    *,
    effect: MaterialEffect,
    start: float = 0.0,
    duration: float | None = None,
    target: Literal['fill', 'outline', 'shadow', 'all'] = 'fill',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `effect` | `MaterialEffect` | `required` |
| `start` | `float` | `0.0` |
| `duration` | `float \| None` | `None` |
| `target` | `Literal['fill', 'outline', 'shadow', 'all']` | `'fill'` |

## MaterialEffect

*class* · [Source](../../kara_templater/paint_fields.py#L124)

A reusable WGSL function evaluated after sampling a coverage plane.

Define ``shade(material: vec4<f32>, ctx: KaraPaintContext, ...)`` to
return straight RGB and opacity. The renderer provides ``ctx.local`` and
``ctx.screen`` in script pixels, ``ctx.coverage`` in 0..1, ``ctx.time`` in
seconds from the effect start, and ``ctx.progress`` in 0..1. Component
indices are 0 for fill, 1 for outline, 2 for shadow and 3 for extrusion.
Additional arguments follow ``parameters()`` in order. Float, Color and
Vec2 become f32, vec3<f32> in 0..1, and vec2<f32> respectively.

```python
MaterialEffect()
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `wgsl` | `ClassVar[str]` | `instance attribute` |
| `entry_point` | `ClassVar[str]` | `instance attribute` |

### MaterialEffect.parameters

Return the values supplied as arguments after material and context.

```python
MaterialEffect.parameters() -> tuple[PaintValue | PaintInput, ...]
```

## ORANGE

*constant*

```python
ORANGE = Color(red=255, green=165, blue=0)
```

## PINK

*constant*

```python
PINK = Color(red=255, green=192, blue=203)
```

## PURPLE

*constant*

```python
PURPLE = Color(red=128, green=0, blue=128)
```

## Paint

*dataclass* · [Source](../../kara_templater/composition.py#L105)

Resolved fill, outline, border width, opacity, and optional glow for one drawing.

Distances use script pixels and opacity uses 0 through 1.

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

## PaintControl

*dataclass* · [Source](../../kara_templater/paint_fields.py#L65)

Describe a browser control for a named paint input.

Bounds are inclusive and apply to a scalar or to both vector axes.
Step is the suggested increment for a preview control. Labels, units,
and group names are display text. Order sorts controls within a group.

```python
PaintControl(
    bounds: tuple[float, float] | None = None,
    step: float | None = None,
    unit: str = '',
    label: str = '',
    group: str = '',
    order: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `bounds` | `tuple[float, float] \| None` | `None` |
| `step` | `float \| None` | `None` |
| `unit` | `str` | `''` |
| `label` | `str` | `''` |
| `group` | `str` | `''` |
| `order` | `int` | `0` |

## PaintInput

*dataclass* · [Source](../../kara_templater/paint_fields.py#L92)

A named material value that a preview host may update while playing.

Uses of the same name share one value and must have matching defaults
and control declarations. An omitted control keeps the host's existing
presentation for unbounded inputs.

```python
PaintInput(
    name: str,
    value: PaintValue,
    control: PaintControl | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `name` | `str` | `required` |
| `value` | `PaintValue` | `required` |
| `control` | `PaintControl \| None` | `None` |

## PaintPair

*dataclass* · [Source](../../kara_templater/appearance.py#L10)

The Paint values before and after the karaoke transition.

Paint changes do not rewrite the source timing.

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

## PaintValue

*type alias*

```python
type PaintValue = float | Color | Vec2
```

## RED

*constant*

```python
RED = Color(red=255, green=0, blue=0)
```

## SecondaryOutline

*dataclass* · [Source](../../kara_templater/composition.py#L91)

A solid outer lyric stroke. Width adds script pixels beyond the primary outline.

A zero width hides the stroke. Its color is independent of fill, primary outline and glow.

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

*dataclass* · [Source](../../kara_templater/paint_fields.py#L34)

GLSL applied per covered pixel after the normal material and feather.

The body can modify RGB ink and opacity alpha. local and screen are script
pixel coordinates, time is signed seconds from the object clock, coverage
is the native mask, and component is 0 for fill, 1 for outline, 2 for
shadow. Numeric parameters are accessible through item(data + offset).
Optional functions can contain Metashade-generated GLSL definitions.

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

*constant*

```python
WHITE = Color(red=255, green=255, blue=255)
```

## YELLOW

*constant*

```python
YELLOW = Color(red=255, green=255, blue=0)
```

## paint_pair_from_style

*function* · [Source](../../kara_templater/appearance.py#L55)

Decode the ASS secondary and primary colors as the before and after paints.

```python
paint_pair_from_style(
    style: Style,
) -> PaintPair
```
