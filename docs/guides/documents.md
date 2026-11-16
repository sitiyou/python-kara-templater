# Documents and lyrics

A Document is the shared input and output model. Use `Document.load(path)` for
files, `Document.parse(text)` for ASS strings, or `Document.create(...)` for a
new script. `save(path)` writes ASS; `dumps()` returns the serialized text.
Ordinary loading never executes template code.

## Records and source ownership

`document.records` preserves ordered Script Info, styles, events, unknown
sections, and unrecognized event fields. Line times use milliseconds. Styles
are indexed by `document.styles`; `document.lines` returns event records.
Use `record_index` for a position in records, not a physical text-file line number.
Keep the Document's PlayRes and output settings consistent.

A Scene retains its Document and adds visual objects. Call
`scene.replace_source(record_index)` when generated content replaces that event;
the original becomes a retained Comment. Scene compilation returns a new Document.
Keep a stable `owner` to replace that owner's output on regeneration. Other
owners and unselected records remain available. Generated ownership markers are
reserved for the library; editing those markers can invalidate regeneration.

Track preparation imports timed lyrics automatically, retains their source
records, and restores sources when selection changes. Explicit `LyricSource`
values created from DocumentLyrics leave existing dialogue untouched. Track.source
is a predicate over LyricSource metadata. Multiple Tracks may show the same
source; visual view identity is separate from record replacement ownership.

## Choose the lyric frontend

| Input task | Interface | Timing and scope |
| --- | --- | --- |
| Plain text with static colors/style resets and optional cues | `read_document_text`, `layout_document_text` | Decoded text ranges and SingingSpan clocks |
| Body text, ruby, and repeated singing | `layout_document_lyrics` | Body/ruby source projection and grouped lyric units |
| Declarative lyric styling and animations | `prepare_tracks`, `LyricSource.from_lyrics` | DocumentLyrics and semantic targets; times in seconds |
| Existing Python ASS templates | `Engine`, `apply_templates` | Explicit template execution; separate helper context |

These frontends enforce their supported input subsets. Parsing does not evaluate
arbitrary ASS animation overrides. Track uses the Document lyric projection,
including static inline color/reset scopes and cue markers. See
[text and cues](text-and-cues.md) for their authoring workflow.

`TextObject.text` is literal Unicode. Braces and backslashes are displayed as
characters, including strings that look like ASS overrides; use `NativeEvent`
for already encoded ASS. A newline becomes a hard line break. CR and NUL are
rejected. Compilation escapes braces and protects literal backslashes with an
invisible word joiner. The Document text projection decodes these sequences
while retaining their original raw tokens and decoded character offsets.

Karaoke timing recognizes `\k`, `\K`, `\kf`, `\ko`, and explicit `\kt`
offsets. The body/ruby convention uses `body|reading`; a `#` or `＃` continuation
adds a singing segment to the previous body unit. Empty chunks and static text
consume or retain their original positions in the source model. Display entry
and exit are separate from the original singing intervals.

Zero-length singing segments remain source data. Skip their animation or choose
an explicit positive display duration when creating an AnimationClip. Backward
singing-time jumps and unsupported input produce contextual errors.

## Ranges and origin information

Document ranges count decoded Unicode code points. Semantic targets identify
measured syllables, segments and glyph clusters. A range cannot split an
indivisible shaped cluster. A visual character can
contain multiple code points, and spaces can have advance without ink.

`SourceRef` identifies an item and optional unit/segment. It remains stable when
presentation or item order changes; editing the source structure changes what
its indices refer to. `EventOrigin` records source dependencies and highlight
track IDs. `SceneResult.event_origins` pairs generated Dialogue objects with
optional origins; these are the actual records in the output Document.

For loading failures, inspect AssImportError.record_index, style, origin, and
its exception cause. Document binding errors report the source record and text
range. See [troubleshooting](troubleshooting.md).
