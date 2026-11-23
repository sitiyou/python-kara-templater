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

Volume columns and shape lamps default to half the authored font size at the marker. A size of 100 gives a 50 px lamp, and a size of 80 gives a 40 px lamp in any font family. Adjust `size_ratio` to choose another proportion. Bars and text countdowns follow the full authored size by default. Text countdowns draw their labels in their own font.
For columns, `column_width_ratio` sets each column’s width as a fraction of the group height
(default 0.25). `VolumeCue(align="bottom")` puts the shorter bars on the same baseline as the
tallest one. Choose `"top"` or `"center"` (default) to align their tops or centers.
Set `height` on `VolumeCue`
or `size` on `SignalCue` for a fixed size in script pixels. Built-in lamps have a
small reflection that fades with the lamp. Set `edge_brightness=0` to remove it.

Set a track's solid lyric colors once with `KaraokeEffects`. Lamps use the sung
fill and outline throughout the countdown. Each column switches from the unsung
pair to the sung pair as its turn arrives. With source styling alone, the first
nonblank body run supplies ASS secondary, primary and outline colors. The marker anchors the cue to the lyric layout.
For volume columns, `transition=0` makes each flash blink off for the middle half of its cycle.
Higher values soften the fade. The default is `0.67`. Changing it keeps the final fill on beat.
With `zoom_pulse` or `zoom_pulse_scanline`, each lamp grows during its own
countdown step. Each column grows during its fill step and settles over 0.30 s,
using the same curve level as the sung text.

To reuse a fixed role palette across tracks, pass a `PaintPair` to
`CuePreset(colors=...)`. The vector cues read its fill, primary outline, secondary outline, opacity
and static glow. A `SecondaryOutline(color, width=6)` adds 6 script pixels
outside the lyric’s primary outline. The cue scales this width to its own size.
Use `sung_secondary_outline` on the lyric recipe to change the outer ring
as each column fills. Lamps inherit the sung ring throughout the countdown.
`base_glow` and `glow` independently supply the unsung and sung halo.
For a sung gradient use `KaraokeEffects(material=LyricGradient(colors, axis="x"))`.
Leading inline volume columns share the first nonblank singer’s horizontal ramp.
When the line changes styles, the columns extend only to that singer’s last advance.
Columns switch from `base_material` to `material` on their individual fill steps.
Set `SignalCue(spacing=8)` for eight extra script pixels between adjacent lamps.
A separate lamp row uses the sung palette and spans all of its original slots, so the remaining lamps
keep their colors during countdown. Explicit cue colors take precedence.
Callback-generated decorations need a custom cue drawing.

### Sing an inline vector symbol

For symbols that fill in time with the lyrics and stay visible after their beat,
give each symbol an ordinary karaoke interval in the body, for example
`{\k30}◆{\k30}◆{\k50}歌`. Map the marker to a drawing on the track:

```python
from kara_templater import KaraokeEffects, Track, Vec2, VectorGuide, VectorPath

triangle = VectorPath.polygon(Vec2(0.1, -0.75), Vec2(0.7, -0.4), Vec2(0.1, -0.05))
track = Track(
    id="main",
    guide_symbols={"◆": VectorGuide(triangle, advance=0.8)},
    effects=(KaraokeEffects(singing="utopia_scanline"),),
)
```

The path coordinates and advance are multiples of the authored font size at the marker, or the guide’s explicit `size` in script pixels. Zero y is the
baseline and negative y extends above it. The mapping applies to every matching
body character on that track. Existing timed placeholder characters can use
their original intervals. The column advance positions the next lyric, while
the ink bounds set the sweep distance. Ruby and outline clearance use the
replacement geometry. To anchor two symbols to the first sung character, give
both symbols a `\k0` interval before it. With the built-in wipe they retain their
waiting color on the onset frame and switch at the next ASS centisecond.
Ordinary ASS and standalone hooks both draw the path.

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

Pass a fixed song tempo with `prepare_tracks(document, tracks=tracks, bpm=180)`,
or pass `bpm` to `bind_cues` or `bind_lyric_cues`. A preset with automatic timing
ends at the first sung syllable. A volume countdown reserves one beat for the final fill and `flash_ratio` beats per flash. With the default three flashes, the four stages last two seconds at 120 BPM. The column count divides the final beat. For other cues each step budgets four beats rounded to the
nearest millisecond. At 1800 ms or longer the budget is halved (whole milliseconds).
Three steps at 180 BPM span 3.999 seconds. Nonuniform `steps` divide the total in
the declared proportions. With BPM, an explicit `duration` overrides that
budget and an omitted `lead` follows the duration. Without BPM each omitted
field independently defaults to one second. Use `preset.resolve_timing(bpm=bpm)`
to check the required pre-roll before adding a marker.

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
independent cues use their configured canvas position by default. To keep a
separate guide clear of ruby on alternating rows, set the Track preset to
`CuePreset(factory=BarsCue(), line_edge="above")`. The allocator
receives the combined bounds of the measured lyric row and guide. Use
`line_edge="below"` to place the guide beneath a top row.
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

An inline cue centers on the measured body cell at its marker. An end marker uses the last cell. The automatic guide gap is one eighth of the authored font size. Supply `CuePreset(gap=...)` to set a pixel distance, including zero. An inline cue in a vertical column advances the lyrics and readings by its measured height plus clearance. Independent cues with `line_edge` clear body cells, readings and other row cues that intersect their horizontal span.
