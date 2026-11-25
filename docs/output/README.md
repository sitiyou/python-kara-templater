# Preview and export

Write materials in WGSL, preview effects live in the browser, or export a playback shader. Compile standard ASS from the same scene when you need an editable subtitle file.

## How the scene shader is built

At export time, Naga validates WGSL material functions and translates them to GLSL. The scene compiler adds those functions to its GLSL renderer and prepares glyph masks and timeline data for the playback host. The current scene shader exports are GLSL. WGSL is the source language for the material functions.

| Use case | Python API | Result |
| --- | --- | --- |
| Preview live in a browser | `scene.preview()` | Opens a self-contained WebGL 2 player with playback, scrubbing, and named material controls. |
| Use your own preview player | `scene.export_resources("preview-resources")` | Writes GLSL, binary textures, and `textures.json`. |
| Play or render over video | `scene.export("song.hook")` | Packages the shader and textures as a libplacebo `.hook` for mpv or FFmpeg. |
| Deliver a conventional subtitle | `scene.ass.compile().document.save("song.ass")` | Compiles standard ASS for subtitle renderers such as libass and VSFilter. |

## Preview live in a browser

Call `scene.preview()` after building a scene. It opens your default browser and returns the path to the HTML file. You can reopen that file offline.

```python
preview_path = scene.preview()
```

To inspect a chorus or generate a preview on a headless machine, pass a filename and a time window:

```python
scene.preview("chorus.html", start=36, duration=8, open_browser=False)
```

`start` and `duration` are in seconds. Align `start` to the requested frame rate. Material edits apply to the open preview. See [Export a time interval](hook.md#export-a-time-interval) for frame-rate and window limits.

## Shader rendering and standard ASS capabilities

| Aspect | Shader rendering | Standard ASS |
| --- | --- | --- |
| Fonts on playback machine | Not required; glyph masks are baked at export time | Required; install or attach fonts in the container |
| Supported effects | Text, static paths, feathered and slanted wipes, gradients (up to 16 stops), soft scanlines, blended glow, extrusion, GPU motion, WGSL materials, `Petal` and `Sparkle` particles | Text, vector drawings, hard wipes, linear moves, eligible transforms and fades, static/inverse vector clips, linear `Sparkle` particles, preserved `AssDialogue` |
| Unsupported features | `AssDialogue`, vector and inverse clips, group-local clips, deformed paths, object references | Gradients, feathered or slanted wipes, soft scanlines, blended glow, extrusion, shader paint/materials, frame-sampled animations |

## Play or render right away

Preview a Hook over your video in mpv without burning subtitles into the file. Disable subtitle autoload so mpv does not draw a second lyric layer on top of the shader:

```sh
mpv --vo=gpu-next --sub-auto=no --glsl-shader=karaoke.hook video.mp4
```

Burn the Hook into a finished video with FFmpeg at the matching export frame rate (60 fps by default):

```sh
ffmpeg -init_hw_device vulkan=vk -i video.mp4 \
  -vf 'fps=60,libplacebo=custom_shader_path=karaoke.hook' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac karaoke.mp4
```

When your effects fit standard ASS, compile and save the subtitle file from Python:

```python
result = scene.ass.compile()
result.document.save("karaoke.ass")
```

## Keep a template compatible with ASS

If a scene uses an effect that standard ASS cannot represent—such as a gradient, feathered wipe, soft scanline, blended glow, extrusion, or procedural motion—`scene.ass.compile()` raises `SceneCompileError` with the failing `object_id`. Raising `AssBudget` limits does not enable unsupported effects.

To author a template that exports cleanly to ASS:

- Use a hard two-color wipe such as `KaraokeEffects.duotone(feather=0)` instead of a feathered or slanted sweep.
- Keep fills and outlines solid rather than using `LinearGradient` or custom WGSL materials.
- Use linear particle factories like `Sparkle` rather than custom-motion factories like `Petal`.

> [!TIP]
> You can export both outputs from the same project: distribute a Hook for full-quality rendering alongside a simpler fallback ASS file for players that only read subtitles.

## Next steps

- [Play and render a Hook](hook.md)
- [Export standard ASS](ass.md)
- [Troubleshooting](troubleshooting.md)
- [Command line](../guides/cli.md)
