# Architecture

```mermaid
flowchart LR
    A[ASS file] --> D[Document]
    P[Python construction] --> D
    D --> L[Document text and lyric binding]
    D --> T[Track configuration]
    D --> E[Explicit Python templates]
    L --> S[Scene]
    T --> S
    E --> S
    C[Custom objects and animations] --> S
    S --> O[Standard ASS Document]
    S --> G[Shared evaluation and cached glyph coverage]
    G --> EGPU[ASS fallback with GPU Comment payload]
    EGPU --> R[Explicit GPU renderer and FFmpeg]
```

## Shared model

ass.py preserves ordered records and serializes standard ASS. Document text and
lyric modules project decoded text, styles, singing spans, ruby, and cue markers
with source mappings. LyricSource wraps parsed or structured DocumentLyrics. Track authoring, lyric
anchors and Scene object clocks use seconds; raw ASS records retain milliseconds.

scene.py defines text, path, group, and native-event objects. scene_animation.py
provides typed animation declarations and seekable evaluation.
SceneEvaluator composes hierarchy and reference dependencies in world coordinates.
Geometry, masks, paint fields, particles, and cues are independent typed extensions.

## Frontends

orchestration.prepare_tracks selects independent Track streams, measures lyric
objects, resolves timing rules from Track.effects, constructs its callable visuals once, collects
authored visual intervals, calls Layout.allocate once per stream, and binds
common animations to the prepared LyricLine targets. Custom callables can return
`line.schedule(...)`: animation factories resolve once per interval when declared, while reservation
and final alias binding use the same preparation helpers as Track rules.
Visibility changes retain
explicit local clock origins rather than rebuilding factory callbacks. LyricScene adds inspectable
plans to Scene without overriding compilation. Arbitrary row counts use the same
allocator; custom policies override its batch function. Source ownership and
same-source visual views remain separate.

The CLI default recipe uses this frontend, including its source-position
allocator and before/after paint rules. Effect scripts return a Scene or declare
Tracks. No new lyrics are pre-encoded into NativeEvents before compilation.

ObjectGroup.coverage declares explicit component and material bindings. Coverage, ordinary per-layer drawing, and completed-group
RGBA rasterization have different composition semantics and explicit budgets.
They are not interchangeable names for one rendering operation.

Karaoke sweep timing belongs to the lyric engine. Singing progress is measured
over undecorated text geometry; outline and glow margins must never expand
the distance traversed during the source singing interval. The built-in singing
highlighter reserves decorative edge transitions and lowers eligible linear
clips internally. Templates declare appearance rather than compensating for
blur in clip coordinates or source clocks.

engine.py preserves the Python ASS-template frontend and its context helpers.
Template execution prepares NativeEvents for Scene compilation. Its historical
preprocessing semantics are intentionally separate from new visual object
lifetimes. No template code runs from ordinary parsing.

## Compiler and native measurement

scene_output.py performs whole-scene preflight, strategy selection, deterministic
sampling, event merging, ownership handling, reporting, and final resource checks.
NativeEvent preserves already-lowered ASS while sharing output/provenance rules.
Rendered output is a new Document; caller-owned scene/source objects remain intact.

native/metrics.cpp and the bundled libass patches supply text measurement,
shaping, outlines, and raster coverage. The native build is keyed by source and
patch bytes, platform, and Python ABI. Python author callbacks are evaluated
before serialization; the player receives ordinary ASS rather than Python.

Public exports are defined once in kara_templater.__all__. Add a public interface
only when authors need it; internal preparation/compiler values stay internal.
The generated [API reference](../reference/README.md) documents the retained set.

## Optional GPU output

Scene.enhance accepts an explicit complete ASS fallback and uses the existing
SceneEvaluator to sample portable draw commands. `_gpu_scene.py` caches neutral
local glyph/path coverage, preserving object/material ownership. `_gpu.py`
composites coverage textures with affine state, clipping and shader gradients;
`_gpu_driver.py` bounds the untyped optional ModernGL dependency.

`_gpu_bundle.py` carries versioned, bounded data in private Comment records.
It serializes no Python callbacks or arbitrary shader source. `gpu_render.py`
explicitly decodes that data and streams premultiplied frames to FFmpeg. Ordinary
Document parsing remains data-only. Standard ASS compilation and its existing
strategies remain independent. See [GPU output](../guides/gpu-rendering.md) for
supported semantics and current limits.
