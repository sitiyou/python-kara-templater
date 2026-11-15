# Text, ruby, and lyric cues

TextObject draws one string; layout_document_text and layout_document_lyrics
bind Document text into measured, independently editable objects. Use the lyric
binder for body/ruby projection and repeated singing intervals. These interfaces
retain source ranges and timing separately from visual objects.

## Bind text and readings

Find the desired Line's index in Document.records, then call the appropriate
layout function with the Document and that record index. A LyricLayout exposes
body, positioned ruby, singing units, and unit_group(index). A unit group combines
its body and readings around the body's center, so a shared pulse moves them
together. Multiline or bilingual content can be composed by binding separate
source records and adding the groups to one Scene.

DocumentLayout.characters associates each object with its decoded source range,
layout box, conservative ink bounds, and actual font faces. range_bounds and
background measure author-selected ranges without implicit word segmentation.
`background(..., follow=True)` follows the local animated text range and its
breakpoints; put it in the same parent group to inherit group transforms. Use a
world-space reference when following across parent groups.

Shaping can combine several code points into one cluster. Color boundaries, cue
anchors, and outline extraction must respect independent drawing boundaries.
Missing glyphs and unsupported splitting produce errors with source context.
Static color and style-reset scopes are preserved by the Document binder; the
current binders do not evaluate every possible ASS override.

Independent layout considers Latin, Greek, Cyrillic, CJK, kana, modern Hangul,
digits, punctuation, and guide dots, with combining marks kept with their base.
Actual outlines still determine whether a candidate can be drawn independently.
Joining scripts, bidi controls, emoji sequences, and archaic jamo are outside
this independent-character backend. Whole TextObject rendering and independently
editable glyph layout have different requirements.

## Define and place cues

CuePreset chooses a factory, lead, duration, steps, gap, position, and whether to
keep reserved space. BarsCue and TextCue are built-in factories. A custom
CueFactory receives CueContext and returns CueContent: local Scene objects plus
explicit layout width and height. Content and display behavior can therefore be
replaced independently of the input marker syntax.

Use bind_cues for plain DocumentLayout or bind_lyric_cues for LyricLayout, supplying
a mapping of preset names to CuePreset values. Inline cues reserve body space;
independent cues use their configured position without reserving lyric width.
Ruby follows the same inline reservation/release rule as its associated body.
The default cue trigger is the first relevant singing interval; a preset may
specify an absolute trigger. No beat grid is inferred.

See [scene_lyric_cues.py](../../examples/scene_lyric_cues.py) and
[scene_cue_follow.py](../../examples/scene_cue_follow.py) for complete custom
factories, text content, timing, and following.

## Input marker contract

The input carrier is an ASS comment block:

```text
{kara:v1 cue id=count-in preset=bars placement=inline}
```

The exact `kara:` prefix follows the opening brace. Version `v1` supports cue
markers with required nonempty id and preset keys and optional placement
`inline` or `independent` (default inline). Unknown versions, kinds, keys,
duplicate keys, malformed quotes, and invalid placements are rejected.

Values use POSIX shlex quoting without shell execution or expression evaluation.
Names may contain Unicode, spaces, quotes, and equals signs. Braces, backslashes,
and newlines are not allowed within names. Use CueMarker.markup() to quote names
correctly. It serializes the marker declaration, not its numeric offset: a
serialized marker's location in the decoded body determines its offset.

Marker IDs are unique within one source record. Explicit Python CueMarker values
provide the same behavior without editing the ASS. Offsets must be inside the
body and on cluster boundaries; invalid anchors inside ruby/continuation syntax
are rejected during projection.

Parser diagnostics identify a Document record index and a code-point offset in
the original Text string, including preceding tags. This differs from the marker's
decoded body offset. Compilation preserves the original as a source comment and
consumes the marker; generated Dialogue uses standard ASS tags. Use standard ASS
color/reset tags for input colors rather than inventing player-side extensions.
