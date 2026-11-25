# Choose an output

Export a standalone libplacebo Hook for full shader quality in mpv and FFmpeg, or compile standard ASS when you need an editable subtitle file. Both outputs are generated from the same scene.

## Hook vs standard ASS

The standalone Hook is the primary output format. It embeds glyph coverage, gradients, clips, and animation parameters in one shader file so playback looks the same regardless of installed fonts. Standard ASS is a compatibility format for subtitle players and workflows that need plain-text `.ass` events.

| Aspect | Standalone Hook | Standard ASS |
| --- | --- | --- |
| Python export | `scene.export("song.hook")` | `scene.ass.compile().document.save("song.ass")` |
| Playback and rendering | mpv (`--vo=gpu-next`) and FFmpeg (`libplacebo`) | ASS subtitle players (mpv, libass, VSFilter) |
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
