# Import timed lyrics

Load timed ASS scripts or build lyrics directly in Python before laying out vocal tracks. Learn which karaoke timing tags and ruby notations are supported, how lines are selected, and how to read source positions in error messages.

## Load or create a Document

A `Document` holds script resolution (`PlayRes`), named styles, and ordered ASS records. Load an existing timed ASS file with `Document.load(path)`, parse an ASS string with `Document.parse(text)`, or build a script in Python with `Document.create(...)`.

```python
from kara_templater import (
    Document,
    KaraokeEffects,
    Track,
    build_lyric_scene,
)

ass_text = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,54,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\k50}Ka|ka{\\k50}ra|ra{\\k50}o|o{\\k50}ke|ke
"""

document = Document.parse(ass_text)
scene = build_lyric_scene(
    document,
    tracks=(Track(id="main", effects=(KaraokeEffects(),)),),
)
scene.export("output.hook")
```

To read from a file on disk, replace `Document.parse(ass_text)` with `Document.load("song.ass")`. Call `document.save(path)` to write standard ASS (UTF-8 with BOM) or `document.dumps()` to get the serialized string.

Inside a `Document`:

- `document.records` stores Script Info lines, `Style` objects, `Line` events, and unknown sections in their original order. A `record_index` is an index into `document.records`, not a physical line number in the text file.
- `document.styles` maps style names to `Style` objects.
- `document.lines` returns all `Line` events (both Dialogue and Comment) in source order.

> [!NOTE]
> `Line.start_time` and `Line.end_time` use **milliseconds** to match ASS records. Everything in `Track`, `Scene`, and lyric timing spans uses **seconds**.

If you already have structured lyrics in Python, you do not need to synthesize ASS dialogue lines. Pass `LyricSource.from_lyrics(...)` entries to `Document.create(..., lyric_sources=..., bpm=...)` or to `build_lyric_scene(..., inputs=...)`. `build_lyric_scene` reads those sources and uses `bpm` for automatic cue timing, while `save()` and `dumps()` only serialize the ASS records.

## Karaoke timing tags

Imported lyrics recognize `\k`, `\K`, `\kf`, and `\ko` interchangeably. Each tag advances the timing cursor by centiseconds from the event's `start_time`.

- **Rests**: An empty timed chunk advances the clock without adding text. In `{\k30}{\kf20}春|>はる`, the syllable starts 300 ms into the line and lasts 200 ms.
- **Ignored `\kt`**: The lyrics clock ignores `\kt`. Use an empty `\k` tag for a rest instead.
- **Zero-length intervals**: Tags such as `{\k0}` stay in the source data. Skip animating them, or give an `AnimationClip` an explicit positive duration.
- **Skipped events**: When tracks import an ASS file, untimed dialogue lines, comments, and `\p1` vector drawing spans are skipped automatically. Display entry and exit times come from your track template.

## Ruby and repeated-timing syntax

Write inline readings (furigana) inside any timed chunk with a vertical bar (`|` or fullwidth `｜`). Both `body|reading` and `body|>reading` produce the same base text and reading.

To split one body unit across multiple timed segments—for example, a kanji sung over two kana with a rest in between—follow it with `#` (or fullwidth `＃`) in the next timed chunk:

```text
{\k40}影|か{\k20}{\k40}#|げ
```

Here `影` sweeps halfway during `か`, holds its highlight across the 200 ms rest, and finishes sweeping during `げ`, while each reading keeps its own timing clock. In code-built `DocumentLyrics`, set `LyricUnit(..., repeat=True)` if you want each segment to sweep the full body from scratch instead of continuing.

In code-authored documents created with `Document.create(...)`, two extra prefixes control horizontal ruby grouping:

- `|!` starts a separate reading group instead of joining adjacent annotated syllables.
- `|<` lets a wide reading overflow equally to the left and right.

Fullwidth `！` and `＜` work the same way. In imported ASS files (`Document.load` or `Document.parse`), `|!`, `|<`, and `|>` are all read as ordinary ruby separators. See [Ruby readings and cues](text-and-cues.md) for spacing and grouping rules.

## Imported ASS vs. code-authored documents

`Document.load` and `Document.parse` treat the file as timed lyric input whose appearance belongs to your template. `Document.create` treats the script as code-authored, keeping its own styles and inline color tags.

| Behavior | Imported ASS (`load` / `parse`) | Code-authored (`create`) |
| --- | --- | --- |
| Text, `\k` timing, ruby, cue markers | Read | Read |
| Inline color (`\c`, `\1c`–`\4c`) and `\r` resets | Ignored (template supplies appearance) | Preserved as appearance runs |
| Styles used for layout | `Default` and `Default-furigana` (override via `Track.styles`) | Document's own named styles |
| `source.style`, `source.actor`, `source.effect` | Preserved for `Track(source=...)` selection | Preserved for `Track(source=...)` selection |
| `\|!` and `\|<` ruby prefixes | Treated as ordinary `\|` separators | Control ruby group breaks and overflow |
| `\p1` drawing spans | Skipped | Rejected as unsupported overrides when binding text |

Most templates read lyrics through `build_lyric_scene`. Lower-level helpers are available when you want direct access to decoded text or measured characters:

| Task | Function or method | What it returns |
| --- | --- | --- |
| Style and animate timed vocal tracks | `build_lyric_scene` | A `LyricScene` with laid-out lines and cues (times in seconds) |
| Measure body text, ruby, and `#` repeats on one line | `layout_document_lyrics`, `document.lyrics_at(record_index)` | Measured `LyricLayout` or decoded `DocumentLyrics` |
| Read plain text, static inline colors, and cues on one line | `layout_document_text`, `document.text_at(record_index)`, `read_document_text` | Measured `TextLayout` or decoded `DocumentText` |

When creating standalone text nodes directly with `TextObject`, its `text` field is literal Unicode: braces and backslashes display as characters rather than ASS override tags, newlines become hard line breaks, and CR (`\r`) and NUL (`\0`) are rejected. Use `AssDialogue` only when you need to pass pre-encoded ASS dialogue straight through.

## Select lines and preserve source records

Use `Track(source=...)` to pick which lines belong to a vocal stream. The predicate receives a `LyricSource` with `style`, `actor`, `effect`, `text`, and `display`:

```python
from kara_templater import Track

lead = Track(id="lead", source=lambda s: s.style == "Lead")
harmony = Track(id="harmony", source=lambda s: s.actor == "harmony")
```

Multiple tracks can select the same source line without interfering with each other; each track gets its own visual objects. Lines not matched by any track stay untouched.

When you export standard ASS or build a scene manually, `build_lyric_scene(..., owner="karaoke")` and `scene.replace_source(record_index)` keep each original dialogue line as a marked Comment record. Keeping the same `owner` name lets future runs replace only that owner's generated lines and restore any source lines you deselected. Do not hand-edit the library's ownership markers in generated ASS files, or regeneration may fail to match previous output.

> [!TIP]
> Keep your `Document`'s `PlayResX` and `PlayResY` consistent with your target aspect ratio. Sizes, outlines, margins, and positions are all measured in script pixels.

## Source ranges and error diagnostics

Character ranges in `DocumentText` and `DocumentLyrics` count decoded Unicode code points, not UTF-8 bytes or shaped glyphs. A single visible character can contain multiple code points (such as a base letter plus a combining mark), and spaces keep advance width without visible ink. A range used for layout or painting cannot split a shaped cluster in half.

When input fails to load or bind, check the exception details:

- **Malformed ASS files**: `Document.load` and `Document.parse` raise `ValueError` for invalid ASS syntax (such as SSA v4 styles, missing `Format:` lines, or invalid timestamps) and `OSError` when a file cannot be read.
- **Invalid text, timing, or cue markup**: `read_document_text`, `parse_document_lyrics`, `document.text_at`, and `document.lyrics_at` raise `ValueError` with the `record_index` and raw character offset in the message (or `TypeError` if `record_index` does not point to a `Line`). Unsupported ASS overrides are recorded in `DocumentText.unsupported` as `TextIssue(record_index, raw_offset, raw, reason)`.
- **Shaping or cluster-split errors**: `layout_document_text` and `layout_document_lyrics` raise `LayoutCapabilityError` when a script cannot be split into independent glyphs or a boundary cuts across a shaped cluster.

For tracing generated events back to input lyrics, `SourceRef(source_id, unit_index, segment_index)` identifies a line and optional unit or segment stably across layout changes (though editing the source structure changes what indices point to). `EventOrigin` attaches those references and track IDs to generated objects; on ASS export, `AssResult.event_origins` pairs each output dialogue line with its `EventOrigin`. See [Troubleshooting](../output/troubleshooting.md) for common fixes.

## Next steps

- [Lay out vocal tracks](tracks.md)
- [Ruby readings and cues](text-and-cues.md)
- [Choose and register fonts](fonts.md)
- [Documents API reference](../reference/documents.md)
