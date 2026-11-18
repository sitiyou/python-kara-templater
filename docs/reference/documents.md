# Documents and lyric input

Records, decoded text, input selection, and source mappings. Raw Line clocks use milliseconds; Document lyric singing spans and Track authoring use seconds. See [Documents](../guides/documents.md).

[All public symbols](README.md#symbol-index)

## Contents

- [AssImportError](#assimporterror)
- [CueMarker](#cuemarker)
- [Document](#document)
- [DocumentLyrics](#documentlyrics)
- [DocumentText](#documenttext)
- [EventOrigin](#eventorigin)
- [ImportSettings](#importsettings)
- [ImportedKaraoke](#importedkaraoke)
- [Line](#line)
- [LyricMapping](#lyricmapping)
- [LyricSegment](#lyricsegment)
- [LyricUnit](#lyricunit)
- [Record](#record)
- [RubyText](#rubytext)
- [SingingTag](#singingtag)
- [SourceRef](#sourceref)
- [Style](#style)
- [TextAppearance](#textappearance)
- [TextIssue](#textissue)
- [TextRun](#textrun)
- [TextToken](#texttoken)
- [import_karaoke](#import_karaoke)
- [paint_pair_from_style](#paint_pair_from_style)
- [parse_document_lyrics](#parse_document_lyrics)
- [parse_karaoke](#parse_karaoke)
- [read_document_text](#read_document_text)
- [walk_karaoke](#walk_karaoke)

## AssImportError

Failure at a zero-based Document.records position, before a lyric exists.

[Source](../../kara_templater/import_ass.py#L21)

```python
AssImportError(
    message: str,
    *,
    record_index: int,
    style: str,
    item_id: str | None = None,
)
```

## CueMarker

A non-executable cue anchor with ID, preset key, decoded body offset, and inline/independent placement.

markup quotes the declaration; its insertion point carries the serialized
offset.

[Source](../../kara_templater/document_text.py#L73)

```python
CueMarker(
    id: str,
    preset: str,
    offset: int = 0,
    placement: Literal['inline', 'independent'] = 'inline',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `preset` | `str` | `required` |
| `offset` | `int` | `0` |
| `placement` | `Literal['inline', 'independent']` | `'inline'` |

### CueMarker.markup

Encode a non-executable comment block at the desired text position.

```python
CueMarker.markup() -> str
```

## Document

An ordered ASS record collection with parsed script metadata.

Load/parse preserve source content without executing code; create builds a new
script, and save/dumps serialize standard ASS.

[Source](../../kara_templater/ass.py#L232)

```python
Document(
    records: list[str | Style | Line],
    meta: Record,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `records` | `list[str \| Style \| Line]` | `required` |
| `meta` | `Record` | `required` |

### Document.create

Create standard ASS with raw RGB colors for code-authored scenes.

YCbCr Matrix: None prevents playback color-matrix reinterpretation of
authored RGB values. Parsing existing ASS retains its original metadata.

```python
Document.create(
    *,
    width: int = 1280,
    height: int = 720,
    styles: tuple[Style, ...] = (),
) -> Document
```

### Document.dumps

Serialize the current records and preserved fields as standard ASS text.

```python
Document.dumps() -> str
```

### Document.lines

Return Dialogue and Comment records in source order.

Type: `list[Line]`.

### Document.load

Read an ASS file and parse its records, preserving source fields and unknown sections.

```python
Document.load(
    path: str | pathlib.Path,
) -> Document
```

### Document.lyrics_at

Read scoped body/ruby and timing without layout or template execution.

```python
Document.lyrics_at(
    record_index: int,
) -> DocumentLyrics
```

### Document.parse

Parse ASS text into ordered records and script metadata without executing templates.

```python
Document.parse(
    text: str,
) -> Document
```

### Document.save

Serialize ASS to the requested file using UTF-8 with a byte-order mark.

```python
Document.save(
    path: str | pathlib.Path,
) -> None
```

### Document.styles

Return the current style-name mapping from ordered Style records.

Type: `dict[str, Style]`.

### Document.text_at

Read typed text semantics without executing templates or changing records.

```python
Document.text_at(
    record_index: int,
) -> DocumentText
```

## DocumentLyrics

A decoded body/ruby projection with source mappings and ordered lyric units.

Original DocumentText remains available for diagnostics and round trips.

[Source](../../kara_templater/document_lyrics.py#L88)

```python
DocumentLyrics(
    source: DocumentText,
    body: DocumentText,
    mapping: tuple[LyricMapping, ...],
    units: tuple[LyricUnit, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `DocumentText` | `required` |
| `body` | `DocumentText` | `required` |
| `mapping` | `tuple[LyricMapping, ...]` | `required` |
| `units` | `tuple[LyricUnit, ...]` | `required` |

## DocumentText

A source-preserving decoded ASS text view with tokens, appearance runs, karaoke tags, cues, and issues.

Offsets count Unicode code points rather than bytes or shaped glyphs.

[Source](../../kara_templater/document_text.py#L118)

```python
DocumentText(
    record_index: int | None,
    tokens: tuple[TextToken, ...],
    runs: tuple[TextRun, ...],
    timing: tuple[SingingTag, ...],
    cues: tuple[CueMarker, ...],
    unsupported: tuple[TextIssue, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `record_index` | `int \| None` | `required` |
| `tokens` | `tuple[TextToken, ...]` | `required` |
| `runs` | `tuple[TextRun, ...]` | `required` |
| `timing` | `tuple[SingingTag, ...]` | `required` |
| `cues` | `tuple[CueMarker, ...]` | `required` |
| `unsupported` | `tuple[TextIssue, ...]` | `required` |

### DocumentText.original

Reconstruct the original source Text from its preserved raw tokens.

```python
DocumentText.original() -> str
```

### DocumentText.require_supported

Raise a contextual error when the text contains unsupported semantics for a binder.

```python
DocumentText.require_supported() -> None
```

### DocumentText.text

Concatenate decoded text runs without override/comment markup.

Type: `str`.

## EventOrigin

Source dependencies, not a claim that one segment owns an event's time.

A body glyph can depend on every segment in its unit. Explicit tracks are
independent of source segments; their IDs are recorded separately.

[Source](../../kara_templater/sources.py#L58)

```python
EventOrigin(
    sources: tuple[SourceRef, ...],
    effect: str,
    track_ids: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `sources` | `tuple[SourceRef, ...]` | `required` |
| `effect` | `str` | `required` |
| `track_ids` | `tuple[str, ...]` | `()` |

## ImportSettings

Track ASS-import display padding and optional style selection.

lead_ms/tail_ms extend visibility independently of the original singing
intervals.

[Source](../../kara_templater/import_ass.py#L37)

```python
ImportSettings(
    lead_ms: int = 0,
    tail_ms: int = 0,
    styles: tuple[str, ...] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `lead_ms` | `int` | `0` |
| `tail_ms` | `int` | `0` |
| `styles` | `tuple[str, ...] \| None` | `None` |

## ImportedKaraoke

Structured lyric items plus source-record bindings for owner-aware regeneration.

Importing does not itself replace or execute source events.

[Source](../../kara_templater/import_ass.py#L61)

```python
ImportedKaraoke(
    items: tuple[KaraokeItem, ...],
    sources: tuple[SourceBinding, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `items` | `tuple[KaraokeItem, ...]` | `required` |
| `sources` | `tuple[SourceBinding, ...]` | `required` |

## Line

An ASS Dialogue or Comment event with millisecond start/end times and preserved extra fields.

Actor, effect, margins, layer, and source style remain distinct event
attributes.

[Source](../../kara_templater/ass.py#L154)

```python
Line(
    text: str = '',
    start_time: float = 0,
    end_time: float = 0,
    style: str = 'Default',
    actor: str = '',
    layer: int = 0,
    margin_l: int = 0,
    margin_r: int = 0,
    margin_v: int = 0,
    effect: str = '',
    comment: bool = False,
    fields: dict[str, str] = _HAS_DEFAULT_FACTORY_CLASS(),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `str` | `''` |
| `start_time` | `float` | `0` |
| `end_time` | `float` | `0` |
| `style` | `str` | `'Default'` |
| `actor` | `str` | `''` |
| `layer` | `int` | `0` |
| `margin_l` | `int` | `0` |
| `margin_r` | `int` | `0` |
| `margin_v` | `int` | `0` |
| `effect` | `str` | `''` |
| `comment` | `bool` | `False` |
| `fields` | `dict[str, str]` | `dict()` |

### Line.margin_b

Template-facing bottom-margin alias using the event vertical margin.

Type: `int`.

### Line.margin_t

Template-facing top-margin alias using the event vertical margin.

Type: `int`.

### Line.serialize

Serialize this Dialogue or Comment in its preserved event field order.

```python
Line.serialize() -> str
```

## LyricMapping

One unchanged text slice from the original decoded text into a component.

[Source](../../kara_templater/document_lyrics.py#L10)

```python
LyricMapping(
    source_start: int,
    source_end: int,
    start: int,
    end: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source_start` | `int` | `required` |
| `source_end` | `int` | `required` |
| `start` | `int` | `required` |
| `end` | `int` | `required` |

## LyricSegment

One absolute-seconds singing interval and its optional RubyText, retaining source text bounds.

Repeated singing adds segments without duplicating the body.

[Source](../../kara_templater/document_lyrics.py#L32)

```python
LyricSegment(
    singing: SingingSpan,
    source_start: int,
    source_end: int,
    ruby: RubyText | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `singing` | `SingingSpan` | `required` |
| `source_start` | `int` | `required` |
| `source_end` | `int` | `required` |
| `ruby` | `RubyText \| None` | `None` |

## LyricUnit

A decoded body range and its ordered singing segments.

Ranges count Unicode code points and must later respect shaped cluster
boundaries.

[Source](../../kara_templater/document_lyrics.py#L45)

```python
LyricUnit(
    start: int,
    end: int,
    segments: tuple[LyricSegment, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `int` | `required` |
| `end` | `int` | `required` |
| `segments` | `tuple[LyricSegment, ...]` | `()` |

## Record

An attribute-backed record used by script metadata and template contexts.

Document metadata exposes script resolution and the template aspect-correction
factor.

[Source](../../kara_templater/ass.py#L13)

Supports standard dict construction and attribute access to stored keys.

Example: `Record(res_x=1280, res_y=720)`.

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `res_x` | `int` | `instance attribute` |
| `res_y` | `int` | `instance attribute` |
| `video_x_correct_factor` | `float` | `instance attribute` |

## RubyText

A reading text view with mappings back to source text and join/break/spill mode.

Its source indices are local to the reading view.

[Source](../../kara_templater/document_lyrics.py#L20)

```python
RubyText(
    source: DocumentText,
    mapping: tuple[LyricMapping, ...],
    mode: Literal['join', 'break', 'spill'] = 'join',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source` | `DocumentText` | `required` |
| `mapping` | `tuple[LyricMapping, ...]` | `required` |
| `mode` | `Literal['join', 'break', 'spill']` | `'join'` |

## SingingTag

A decoded karaoke timing tag at a text offset.

Its seconds value is a duration for k/K/kf/ko and an absolute cursor offset for
kt.

[Source](../../kara_templater/document_text.py#L60)

```python
SingingTag(
    offset: int,
    kind: Literal['k', 'K', 'kf', 'ko', 'kt'],
    seconds: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `int` | `required` |
| `kind` | `Literal['k', 'K', 'kf', 'ko', 'kt']` | `required` |
| `seconds` | `float` | `required` |

## SourceRef

Address within an item, stable while its source structure is unchanged.

Item order, layout and effects do not affect addresses. Editing/reordering
units or segments creates a new source structure; indices are not edit IDs.

[Source](../../kara_templater/sources.py#L81)

```python
SourceRef(
    item_id: str,
    unit_index: int | None = None,
    segment_index: int | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `item_id` | `str` | `required` |
| `unit_index` | `int \| None` | `None` |
| `segment_index` | `int \| None` | `None` |

### SourceRef.resolve

Return the original source object; never a layout or generated copy.

```python
SourceRef.resolve(
    item: KaraokeItem,
) -> KaraokeLine | TextUnit | Segment
```

## Style

An ASS style with typed font/layout fields and preserved raw style columns.

Font scales are percentages, alignment uses ASS 1 through 9, and sizes/margins
use script pixels.

[Source](../../kara_templater/ass.py#L75)

```python
Style(
    name: str = 'Default',
    fontname: str = 'Arial',
    fontsize: float = 20,
    bold: bool = False,
    italic: bool = False,
    scale_x: float = 100,
    scale_y: float = 100,
    spacing: float = 0,
    encoding: int = 1,
    align: int = 2,
    margin_l: int = 10,
    margin_r: int = 10,
    margin_v: int = 10,
    outline: float = 2,
    shadow: float = 2,
    fields: dict[str, str] = _HAS_DEFAULT_FACTORY_CLASS(),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `name` | `str` | `'Default'` |
| `fontname` | `str` | `'Arial'` |
| `fontsize` | `float` | `20` |
| `bold` | `bool` | `False` |
| `italic` | `bool` | `False` |
| `scale_x` | `float` | `100` |
| `scale_y` | `float` | `100` |
| `spacing` | `float` | `0` |
| `encoding` | `int` | `1` |
| `align` | `int` | `2` |
| `margin_l` | `int` | `10` |
| `margin_r` | `int` | `10` |
| `margin_v` | `int` | `10` |
| `outline` | `float` | `2` |
| `shadow` | `float` | `2` |
| `fields` | `dict[str, str]` | `dict()` |

### Style.margin_b

Template-facing bottom-margin alias using the style vertical margin.

Type: `int`.

### Style.margin_t

Template-facing top-margin alias using the style vertical margin.

Type: `int`.

### Style.serialize

Serialize this ASS style while preserving extra fields and updating typed values.

```python
Style.serialize() -> str
```

## TextAppearance

The active style and resolved RGB channel colors for a text run.

inline_colors records channels explicitly supplied by override tags.

[Source](../../kara_templater/document_text.py#L32)

```python
TextAppearance(
    style: str,
    primary: Color,
    secondary: Color,
    outline: Color,
    shadow: Color,
    inline_colors: frozenset[str] = frozenset({}),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `style` | `str` | `required` |
| `primary` | `Color` | `required` |
| `secondary` | `Color` | `required` |
| `outline` | `Color` | `required` |
| `shadow` | `Color` | `required` |
| `inline_colors` | `frozenset[str]` | `frozenset({})` |

## TextIssue

A source offset and diagnostic message for text semantics a binder may reject.

Parsing retains the original tokens for unsupported overrides.

[Source](../../kara_templater/document_text.py#L105)

```python
TextIssue(
    record_index: int | None,
    raw_offset: int,
    raw: str,
    reason: str,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `record_index` | `int \| None` | `required` |
| `raw_offset` | `int` | `required` |
| `raw` | `str` | `required` |
| `reason` | `str` | `required` |

## TextRun

A half-open decoded text range with its resolved appearance.

It preserves color/reset scopes independently of later glyph shaping.

[Source](../../kara_templater/document_text.py#L47)

```python
TextRun(
    text: str,
    start: int,
    end: int,
    appearance: TextAppearance,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `text` | `str` | `required` |
| `start` | `int` | `required` |
| `end` | `int` | `required` |
| `appearance` | `TextAppearance` | `required` |

## TextToken

An original literal or override token with its source Text-string offset.

Raw text is retained even if a particular effect cannot interpret it.

[Source](../../kara_templater/document_text.py#L20)

```python
TextToken(
    raw: str,
    offset: int,
    override: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `raw` | `str` | `required` |
| `offset` | `int` | `required` |
| `override` | `bool` | `False` |

## import_karaoke

Import supported timed ASS lyrics into KaraokeItem values with stable source bindings.

Preserve source timing and report unsupported tags with record/style context.

[Source](../../kara_templater/import_ass.py#L175)

```python
import_karaoke(
    document: Document,
    *,
    owner: str = 'default',
    settings: ImportSettings | None = None,
) -> ImportedKaraoke
```

## paint_pair_from_style

ASS secondary is unsung, primary is sung; decode AABBGGRR at this boundary.

[Source](../../kara_templater/import_ass.py#L255)

```python
paint_pair_from_style(
    style: Style,
) -> PaintPair
```

## parse_document_lyrics

Project text|ruby and # continuations; all singing times remain absolute.

Syntax is recognized within each explicit karaoke interval. Untimed text is
preserved, but ruby/continuation syntax requires a karaoke time tag. Body
and ruby views retain the original tokens for provenance, not serialization.

[Source](../../kara_templater/document_lyrics.py#L116)

```python
parse_document_lyrics(
    source: DocumentText,
    *,
    start: float,
) -> DocumentLyrics
```

## parse_karaoke

Read k/kf/K/ko durations, kt offsets, text|ruby, and # continuations.

These tags import timing only; appearance and animation come from the recipe.
Unsupported override tags are diagnosed instead of silently losing layout.

[Source](../../kara_templater/import_ass.py#L85)

```python
parse_karaoke(
    line: Line,
) -> KaraokeLine
```

## read_document_text

Bind one event's text while preserving every original byte of its text.

Standard inline colors override the current style. An empty color tag resets
that channel to the current style; r resets all channels to the named style
or the event style. Unhandled tags are retained and explicitly diagnosed.
Cue presets are resolved later by the effect registry, never executed here.

[Source](../../kara_templater/document_text.py#L229)

```python
read_document_text(
    document: Document,
    record_index: int,
) -> DocumentText
```

## walk_karaoke

Visit sources in input order, including empty and zero-duration sources.

Static units appear at unit level and have no segment visits. Times never
sort or filter the source; simultaneous lines and repeated readings retain
distinct addresses. IDs are validated before any visits are yielded.

[Source](../../kara_templater/sources.py#L141)

```python
walk_karaoke(
    items: Iterable[KaraokeItem],
    *,
    level: Literal['line'],
) -> Iterator[tuple[SourceRef, KaraokeLine]]
```

```python
walk_karaoke(
    items: Iterable[KaraokeItem],
    *,
    level: Literal['unit'],
) -> Iterator[tuple[SourceRef, TextUnit]]
```

```python
walk_karaoke(
    items: Iterable[KaraokeItem],
    *,
    level: Literal['segment'] = 'segment',
) -> Iterator[tuple[SourceRef, Segment]]
```
