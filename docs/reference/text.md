# Text measurement and layout

Font-dependent layout, source clusters, and editable body/ruby binding. Unicode code-point ranges must align with independently drawable clusters. See [text and cues](../guides/text-and-cues.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Box](#box)
- [CharacterTarget](#charactertarget)
- [DocumentLayout](#documentlayout)
- [DrawableCharacter](#drawablecharacter)
- [FontFace](#fontface)
- [KaraokeLine](#karaokeline)
- [LaidOutLine](#laidoutline)
- [LaidOutSegment](#laidoutsegment)
- [LaidOutUnit](#laidoutunit)
- [LayoutCapabilityError](#layoutcapabilityerror)
- [LoadedFont](#loadedfont)
- [LyricLayout](#lyriclayout)
- [PositionedRuby](#positionedruby)
- [PositionedText](#positionedtext)
- [Segment](#segment)
- [SingingSpan](#singingspan)
- [StudioSpacing](#studiospacing)
- [TextRange](#textrange)
- [TextUnit](#textunit)
- [VectorGuide](#vectorguide)
- [layout_characters](#layout_characters)
- [layout_document_lyrics](#layout_document_lyrics)
- [layout_document_text](#layout_document_text)
- [layout_line](#layout_line)
- [layout_lyrics](#layout_lyrics)
- [load_font](#load_font)
- [select_characters](#select_characters)
- [text_extents](#text_extents)

## Box

An axis-aligned layout rectangle in script pixels.

right, center, and middle are derived from left, top, width, and height.

[Source](../../kara_templater/model.py#L58)

```python
Box(
    left: float,
    top: float,
    width: float,
    height: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `left` | `float` | `required` |
| `top` | `float` | `required` |
| `width` | `float` | `required` |
| `height` | `float` | `required` |

### Box.center

The horizontal midpoint of the layout rectangle.

Type: `float`.

### Box.middle

The vertical midpoint of the layout rectangle.

Type: `float`.

### Box.right

The rectangle left coordinate plus its width, in script pixels.

Type: `float`.

## CharacterTarget

An independently drawable cluster supplied by layout, never a codepoint.

A layout backend must establish that the cluster can be drawn independently.
This model deliberately does not split text or claim shaping support.

[Source](../../kara_templater/characters.py#L13)

```python
CharacterTarget(
    id: str,
    unit_index: int,
    region: Region,
    center_y: float,
    drawable: bool = True,
    center_x: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `unit_index` | `int` | `required` |
| `region` | `Region` | `required` |
| `center_y` | `float` | `required` |
| `drawable` | `bool` | `True` |
| `center_x` | `float \| None` | `None` |

## DocumentLayout

Measured editable text objects with decoded source ranges, singing spans, bounds, and source-record identity.

Range backgrounds can optionally follow local text animation.

[Source](../../kara_templater/scene_text.py#L58)

```python
DocumentLayout(
    id: str,
    record_index: int | None,
    source: DocumentText,
    lifetime: Lifetime,
    characters: tuple[PositionedText, ...],
    singing: tuple[SingingSpan, ...],
    bounds: Box,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `record_index` | `int \| None` | `required` |
| `source` | `DocumentText` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `characters` | `tuple[PositionedText, ...]` | `required` |
| `singing` | `tuple[SingingSpan, ...]` | `required` |
| `bounds` | `Box` | `required` |

### DocumentLayout.background

Create a measured range background with padding and optional local animation following.

```python
DocumentLayout.background(
    start: int,
    end: int,
    *,
    id: str,
    color: Color,
    padding: Vec2 | None = None,
    layer: int = -1,
    follow: bool = False,
) -> PathObject
```

### DocumentLayout.group

Collect measured text objects into an editable group with the layout lifetime.

```python
DocumentLayout.group(
    *,
    position: Vec2 | None = None,
) -> ObjectGroup
```

### DocumentLayout.range_bounds

Bounds for an explicit word/range; reject splits within shaping clusters.

```python
DocumentLayout.range_bounds(
    start: int,
    end: int,
    *,
    time: float | None = None,
) -> Box
```

## DrawableCharacter

An independently drawable shaped cluster with unit-local source range, advance/ink bounds, timing region, and actual font faces.

A cluster can contain several Unicode code points.

[Source](../../kara_templater/characters.py#L76)

```python
DrawableCharacter(
    source: TextRange,
    text: str,
    box: Box,
    ink_bounds: Box | None,
    timing_region: Region,
    font_faces: tuple[FontFace, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `TextRange` | `required` |
| `text` | `str` | `required` |
| `box` | `Box` | `required` |
| `ink_bounds` | `Box \| None` | `required` |
| `timing_region` | `Region` | `required` |
| `font_faces` | `tuple[FontFace, ...]` | `()` |

### DrawableCharacter.id

The stable layout-local identity of this drawable source cluster.

Type: `str`.

### DrawableCharacter.target

Expose the character region, source unit, and center for highlight scheduling.

Type: `CharacterTarget`.

## FontFace

Face names and em-to-ASS-size ratio from FreeType. Names determine equality.

[Source](../../kara_templater/characters.py#L67)

```python
FontFace(
    family: str,
    style: str,
    em_ratio: float = 1.0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `family` | `str` | `required` |
| `style` | `str` | `required` |
| `em_ratio` | `float` | `1.0` |

## KaraokeLine

An ordered tuple of TextUnit values forming one lyric line.

It contains source content and timing, independently of its measured layout.

[Source](../../kara_templater/model.py#L48)

```python
KaraokeLine(
    units: tuple[TextUnit, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `units` | `tuple[TextUnit, ...]` | `required` |

## LaidOutLine

The measured line box and ordered laid-out units.

Each unit still references its original structured source.

[Source](../../kara_templater/model.py#L111)

```python
LaidOutLine(
    box: Box,
    units: tuple[LaidOutUnit, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `box` | `Box` | `required` |
| `units` | `tuple[LaidOutUnit, ...]` | `required` |

## LaidOutSegment

A singing segment with its measured horizontal interval and optional reading box.

Geometry belongs to layout; times belong to its source Segment.

[Source](../../kara_templater/model.py#L86)

```python
LaidOutSegment(
    source: Segment,
    left: float,
    right: float,
    ruby: Box | None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `Segment` | `required` |
| `left` | `float` | `required` |
| `right` | `float` | `required` |
| `ruby` | `Box \| None` | `required` |

## LaidOutUnit

A source TextUnit paired with a layout box and measured segments.

Unit geometry can contain multiple repeated singing intervals.

[Source](../../kara_templater/model.py#L99)

```python
LaidOutUnit(
    source: TextUnit,
    box: Box,
    segments: tuple[LaidOutSegment, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `TextUnit` | `required` |
| `box` | `Box` | `required` |
| `segments` | `tuple[LaidOutSegment, ...]` | `required` |

## LayoutCapabilityError

The available metrics cannot establish a safe independent drawing.

[Source](../../kara_templater/characters.py#L38)

Construction: `LayoutCapabilityError(*args)` using the inherited exception constructor.

## LoadedFont

The registered metrics font family and SHA-256 digest of the loaded bytes.

Registration does not configure a playback application or embed fonts into
output.

[Source](../../kara_templater/fonts.py#L14)

```python
LoadedFont(
    family: str,
    sha256: str,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `family` | `str` | `required` |
| `sha256` | `str` | `required` |

## LyricLayout

Measured body and positioned readings for projected DocumentLyrics.

unit_group builds editable body/ruby groups using the body center as pivot.

[Source](../../kara_templater/scene_lyrics.py#L92)

```python
LyricLayout(
    lyrics: DocumentLyrics,
    body: DocumentLayout,
    ruby: tuple[PositionedRuby, ...],
    bounds: Box,
    script_height: int = 1080,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `lyrics` | `DocumentLyrics` | `required` |
| `body` | `DocumentLayout` | `required` |
| `ruby` | `tuple[PositionedRuby, ...]` | `required` |
| `bounds` | `Box` | `required` |
| `script_height` | `int` | `1080` |

### LyricLayout.group

Combine measured body and positioned ruby objects into an editable group.

```python
LyricLayout.group(
    *,
    position: Vec2 | None = None,
) -> ObjectGroup
```

### LyricLayout.unit_group

Body and associated ruby around their shared body-center pivot.

```python
LyricLayout.unit_group(
    index: int,
) -> ObjectGroup
```

## PositionedRuby

A reading layout associated with a source unit/segment and decoded body range.

Its own text view retains source mappings and singing timing.

[Source](../../kara_templater/scene_lyrics.py#L78)

```python
PositionedRuby(
    unit_index: int,
    segment_index: int,
    body_start: int,
    body_end: int,
    layout: DocumentLayout,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `unit_index` | `int` | `required` |
| `segment_index` | `int` | `required` |
| `body_start` | `int` | `required` |
| `body_end` | `int` | `required` |
| `layout` | `DocumentLayout` | `required` |

## PositionedText

A drawable text cluster, decoded source range, measured advance/ink bounds, and selected font faces.

bounds is the allocated cell. The pen origin is object.state.position.
Layout scale is retained when used for range measurements. baseline is the
local y coordinate of the font baseline measured during shaping.

[Source](../../kara_templater/scene_text.py#L23)

```python
PositionedText(
    start: int,
    end: int,
    object: TextObject,
    bounds: Box,
    ink_bounds: Box | None,
    fonts: tuple[FontFace, ...],
    layout_scale: Vec2 | None = None,
    baseline: float | None = None,
    source_style: str | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `int` | `required` |
| `end` | `int` | `required` |
| `object` | `TextObject` | `required` |
| `bounds` | `Box` | `required` |
| `ink_bounds` | `Box \| None` | `required` |
| `fonts` | `tuple[FontFace, ...]` | `required` |
| `layout_scale` | `Vec2 \| None` | `None` |
| `baseline` | `float \| None` | `None` |
| `source_style` | `str \| None` | `None` |

### PositionedText.em_size

Local size of one em of the cluster's primary shaped face, in script pixels.

Type: `float`.

## Segment

A source singing interval in milliseconds with optional ruby text.

Zero duration is allowed as source data; positive visual animation lifetimes are
handled separately.

[Source](../../kara_templater/model.py#L6)

```python
Segment(
    start_ms: int,
    end_ms: int,
    ruby: str = '',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `int` | `required` |
| `end_ms` | `int` | `required` |
| `ruby` | `str` | `''` |

## SingingSpan

Source text offsets and original absolute singing times, including zero duration.

[Source](../../kara_templater/document_text.py#L358)

```python
SingingSpan(
    start_offset: int,
    end_offset: int,
    start: float,
    end: float,
    kind: Literal['k', 'K', 'kf', 'ko'],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_offset` | `int` | `required` |
| `end_offset` | `int` | `required` |
| `start` | `float` | `required` |
| `end` | `float` | `required` |
| `kind` | `Literal['k', 'K', 'kf', 'ko']` | `required` |

## StudioSpacing

Studio lyric cell metrics for the body and its readings.

space_width_percent sets an ASCII space's width as a percentage of the
selected font em (10 to 100). allow_biting includes negative side bearings
when measuring overhanging glyphs. Hard-outline clearance applies afterward.

[Source](../../kara_templater/scene_lyrics.py#L61)

```python
StudioSpacing(
    *,
    space_width_percent: int = 20,
    allow_biting: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `space_width_percent` | `int` | `20` |
| `allow_biting` | `bool` | `False` |

## TextRange

Half-open Python string offsets in an immutable source unit.

Offsets are source references, not drawable character indices. A range used
for painting must end on the verified cluster boundaries.

[Source](../../kara_templater/characters.py#L42)

```python
TextRange(
    unit_index: int,
    start: int,
    end: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `unit_index` | `int` | `required` |
| `start` | `int` | `required` |
| `end` | `int` | `required` |

## TextUnit

One body text unit with ordered, nonoverlapping singing segments.

Static units can have no segments and repeated singing retains a single body
string.

[Source](../../kara_templater/model.py#L27)

```python
TextUnit(
    text: str,
    segments: tuple[Segment, ...] = (),
    ruby_continuation: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `str` | `required` |
| `segments` | `tuple[Segment, ...]` | `()` |
| `ruby_continuation` | `bool` | `False` |

## VectorGuide

A timed lyric glyph with a baseline-relative path and horizontal advance in em units.

Positive y points down. One em follows the selected font at the marker.
Track.guide_symbols maps individual body characters to guide glyphs.

[Source](../../kara_templater/scene_lyrics.py#L21)

```python
VectorGuide(
    path: VectorPath,
    advance: float = 1,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `path` | `VectorPath` | `required` |
| `advance` | `float` | `1` |

## layout_characters

Measure verified clusters in the original unit layout, without relayout.

Ink bounds are conservative outline control-point bounds (no blur/stroke),
not exact raster extents. TextRange identities are independent of timing and
appearance. Empty-outline spaces retain advance but are not pulse targets.

[Source](../../kara_templater/characters.py#L220)

```python
layout_characters(
    layout: LaidOutLine,
    *,
    style: Style,
) -> tuple[DrawableCharacter, ...]
```

## layout_document_lyrics

Bind body/ruby without changing original singing or decoded source ranges.

Body text is shaped together before ruby spacing is applied. Unit boundaries
crossing a shaping cluster are rejected when independent placement is needed.
vertical stacks cells downward around x=0, with readings on the right.
Joined ruby runs share a row; explicit break/spill markers start a new group.

[Source](../../kara_templater/scene_lyrics.py#L416)

```python
layout_document_lyrics(
    document: Document,
    record_index: int,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
    ruby_gap: float = 6,
    studio_spacing: bool | StudioSpacing = False,
    guide_symbols: Mapping[str, VectorGuide] | None = None,
    right_to_left: bool = False,
    vertical: bool = False,
    min_outline_gap: float | None = None,
    reserved_border: float = 0,
) -> LyricLayout
```

## layout_document_text

Bind a plain line; use layout_document_lyrics for ruby/continuations.

[Source](../../kara_templater/scene_text.py#L420)

```python
layout_document_text(
    document: Document,
    record_index: int,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
) -> DocumentLayout
```

## layout_line

Measure a structured KaraokeLine with body and reading styles at the requested resolution.

Return layout boxes without changing source singing intervals.

[Source](../../kara_templater/layout.py#L65)

```python
layout_line(
    source: KaraokeLine,
    *,
    style: Style,
    ruby_style: Style | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> LaidOutLine
```

## layout_lyrics

Measure structured or parsed lyrics using Document styles and resolution.

studio_spacing measures character cells from ink width, bearings and the primary
outline before applying minimum outline clearance. The default uses shaped advances.
ruby_gap sets the vertical clearance between the hard ink bounds of a
reading group and its body before animation. Negative values allow overlap.
vertical stacks glyphs in measured font cells. ruby_gap then separates the body
and reading cells horizontally, in script pixels.
No ASS event is required or synthesized. Singing intervals retain their full
seconds precision; record indices, if present, are provenance only.

[Source](../../kara_templater/scene_lyrics.py#L456)

```python
layout_lyrics(
    document: Document,
    lyrics: DocumentLyrics,
    *,
    id: str,
    display: Lifetime,
    ruby_gap: float = 6,
    studio_spacing: bool | StudioSpacing = False,
    guide_symbols: Mapping[str, VectorGuide] | None = None,
    right_to_left: bool = False,
    vertical: bool = False,
    min_outline_gap: float | None = None,
    reserved_border: float = 0,
) -> LyricLayout
```

## load_font

Make an extra font file available to this interpreter's metrics renderer.

Each style still selects its font by family name via ``Style.fontname``.
This does not set a global font or bind a style to a specific font file.
Registration persists for this interpreter. Duplicate bytes are loaded once.
ASS playback/rendering must be configured with the same font separately.

[Source](../../kara_templater/fonts.py#L29)

```python
load_font(
    path: str | pathlib.Path,
) -> LoadedFont
```

## select_characters

Select complete drawable clusters covered by a TextRange.

Reject boundaries that cut a cluster instead of silently expanding or reshaping
the selection.

[Source](../../kara_templater/characters.py#L326)

```python
select_characters(
    characters: tuple[DrawableCharacter, ...],
    source: TextRange,
) -> tuple[DrawableCharacter, ...]
```

## text_extents

Measure text using the native font/shaping environment and ASS style metrics.

Return width, height, descent, and external leading in script pixels.

[Source](../../kara_templater/layout.py#L47)

```python
text_extents(
    style: Style,
    text: str,
) -> tuple[float, float, float, float]
```
