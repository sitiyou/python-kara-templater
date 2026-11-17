# GPU-enhanced ASS

![Shader gradient and eased motion](../examples/assets/gpu-gradient.gif)

Complex continuous color fields and sampled motion can produce very large
standard ASS files. The GPU path keeps an ordinary ASS fallback and stores an
additional, versioned effect payload in private `Comment` records. Normal
players show the fallback. `kara-render` uses the enhanced presentation instead.
It does not install shaders into mpv or change libass.

## Author once, choose output

Use the same Scene, Tracks, lyric timing and animation callbacks. For ordinary
ASS, continue using `scene.compile()`. For enhanced output:

```python
from kara_templater import (
    Color, ColorRamp, ColorStop, Document, Lifetime, Line,
    LinearGradient, Scene, TextObject, Vec2, VisualState,
)

fallback = Document.create(width=640, height=360)
fallback.records.append(Line(
    text=r"{\an7\pos(100,140)\fs56}Sing in color", end_time=3000,
))
scene = Scene(fallback).add(TextObject(
    id="lyric", text="Sing in color", font_size=56, lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(100, 140), border=2),
    material=LinearGradient(axis="y", space="local", fill=ColorRamp((
        ColorStop(5, Color.hex("#60E8FF")),
        ColorStop(65, Color.hex("#F075CB")),
    ))),
))
scene.enhance(fallback, fps=60).save("song.enhanced.ass")
```

[The runnable example](../../examples/gpu_gradient.py) also adds eased scaling
and departure through the ordinary animation API.

`fallback` is an explicit, complete ordinary-ASS presentation at the same script
resolution. A useful fallback has the source lyrics, karaoke timing, layout and
simple colors. It need not reproduce every GPU effect. The enhanced renderer
replaces this presentation as a whole; it does not draw both versions or merge
unrelated fallback events automatically. The caller's fallback stays unchanged.

`LinearGradient` becomes a continuous fragment-shader color field, including
multiple color stops inside a single glyph. The standard ASS `step` setting has
no effect on shader smoothness. Local gradients follow the glyph's transform;
screen gradients remain in screen coordinates. Sweeping a clip does not resize
or restart the gradient. The existing Scene evaluator still determines lyric
pulse duration, easing, pivots, and each character's departure time.

## Render video

Install the optional Python adapter, FFmpeg, and an OpenGL-capable driver:

```sh
python -m pip install 'kara-templater[gpu]'
kara-render song.enhanced.ass video.mp4 song.rendered.mp4
```

From a checkout with uv:

```sh
uv run --extra gpu kara-render song.enhanced.ass video.mp4 preview.mp4 \
  --start 36 --duration 12
```

The default headless context backend is `egl`. `--backend` selects another
ModernGL context backend when supported by the host. Current hardware validation
uses Linux EGL with an AMD Radeon 780M; Windows/macOS GPU execution is not yet
validated. Context creation fails explicitly when unavailable. Merely loading
or exporting ASS does not require ModernGL or a GPU.

Frames stream through a pipe to FFmpeg; no image sequence is saved. The output
uses the payload's resolution and frame rate, H.264 video and AAC audio from the
selected source-video interval. Video after the last enhanced subtitle is retained. `--start` must align with the stored frame grid;
`--duration` rounds up to a frame. Existing outputs require `--overwrite`.
A failed render leaves the prior output intact. CPU encoding and GPU readback
still contribute to render time; this is not a zero-copy video pipeline.

## Current scope and limits

The first backend supports text and static vector paths, affine animation,
opacity, ordinary local/screen rectangle clips, and fill/outline linear gradients
with 2–16 color stops. Gradients use encoded RGB interpolation. Glyph fill,
outline and shadow retain separate coverage. Native stroke/blur/shadow coverage
is cached; this version does not implement shader blur, distortion, or a particle
simulation shader. Existing effects made from supported moving objects can use
the adapter without another animation API.

Native ASS events, explicit coverage groups, inherited/vector/inverse clips,
deformed paths and other paint fields currently raise an error. There is no
silent conversion to a different composition model. Cached glyph textures also
mean large magnification differs from rerasterizing font outlines at every scale.

Version 1 evaluates author callbacks at export and stores frame-indexed numeric
draw commands with shared coverage masks. It contains neither Python code nor
arbitrary shader source. Playback does not require the author's effect script or
font for the enhanced glyphs; ordinary fallback playback still needs its fonts.
This payload is not a full-color frame sequence. It is also not frame-rate
independent: export again to change fps or animation. Edit the source recipe and
export again after changing fallback events; the reader verifies its digest.

Export limits are 250,000 frames, 64 MiB of shared mask bytes, 64 MiB compressed
payload and 512 MiB decoded payload. Runtime caches are bounded separately. These
limits make costs explicit; the enhanced file can still grow with scene length
and complexity. The decoder validates version, parts, checksums, dimensions,
resource references, and sequential frame indices. Ordinary ASS parsing only
preserves the comments and never runs them.
