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

## Vertical ruby spacing

Set `Track(id="main", ruby_gap=6)` to leave 6 script pixels between the
bottom of the reading's hard outline and the top of the associated body text's
hard outline. This is also the default. Smaller values bring the reading closer;
zero aligns the outer ink bounds, and negative values allow overlap.

The engine measures shaped ink before animation, including the static stroke
and any reserved hard rim. Joined readings share a row: the lowest outlined
reading and highest outlined body glyph determine the gap for the group.
Shadows, glow and pulse animations may extend into this space. The measurement
uses the document's PlayRes; resizing the video scales the visible gap.

## Define and place cues

CuePreset chooses a factory, lead, duration, steps, gap, position, and whether to
keep reserved space. Choose a factory by its clock and appearance.

| Factory | Before singing | At the cue end |
| --- | --- | --- |
| `VolumeCue` | All columns pulse together, then change to the sung color left to right. Set `count` for the number of columns. | The entire signal clears. |
| `SignalCue` | Circles, squares, rounded squares, stars, eighth notes, sixteenth notes, paired notes or a custom vector path extinguish in the configured order. Optional slide during the fade. | The last lamp clears. |
| `BarsCue` | A descending bar countdown drops individual bars at the supplied steps. | The last bar clears. |
| `TextCue` | Each step displays its configured label. | The last label clears. |

By default the volume columns and shape lamps measure half the selected font’s measured em size at the
marker. Their outlines scale with the host font too. Set `height` on `VolumeCue`
or `size` on `SignalCue` for a fixed size in script pixels. Built-in lamps have a
small reflection that fades with the lamp. Set `edge_brightness=0` to remove it.

Set a track's solid lyric colors once with `KaraokeEffects`. Lamps use the sung
fill and outline throughout the countdown. Each column switches from the unsung
pair to the sung pair as its turn arrives. With source styling alone, the first
nonblank body run supplies ASS secondary, primary and outline colors. The glyph
at the marker still determines automatic dimensions.
For volume columns, `transition=0` makes each flash blink off for the middle half of its cycle.
Higher values soften the fade. The default is `0.67`. Changing it keeps the final fill on beat.
With `zoom_pulse` or `zoom_pulse_scanline`, each lamp grows during its own
countdown step. Each column grows during its fill step and settles over 0.30 s,
using the same curve level as the sung text.

To reuse a fixed role palette across tracks, pass a `PaintPair` to
`CuePreset(colors=...)`. The vector cues read its fill, outline, opacity and static glow. For a second
hard outline, use a `Glow` with zero blur and an outer radius larger than the
main outline. For example, with a 2 px main outline, `Glow(border=8, blur=0)`
adds a 6 px outer ring to the lyric. The cue scales that extra width to its
own size. A positive blur softens a ring around the contour, even with both
outline widths set to zero. Its layout slot stays fixed when the ring changes color. On a
`KaraokeEffects` recipe, `base_glow` supplies the unsung layer and `glow`
the sung layer. Explicit cue colors override their respective channels.
For a sung gradient use `KaraokeEffects(material=LyricGradient(colors, axis="x"))`.
Leading inline volume columns share the first nonblank singer’s horizontal ramp.
When the line changes styles, the columns extend only to that singer’s last advance.
Columns switch from `base_material` to `material` on their individual fill steps.
Set `SignalCue(spacing=8)` for eight extra script pixels between adjacent lamps.
A separate lamp row uses the sung palette and spans all of its original slots, so the remaining lamps
keep their colors during countdown. Explicit cue colors take precedence.
Callback-generated decorations need a custom cue drawing.

### Choose the countdown order

The marker's `placement` sets where the cue appears. Its preset's factory
sets what moves. For three inline lamps before a left-to-right lyric, choose
which lamp should still be visible on the final beat:

| Factory | All lit | After step 1 | After step 2 | Singing begins |
| --- | --- | --- | --- | --- |
| `SignalCue(direction="left_to_right")` | ● ● ● lyric | · ● ● lyric | · · ● lyric | · · · lyric |
| `SignalCue()` (default `right_to_left`) | ● ● ● lyric | ● ● · lyric | ● · · lyric | · · · lyric |

Here · denotes the space left by an extinguished lamp. Set `lead=duration`
to finish at the first sung syllable. For example, register
`CuePreset(factory=SignalCue(direction="left_to_right"), lead=5, duration=5)`
under the input marker's preset key. `steps` always increases in time.
`slide` moves each fading lamp by a pixel offset independently of the order.

For an early preview, `CuePreset(factory=SignalCue(countdown=2), lead=5, duration=5)` shows
all lamps for three seconds, then runs the configured steps during the final two seconds.

A leading empty `\k` advances the singing cursor; the default cue trigger uses
the first timed text. You can also supply an absolute trigger in seconds.
Keep `keep_space=True` for an inline cue whose host text must stay still.
See the [two-track example](../../examples/karaoke_signals.py).

A custom
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
