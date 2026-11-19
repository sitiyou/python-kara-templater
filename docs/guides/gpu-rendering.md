# Render a standalone GPU shader with FFmpeg

![Shader gradient and eased motion](../examples/assets/gpu-gradient.gif)

Export the ordinary subtitle for players and the shader for video production.
The hook includes glyph coverage, timing, gradients, clips and motion. The
rendering machine needs FFmpeg with libplacebo and a working Vulkan device.
The fonts and the Python authoring environment are needed at export time.

For a prepared lyric scene, write the playback ASS with
`scene.export_compact_ass("song.ass")` and the full shader with
`scene.export_hook("song.hook", fps=60)`. Both use the same prepared scene.
See [Export a song](karaoke-effects.md#export-a-song) for a Track-based entry point.
The lower-level example below supplies its own fallback for a raw Scene.

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
fallback.save("song.ass")
scene.export_hook("song.hook", fps=60)
```

The [gradient example](../../examples/gpu_gradient.py) writes both files.
For a matching-aspect, opaque SDR video starting at song time zero:

```sh
ffmpeg -init_hw_device vulkan=vk -i video.mp4 \
  -vf 'fps=60,libplacebo=custom_shader_path=song.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a copy output.mp4
```

Use the hook as the only subtitle layer. Loading the ordinary ASS on top draws
the lyrics twice. Audio stream copy requires a compatible output container.

## Extract a scene interval

```python
scene.export_hook("chorus.hook", fps=60, start=36, duration=8)
```

```sh
ffmpeg -init_hw_device vulkan=vk -ss 36 -i video.mp4 -t 8 \
  -vf 'fps=60,libplacebo=custom_shader_path=chorus.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac chorus.mp4
```

With the FFmpeg frame-counter clock, the first filter frame corresponds to
the exported start. Use the export frame rate and seek the input to that point.

## Seek with mpv

```sh
mpv --vo=gpu-next --gpu-api=vulkan --sub-auto=no --glsl-shader=song.hook video.mp4
```

mpv supplies the current video frame's presentation timestamp (PTS) in seconds.
The hook uses that timestamp to evaluate the animation on the export grid, including after
forward and backward seeks. Open the original video on the same timeline as the
lyrics. An interval hook exported for 36–44 seconds draws only during that
interval on the original video. A host that leaves PTS unset uses a sequential
frame counter, as in the FFmpeg command above.

## Data and limits

Static draws persist until an event changes them. Linear rectangle keyframes,
including lyric wipes, interpolate on the GPU. Isolated fades, position/scale/
opacity tweens, pulses, drift-outs with one easing, and Studio slides carry
timing and endpoint parameters. Each instance can have its own duration and
pivot. All instances use the same shader.

Use `linear_rate`, `smooth_rate`, or `smoother_rate` for built-in easing. A
custom piecewise-linear easing such as
`FadeIn(rate=ProgressCurve(((0, 0), (0.3, 0.8), (1, 1))).at)` stores its
normalized knots once across instances and durations. An arbitrary Python
easing on these motions can store a scalar sample track on the export grid;
identical tracks share storage. Curves outside [0, 1], other animation types,
references, and overlapping motions that need state capture use the Scene
evaluator for the affected leaf and interval. Arbitrary rectangle callbacks
also need evaluation while the object is visible.

The shader draws text/static paths in layer order, with affine transforms,
opacity, ordinary rectangle clips and continuous fill/outline linear gradients
(up to 16 stops). Stroke, blur and shadow coverage is rasterized at export. A fade on outlined
text can reuse two native masks. The shader selects the translucent border
when the fill fades so that the border does not show through the letter.
Use standard ASS compilation for native events; inherited/vector/inverse clips,
deformed paths and explicit coverage groups are unsupported by this backend.

Textures in the mpv hook format use hexadecimal text. Complex or long scenes
can produce large files; compress the hook for transport and extract it before
rendering. The command texture uses exact float indices (up to 2²⁴ scalar
entries). The coverage atlas is 2048 pixels wide and up to 8192 pixels high.
Split into frame-aligned intervals if a scene reaches a limit. Linux/AMD Vulkan
has been exercised on L4TS. The older Scene.enhance / kara-render workflow
remains available for previously authored projects with embedded GPU comments.
