# Colors and appearance

RGB colors, typed appearance, spatial fields, and material animation. Pixel distances and opacity in 0..1 are authoring values; ASS encodings are output details. See [materials](../guides/materials.md).

[All public symbols](README.md#symbol-index)

## Contents

- [BLACK](#black)
- [BLUE](#blue)
- [Blur](#blur)
- [Body](#body)
- [CYAN](#cyan)
- [CharacterPaint](#characterpaint)
- [Color](#color)
- [ColorKeyframe](#colorkeyframe)
- [ColorKeyframes](#colorkeyframes)
- [ColorRamp](#colorramp)
- [ColorSpan](#colorspan)
- [ColorStop](#colorstop)
- [ColorStyle](#colorstyle)
- [ColorTransition](#colortransition)
- [ColorValue](#colorvalue)
- [GRAY](#gray)
- [GREEN](#green)
- [Glow](#glow)
- [INHERIT](#inherit)
- [LinearGradient](#lineargradient)
- [MAGENTA](#magenta)
- [NumberStyle](#numberstyle)
- [ORANGE](#orange)
- [PINK](#pink)
- [PURPLE](#purple)
- [Paint](#paint)
- [PaintBand](#paintband)
- [PaintBounds](#paintbounds)
- [PaintField](#paintfield)
- [PaintPair](#paintpair)
- [PaintStyle](#paintstyle)
- [PaintedRegion](#paintedregion)
- [RED](#red)
- [Ruby](#ruby)
- [RubyPaint](#rubypaint)
- [RubySpan](#rubyspan)
- [SoftSweep](#softsweep)
- [StyleKeyword](#stylekeyword)
- [StyleOverrides](#styleoverrides)
- [StyleProperties](#styleproperties)
- [StyleSheet](#stylesheet)
- [StyleValues](#stylevalues)
- [TextSpan](#textspan)
- [TextStyle](#textstyle)
- [TrackPaint](#trackpaint)
- [UNSET](#unset)
- [WHITE](#white)
- [YELLOW](#yellow)
- [compose_highlights](#compose_highlights)
- [resolve_paints](#resolve_paints)
- [resolve_ruby_paints](#resolve_ruby_paints)
- [rule](#rule)

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

## Blur

A configurable Track glow with color, pixel radius/width, and opacity.

Resolve against an inherited glow while preserving explicit UNSET/INHERIT
semantics.

[Source](../../kara_templater/text_style.py#L38)

```python
Blur(
    *,
    color: ColorStyle = StyleKeyword.UNSET,
    radius: NumberStyle = StyleKeyword.UNSET,
    width: NumberStyle = StyleKeyword.UNSET,
    opacity: NumberStyle = StyleKeyword.UNSET,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `ColorStyle` | `StyleKeyword.UNSET` |
| `radius` | `NumberStyle` | `StyleKeyword.UNSET` |
| `width` | `NumberStyle` | `StyleKeyword.UNSET` |
| `opacity` | `NumberStyle` | `StyleKeyword.UNSET` |

### Blur.resolve

Resolve explicit, inherited, and unset glow fields against an optional existing glow.

```python
Blur.resolve(
    base: Glow,
    inherited: Glow,
) -> Glow
```

## Body

Track body text configuration with TextStyle, source-wide TextSpan declarations, and optional style classes.

Each Track binding uses fresh configuration without changing the source text or
timing.

[Source](../../kara_templater/components.py#L102)

```python
Body(
    *,
    style: TextStyle | None = None,
    spans: Iterable[TextSpan] = (),
    id: str | None = None,
    classes: str | Iterable[str] = (),
    fill: ColorStyle = StyleKeyword.UNSET,
    stroke: ColorStyle = StyleKeyword.UNSET,
    stroke_width: NumberStyle = StyleKeyword.UNSET,
    opacity: NumberStyle = StyleKeyword.UNSET,
    font_size: NumberStyle = StyleKeyword.UNSET,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `kind` | `str` | `instance attribute` |
| `id` | `str \| None` | `instance attribute` |
| `classes` | `set[str]` | `instance attribute` |
| `children` | `tuple[Component, ...]` | `instance attribute` |
| `parent` | `Component \| None` | `instance attribute` |
| `attributes` | `dict[str, str \| int]` | `instance attribute` |

### Body.add_class

Add validated nonempty style class names and return this component.

```python
Body.add_class(
    *names: str,
) -> Self
```

### Body.walk

Iterate this style component and its descendants in declaration order.

```python
Body.walk() -> Iterator[Component]
```

## CYAN

Public constant:

```python
CYAN = Color(red=0, green=255, blue=255)
```

## CharacterPaint

A drawable character paired with its resolved unsung and sung paints.

Character geometry and source range remain unchanged by paint selection.

[Source](../../kara_templater/appearance.py#L44)

```python
CharacterPaint(
    character: DrawableCharacter,
    paints: PaintPair,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `character` | `DrawableCharacter` | `required` |
| `paints` | `PaintPair` | `required` |

### CharacterPaint.highlighted

Return the sung paint or an explicit highlight-track paint override.

```python
CharacterPaint.highlighted(
    track_override: Paint | None = None,
) -> Paint
```

## Color

An immutable RGB color with integer channels in 0 through 255.

hex accepts exactly #RRGGBB; ASS BGR conversion is performed at serialization
boundaries.

[Source](../../kara_templater/composition.py#L15)

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

## ColorKeyframe

A color target at a normalized fraction or a millisecond TimeRef, with an incoming easing curve.

It is resolved against the selected singing/display interval.

[Source](../../kara_templater/material_animation.py#L72)

```python
ColorKeyframe(
    at: float | TimeRef,
    value: Color,
    rate: Callable[[float], float] = linear,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `at` | `float \| TimeRef` | `required` |
| `value` | `Color` | `required` |
| `rate` | `Callable[[float], float]` | `linear` |

### ColorKeyframe.rate

Return normalized progress unchanged for linear interpolation.

```python
ColorKeyframe.rate(
    p: float,
) -> float
```

## ColorKeyframes

An ordered sequence of color targets resolved for a material animation interval.

Keyframe timing and source clocks remain explicit.

[Source](../../kara_templater/material_animation.py#L92)

```python
ColorKeyframes(
    *frames: ColorKeyframe,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `frames` | `tuple[ColorKeyframe, ...]` | `required` |

### ColorKeyframes.resolve

Resolve normalized fractions and TimeRef anchors against the selected millisecond interval.

```python
ColorKeyframes.resolve(
    interval: tuple[float, float],
    segments: tuple[Segment, ...],
    window: DisplayWindow,
) -> tuple[tuple[float, Color, Callable[[float], float]], ...]
```

## ColorRamp

Piecewise linear colors at absolute script coordinates; ends clamp.

[Source](../../kara_templater/paint_fields.py#L82)

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

## ColorSpan

Override before/after paint for a unit-local TextRange with explicit priority.

Selected boundaries must preserve independently drawable clusters.

[Source](../../kara_templater/appearance.py#L25)

```python
ColorSpan(
    source: TextRange,
    before: Paint | None = None,
    after: Paint | None = None,
    priority: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `TextRange` | `required` |
| `before` | `Paint \| None` | `None` |
| `after` | `Paint \| None` | `None` |
| `priority` | `int` | `0` |

## ColorStop

An RGB color at a finite script-space position along a paint field axis.

ColorRamp requires ordered stops.

[Source](../../kara_templater/paint_fields.py#L68)

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

## ColorStyle

Public type alias:

```python
type ColorStyle = Color | str | StyleKeyword
```

## ColorTransition

Interpolate RGB channels between two colors using normalized progress and an optional easing rate.

Result channels are rounded into the valid integer range.

[Source](../../kara_templater/material_animation.py#L50)

```python
ColorTransition(
    start: Color,
    end: Color,
    rate: Callable[[float], float] = linear,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `Color` | `required` |
| `end` | `Color` | `required` |
| `rate` | `Callable[[float], float]` | `linear` |

### ColorTransition.__call__

Evaluate eased normalized progress and return an RGB color with rounded channels.

```python
ColorTransition.__call__(
    progress: float,
) -> Color
```

### ColorTransition.rate

Return normalized progress unchanged for linear interpolation.

```python
ColorTransition.rate(
    p: float,
) -> float
```

## ColorValue

Public type alias:

```python
type ColorValue = Color | tuple[Color, Color] | ColorTransition | ColorKeyframes | Callable[[float], Color]
```

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

[Source](../../kara_templater/composition.py#L48)

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

## INHERIT

Public constant:

```python
INHERIT = StyleKeyword.INHERIT
```

## LinearGradient

A script-space x/y gradient for fill, outline, or both.

Integer step controls color band width and the declared maximum band count.

[Source](../../kara_templater/paint_fields.py#L135)

```python
LinearGradient(
    *,
    fill: ColorRamp | None = None,
    outline: ColorRamp | None = None,
    axis: Literal['x', 'y'] = 'x',
    step: int = 1,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorRamp \| None` | `None` |
| `outline` | `ColorRamp \| None` | `None` |
| `axis` | `Literal['x', 'y']` | `'x'` |
| `step` | `int` | `1` |

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

## MAGENTA

Public constant:

```python
MAGENTA = Color(red=255, green=0, blue=255)
```

## NumberStyle

Public type alias:

```python
type NumberStyle = float | StyleKeyword
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

[Source](../../kara_templater/composition.py#L76)

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

## PaintBounds

Required only when geometry callbacks have no statically known bound.

[Source](../../kara_templater/material_animation.py#L160)

```python
PaintBounds(
    *,
    stroke_width: float | None = None,
    blur_radius: float | None = None,
    blur_width: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `stroke_width` | `float \| None` | `None` |
| `blur_radius` | `float \| None` | `None` |
| `blur_width` | `float \| None` | `None` |

### PaintBounds.for_property

Return the declared maximum for a bounded material property, if supplied.

```python
PaintBounds.for_property(
    name: Literal['fill', 'stroke', 'stroke_width', 'blur_color', 'blur_radius', 'blur_width', 'blur_opacity'],
) -> float | None
```

## PaintField

Pure local-time field. Bands must exactly partition the requested domain.

Breakpoints delimit temporal discontinuities and changes of motion. An empty
tuple declares a static field. max_bands bounds every invocation.

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

[Source](../../kara_templater/appearance.py#L11)

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

## PaintStyle

Track paint-only declarations for fill, stroke, width, opacity, and glow.

It cannot change font layout; resolve produces a validated Paint.

[Source](../../kara_templater/text_style.py#L68)

```python
PaintStyle(
    *,
    fill: ColorStyle = StyleKeyword.UNSET,
    stroke: ColorStyle = StyleKeyword.UNSET,
    stroke_width: NumberStyle = StyleKeyword.UNSET,
    opacity: NumberStyle = StyleKeyword.UNSET,
    blur: Blur | StyleKeyword | None = StyleKeyword.UNSET,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorStyle` | `StyleKeyword.UNSET` |
| `stroke` | `ColorStyle` | `StyleKeyword.UNSET` |
| `stroke_width` | `NumberStyle` | `StyleKeyword.UNSET` |
| `opacity` | `NumberStyle` | `StyleKeyword.UNSET` |
| `blur` | `Blur \| StyleKeyword \| None` | `StyleKeyword.UNSET` |

### PaintStyle.resolve

Resolve this sparse paint declaration against a base Paint and explicit inheritance source.

```python
PaintStyle.resolve(
    base: Paint,
    *,
    inherited: Paint | None = None,
) -> Paint
```

## PaintedRegion

A disjoint highlighted body region with its paints ordered from bottom to top.

It describes composition semantics before choosing an ASS encoding.

[Source](../../kara_templater/composition.py#L113)

```python
PaintedRegion(
    unit_index: int,
    region: Region,
    paints: tuple[Paint, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `unit_index` | `int` | `required` |
| `region` | `Region` | `required` |
| `paints` | `tuple[Paint, ...]` | `required` |

## RED

Public constant:

```python
RED = Color(red=255, green=0, blue=0)
```

## Ruby

Track reading configuration with font/paint style, reading spans, vertical offset, and following policy.

hide disables the reading while retaining its declaration.

[Source](../../kara_templater/components.py#L137)

```python
Ruby(
    *,
    offset_y: float = 0,
    follow: Literal['none', 'syllable'] | Follow = 'none',
    style: TextStyle | None = None,
    spans: Iterable[RubySpan] = (),
    id: str | None = None,
    classes: str | Iterable[str] = (),
    fill: ColorStyle = StyleKeyword.UNSET,
    stroke: ColorStyle = StyleKeyword.UNSET,
    stroke_width: NumberStyle = StyleKeyword.UNSET,
    opacity: NumberStyle = StyleKeyword.UNSET,
    font_size: NumberStyle = StyleKeyword.UNSET,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `kind` | `str` | `instance attribute` |
| `id` | `str \| None` | `instance attribute` |
| `classes` | `set[str]` | `instance attribute` |
| `children` | `tuple[Component, ...]` | `instance attribute` |
| `parent` | `Component \| None` | `instance attribute` |
| `attributes` | `dict[str, str \| int]` | `instance attribute` |

### Ruby.add_class

Add validated nonempty style class names and return this component.

```python
Ruby.add_class(
    *names: str,
) -> Self
```

### Ruby.hide

Disable reading output while retaining its style and source-span declaration.

```python
Ruby.hide() -> None
```

### Ruby.walk

Iterate this style component and its descendants in declaration order.

```python
Ruby.walk() -> Iterator[Component]
```

## RubyPaint

An explicit paint pair for the reading at a unit and segment index.

It overrides inherited body paint for that complete reading.

[Source](../../kara_templater/appearance.py#L100)

```python
RubyPaint(
    unit_index: int,
    segment_index: int,
    paints: PaintPair,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `unit_index` | `int` | `required` |
| `segment_index` | `int` | `required` |
| `paints` | `PaintPair` | `required` |

## RubySpan

A codepoint range within one source reading, independent of its layout.

[Source](../../kara_templater/text_style.py#L170)

```python
RubySpan(
    unit_index: int,
    segment_index: int,
    style: PaintStyle = PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET),
    overlay: PaintStyle = PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET),
    start: int = 0,
    end: int | None = None,
    classes: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `unit_index` | `int` | `required` |
| `segment_index` | `int` | `required` |
| `style` | `PaintStyle` | `PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET)` |
| `overlay` | `PaintStyle` | `PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET)` |
| `start` | `int` | `0` |
| `end` | `int \| None` | `None` |
| `classes` | `tuple[str, ...]` | `()` |

## SoftSweep

Left-to-right (or top-to-bottom) sweep; pairs are (unsung, sung).

Widths are script pixels. The front travels past both ends so the declared
span is completely unsung at start and completely sung at start+duration.
start and duration are local seconds from the owning object's birth.

[Source](../../kara_templater/paint_fields.py#L189)

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

### SoftSweep.rate

Return normalized Scene animation progress unchanged.

```python
SoftSweep.rate(
    progress: float,
) -> float
```

## StyleKeyword

Explicit UNSET and INHERIT declarations for the style cascade.

UNSET contributes no override; INHERIT reads the relevant source/parent value.

[Source](../../kara_templater/stylesheet.py#L19)

### Values

- `StyleKeyword.INHERIT` = `'inherit'`
- `StyleKeyword.UNSET` = `'unset'`

## StyleOverrides

Typed mutable base and sung-state style declarations.

Only supported paint and font-size fields participate in the cascade.

[Source](../../kara_templater/stylesheet.py#L160)

```python
StyleOverrides(
    **values: Unpack[StyleProperties],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `sung` | `StyleValues` | `instance attribute` |

### StyleOverrides.fill

Read or set the RGB fill declaration, including explicit style keywords.

Type: `Color \| StyleKeyword`.

### StyleOverrides.font_size

Read or set the positive font-size declaration in script pixels or a style keyword.

Type: `NumberStyle`.

### StyleOverrides.opacity

Read or set opacity in 0 through 1, including explicit style keywords.

Type: `NumberStyle`.

### StyleOverrides.stroke

Read or set the RGB outline declaration, including explicit style keywords.

Type: `Color \| StyleKeyword`.

### StyleOverrides.stroke_width

Read or set the nonnegative outline-width declaration in script pixels or a style keyword.

Type: `NumberStyle`.

## StyleProperties

Typed optional style-declaration keys used by constructors and rule().

Color and scalar fields retain explicit UNSET/INHERIT support.

[Source](../../kara_templater/stylesheet.py#L60)

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorStyle` | `optional key` |
| `stroke` | `ColorStyle` | `optional key` |
| `stroke_width` | `NumberStyle` | `optional key` |
| `opacity` | `NumberStyle` | `optional key` |
| `font_size` | `NumberStyle` | `optional key` |

## StyleSheet

An immutable ordered collection of selector rules for Track components and

source ranges. Rules combine specificity with explicit declarations and sung-
state scope.

[Source](../../kara_templater/stylesheet.py#L275)

```python
StyleSheet(
    *rules: StyleRule,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `rules` | `tuple[StyleRule, ...]` | `required` |

## StyleValues

Explicit declarations. Assigning UNSET removes this level's override.

[Source](../../kara_templater/stylesheet.py#L133)

```python
StyleValues(
    **values: Unpack[StyleProperties],
)
```

### StyleValues.fill

Read or set the RGB fill declaration, including explicit style keywords.

Type: `Color \| StyleKeyword`.

### StyleValues.font_size

Read or set the positive font-size declaration in script pixels or a style keyword.

Type: `NumberStyle`.

### StyleValues.opacity

Read or set opacity in 0 through 1, including explicit style keywords.

Type: `NumberStyle`.

### StyleValues.stroke

Read or set the RGB outline declaration, including explicit style keywords.

Type: `Color \| StyleKeyword`.

### StyleValues.stroke_width

Read or set the nonnegative outline-width declaration in script pixels or a style keyword.

Type: `NumberStyle`.

## TextSpan

Codepoint range in the complete body text; later spans take precedence.

[Source](../../kara_templater/text_style.py#L143)

```python
TextSpan(
    start: int,
    end: int,
    style: PaintStyle = PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET),
    overlay: PaintStyle = PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET),
    classes: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `int` | `required` |
| `end` | `int` | `required` |
| `style` | `PaintStyle` | `PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET)` |
| `overlay` | `PaintStyle` | `PaintStyle(fill=StyleKeyword.UNSET, stroke=StyleKeyword.UNSET, stroke_width=StyleKeyword.UNSET, opacity=StyleKeyword.UNSET, blur=StyleKeyword.UNSET)` |
| `classes` | `tuple[str, ...]` | `()` |

## TextStyle

Track text appearance with PaintStyle fields plus optional font size, family, and spacing.

Layout-changing values are applied before measurement.

[Source](../../kara_templater/text_style.py#L112)

```python
TextStyle(
    *,
    fill: ColorStyle = StyleKeyword.UNSET,
    stroke: ColorStyle = StyleKeyword.UNSET,
    stroke_width: NumberStyle = StyleKeyword.UNSET,
    opacity: NumberStyle = StyleKeyword.UNSET,
    blur: Blur | StyleKeyword | None = StyleKeyword.UNSET,
    font_size: NumberStyle = StyleKeyword.UNSET,
    font_name: str | None = None,
    spacing: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fill` | `ColorStyle` | `StyleKeyword.UNSET` |
| `stroke` | `ColorStyle` | `StyleKeyword.UNSET` |
| `stroke_width` | `NumberStyle` | `StyleKeyword.UNSET` |
| `opacity` | `NumberStyle` | `StyleKeyword.UNSET` |
| `blur` | `Blur \| StyleKeyword \| None` | `StyleKeyword.UNSET` |
| `font_size` | `NumberStyle` | `StyleKeyword.UNSET` |
| `font_name` | `str \| None` | `None` |
| `spacing` | `float \| None` | `None` |

### TextStyle.apply_to_style

Apply layout-affecting font size, family, and spacing before text measurement.

```python
TextStyle.apply_to_style(
    style: Style,
) -> Style
```

### TextStyle.resolve

Resolve this sparse paint declaration against a base Paint and explicit inheritance source.

```python
TextStyle.resolve(
    base: Paint,
    *,
    inherited: Paint | None = None,
) -> Paint
```

## TrackPaint

A HighlightTrack paired with a resolved Paint and integer composition priority.

It is consumed by the low-level highlight compositor.

[Source](../../kara_templater/composition.py#L97)

```python
TrackPaint(
    track: HighlightTrack,
    paint: Paint,
    priority: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `track` | `HighlightTrack` | `required` |
| `paint` | `Paint` | `required` |
| `priority` | `int` | `0` |

## UNSET

Public constant:

```python
UNSET = StyleKeyword.UNSET
```

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

## compose_highlights

Resolve disjoint body regions; paints are ordered bottom to top.

union requires identical appearance at overlaps. priority picks the highest
priority and rejects conflicting ties. layer requires distinct priorities at
overlaps and retains every paint, including intentional duplicate opacity.
Before-singing paint is outside this operation and is drawn once per target.

[Source](../../kara_templater/composition.py#L125)

```python
compose_highlights(
    layers: tuple[TrackPaint, ...],
    time_ms: float,
    *,
    overlap: str,
) -> tuple[PaintedRegion, ...]
```

## resolve_paints

Precedence: line defaults, source spans, then explicit track override.

Equal-priority spans conflict only if they specify different values for the
same before/after state. Every range must preserve drawable clusters.

[Source](../../kara_templater/appearance.py#L59)

```python
resolve_paints(
    characters: tuple[DrawableCharacter, ...],
    *,
    default: PaintPair = PaintPair(before=Paint(fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, opacity=1, glow=None), after=Paint(fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, opacity=1, glow=None)),
    spans: tuple[ColorSpan, ...] = (),
) -> tuple[CharacterPaint, ...]
```

## resolve_ruby_paints

Inherit homogeneous associated body appearance, otherwise require a map.

Ruby is associated through its measured segment partition, never a second
text layout. Explicit overrides can assign one pair to each reading segment.

[Source](../../kara_templater/appearance.py#L112)

```python
resolve_ruby_paints(
    layout: LaidOutLine,
    characters: tuple[CharacterPaint, ...],
    *,
    overrides: tuple[RubyPaint, ...] = (),
) -> tuple[RubyPaint, ...]
```

## rule

Build a validated selector rule from typed style declarations.

Supported selectors identify roles, IDs, classes, attributes, and sung state.

[Source](../../kara_templater/stylesheet.py#L264)

```python
rule(
    selector: str,
    **properties: Unpack[StyleProperties],
) -> StyleRule
```
