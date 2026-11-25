# Core concepts

Understand the data model, time units, coordinate spaces, lifetimes, and export formats shared across kara-templater. Read this page once so the rest of the guides fit together.

## The pipeline

Every project moves through three objects before export: `Document` → `Track` → `Scene`.

### Document and records

A `Document` holds the canvas size (`meta.res_x`, `meta.res_y`, matching ASS `PlayResX` and `PlayResY`), named `Style` definitions (`document.styles`), and ordered `records` (`Script Info`, styles, and `Line` events accessed through `document.lines`).

- Use `Document.load(path)` to read an ASS file, `Document.parse(text)` for an ASS string, or `Document.create(width=..., height=...)` for a new script (defaults to 1280 × 720 and sets `YCbCr Matrix: None` so authored RGB colors are not shifted on playback).
- Use `document.save(path)` or `document.dumps()` to serialize ASS records.
- Python importers can also pass structured `lyric_sources` and `bpm` directly to `Document.create(...)` without synthesizing ASS dialogue lines.

When `build_lyric_scene` or `scene.replace_source(record_index)` replaces a source dialogue record, the original line is kept as an owner-marked ASS `Comment`. Regenerating with the same `owner` replaces only that owner's output while leaving other records untouched.

### Track

A `Track` defines one independent vocal stream, such as lead, harmony, or translation. Each `Track` declares:

- **Selection** (`source`): a predicate over `LyricSource` metadata (`style`, `actor`, `effect`, `chapter`). By default a track selects all lyric sources.
- **Placement** (`layout`, `region`): defaults to `KaraokeRows()` (two alternating bottom rows, or two right-to-left columns when `vertical=True`). Pass `Layout(...)` for fixed positions or custom row counts.
- **Display padding** (`preview`, `tail`): defaults to `preview=5.0` s and automatic `tail=None` (targets 1.0 s after the last timed unit including exit animation, preferring at least 0.2 s of hold before the exit). On a crowded row, extra preview and hold shrink before exit animations are scaled.
- **Effects** (`effects`, `theme`, `cues`, `styles`): a tuple of `KaraokeEffects`, `LyricRule` bindings, or custom callables that decorate each measured `LyricLine`.

Calling `build_lyric_scene(document, tracks=...)` measures every selected line with real font outlines, arranges non-overlapping rows, binds animations, and returns a `LyricScene` (a subclass of `Scene`).

### Scene and visual objects

A `Scene` combines a `Document` with visual objects you can evaluate or export:

- `TextObject` — literal Unicode lettering (`{`, `}`, and `\` display as characters, not ASS tags; newlines create line breaks).
- `PathObject` — a `VectorPath` drawing with fill, outline, blur, shadow, gradients, or material shaders.
- `ObjectGroup` — a hierarchical container whose transforms compose onto its children. Every prepared `LyricLine` is an `ObjectGroup`.
- `AssDialogue` — an already encoded ASS event passed straight through to ASS export.

Visual objects are immutable dataclasses with unique `id` strings across the entire `Scene` (including all nested children). Use `dataclasses.replace(...)`, `.animate(...)`, or `.copy(...)` to derive updated nodes, and `scene.add(...)` to attach extra objects to a `Scene`.

## Time units

Different layers match the conventions of their source format. Keep these three units straight:

| Where | Unit | Example |
| --- | --- | --- |
| Raw `Line.start_time`, `Line.end_time`, `DisplayWindow` | Milliseconds (ms) | `Line(start_time=1000, end_time=3000, ...)` |
| `\k`, `\K`, `\kf`, `\ko` tags inside `Line.text` | Centiseconds (10 ms) | `{\k50}` lasts 0.5 s |
| `Lifetime`, `TimeSpan`, `AnimationClip`, `Timeline`, `StateKeyframe`, `Track`, `LyricRule`, `KaraokeEffects`, `SceneEvaluator`, geometry/mask/paint callbacks | Seconds (s) | `Lifetime(1.0, 4.0)` |
| Serialized ASS event boundaries | Centiseconds (10 ms grid) | `0:00:01.00` |

Within `Scene` seconds, two clocks exist:

- **Absolute song seconds** start at `0` for the whole song. `Lifetime(start, end)`, `TimeSpan`, `SceneEvaluator.at(id, time)`, and `StateReference` lookups (`StateLookup`) use absolute seconds.
- **Local object seconds** start at the object's `time_origin` (normally `lifetime.start`). `AnimationClip`, `Timeline`, `StateKeyframe`, and object-local geometry, clip, and material callbacks use local seconds.

> [!TIP]
> A common mistake is writing seconds in `Line(start_time=...)` or milliseconds in `Lifetime(...)`. Remember: raw ASS `Line` uses milliseconds, `\k` tags use centiseconds, and all `Track` and `Scene` authoring uses seconds.

## Coordinates and anchors

All distances, font sizes, positions, borders, and offsets use **script pixels** defined by the `Document` canvas (`PlayResX` × `PlayResY`). The origin `(0, 0)` sits at the top-left corner, `x` increases to the right, and `y` increases downward. Rotation angles use degrees, and opacity runs from `0` (transparent) to `1` (opaque).

### Alignment anchors

`TextObject.alignment` (default `7`, top-left) and `Style.align` (default `2`, bottom-center) follow the ASS numpad 1–9 convention:

| Vertical \ Horizontal | Left | Center | Right |
| --- | --- | --- | --- |
| Top | `7` | `8` | `9` |
| Middle | `4` | `5` | `6` |
| Bottom | `1` | `2` | `3` |

A text object's `position` places that anchor point. Borders, glows, and drop shadows do not change text advance or layout boxes — always use measured boxes such as `range_bounds(...)` or `path_bounds(...)` instead of estimating width from character counts.

### Local vs world coordinates

Children inside an `ObjectGroup` use coordinates relative to their parent's `(0, 0)` origin. Parent position, scale, rotation, and skew compose with child transforms, and the group's `(0, 0)` origin acts as its transform pivot — grouping does not automatically recenter children. Note that `VectorPath.rectangle` starts at `(0, 0)`, whereas `VectorPath.circle` is centered on `(0, 0)`.

Every visual node stores its appearance and transform in a `VisualState` (`position`, `scale`, `rotation`, `skew`, `opacity`, `face_opacity`, `fill`, `outline`, `border`, `blur`, `shadow`, `shadow_opacity`):

- Transforms compose down the parent-child tree, and `opacity` multiplies per child (not as an offscreen flattened group).
- Paint colors (`fill`, `outline`) are not inherited from an `ObjectGroup`; set them on child objects or via lyric effects.
- `node.at(time)` evaluates only that node's own local animation clips. Call `scene.evaluator().at(node.id, time)` to evaluate world-space state with parent transforms and references applied.

## Lifetimes and clocks

A `Lifetime(start, end)` is an absolute, half-open interval `[start, end)` in seconds with `0 <= start < end`. An object is visible when `start <= time < end`.

- **Parent clipping**: A child's effective visibility is clipped by every ancestor's `lifetime`, without resetting the child's local animation clock.
- **Clips and holding**: Each `AnimationClip` starts at a local offset from `time_origin` and runs for a positive `duration`. By default (`hold=True`), its final channel values stay active after the clip ends; set `hold=False` to restore the base channels afterward. Two clips on the same object cannot write the same channel at the same time — conflicts raise an error explicitly.
- **Preserved clock origin (`clock_start`)**: Setting `clock_start` keeps an object's local animation, mask, and material clock anchored to an earlier time even when its visible `lifetime` is trimmed (for instance, during a tight track handoff). If visibility starts before `clock_start`, callbacks receive negative local seconds while scheduled clips wait until their clip start.
- **Copies**: `node.copy(id=..., offset=..., delay=...)` clones a node or group, assigns unique descendant IDs, remaps internal references, and shifts lifetimes and `clock_start` by `delay` while preserving local animation clocks.

## Lyric targets

`build_lyric_scene` builds each timed line as a `LyricLine` whose hierarchy exposes six queryable roles (`LyricRole`):

| Role | What it selects |
| --- | --- |
| `line` | The whole `LyricLine` group (body, ruby, and inline cues move together). |
| `syllable` | Each timed body unit together with its attached ruby readings. |
| `segment` | Individual timing intervals of a syllable (useful for repeated timings or `#` continuations). |
| `character` | Shaped body glyphs only (without detaching ruby readings from their syllable). |
| `ruby` | Shaped reading glyphs only. |
| `cue` | Attached count-in or guide cues. |

A `LyricRule` binds any `StateAnimation` (such as `FadeIn`, `ScalePulse`, `DriftOut`, or `Transform`) to a role or queried target at an anchor: `enter`, `exit`, `timing`, `after_timing`, or a custom anchor such as `HighlightArrival`. Original `\k` timing intervals stay fixed even when layout adjusts preview or tail padding.

## Live preview and export

A single `Scene` can produce shader previews and playback files or compile to standard ASS. The shader pipeline uses Naga to translate WGSL materials into GLSL before writing the preview resources or playback package.

| Use case | Entry point | Result |
| --- | --- | --- |
| Live browser preview | `scene.preview()` | Opens a WebGL 2 player for feathered wipes, soft scanlines, gradients, particles, and custom WGSL materials. |
| Video playback and rendering | `scene.export("song.hook")` | Packages the shader and textures for mpv or FFmpeg. |
| Standard ASS compatibility | `scene.ass.compile().document.save("song.ass")` | Produces a plain `.ass` file for subtitle players, with hard wipes and eligible ASS transforms. |

## Next steps

- [Import timed lyrics](guides/documents.md) — See every supported `\k` tag, ruby separator, and structured input option.
- [Lay out vocal tracks](guides/tracks.md) — Configure row rotation, spacing, vertical lyrics, and multiple vocals.
- [Animation and timing](guides/animation.md) — Build timelines, rules, duration-aware factories, and easing curves.
- [Preview and export](output/README.md) — Compare shader and subtitle capabilities.
