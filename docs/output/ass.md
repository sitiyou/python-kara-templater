# Export standard ASS

Compile a scene to a standard ASS file for players such as mpv and libass without requiring plugins or shaders. Check which effects compile natively, tune resource budgets, and keep fonts and playback flags consistent across environments.

## Compile a Scene to ASS

Call `scene.ass.compile()` to build a new `Document` along with cost reports and diagnostics. Compilation never modifies your source `Document` or scene objects.

```python
result = scene.ass.compile()
result.document.save("song.ass")
```

The ASS exporter supports static text and vector drawings, linear `MoveAlong` and position `Tween`, eligible native transforms (`Tween`, `FadeIn`, `FadeOut` with `linear_rate` or quadratic `ease_out` for fades, when held), hard wipes, `RectangleKeyframes`, static and inverse vector clips, and preserved `AssDialogue` records.

Effects that need per-frame sampling, gradients (`LinearGradient`), feathered or slanted wipes (`sweep_angle != 0`), color strips (soft scanlines or blended glow), `Extrusion`, or custom shader paint raise `SceneCompileError` with the failing `object_id`. Preserving an `AssDialogue` keeps already-authored ASS tags intact, though its overrides do not become editable `Scene` properties.

ASS event start and end times round to the nearest centisecond (10 ms), with exact half steps rounding to the even centisecond. `result.max_time_quantization` reports the largest adjustment in seconds. Raw `Document.save()` serialization is unaffected.

## Budgets and compilation reports

Compilation checks whole-scene resource budgets so a script cannot silently grow too heavy for a subtitle player. A budget failure never silently lowers quality or drops detail.

| Limit | Default | What it caps |
| --- | --- | --- |
| `max_events` | `25,000` | Generated ASS events (CLI defaults `--max-events` to `10,000`). |
| `max_bytes` | `10,485,760` (10 MiB) | Serialized output ASS size, including retained source lines and marker comments. |
| `max_active` | `1,000` | Maximum simultaneously visible non-comment events. |
| `max_path_points` | `4,096` | Points per vector path, outline, or clip. |
| `max_boolean_work` | `1,000,000` | Clip boolean intersection work. |
| `clip_error_px` | `0.75` | Maximum interpolation error in screen pixels for eased rectangle clips. |

Pass an explicit `AssBudget` when an intentional effect needs higher limits, and optionally pass `on_estimate` to inspect `AssEstimate.estimated_events` before events are emitted:

```python
from kara_templater import AssBudget, AssEstimate

def check_size(estimate: AssEstimate) -> None:
    if estimate.estimated_events > 5_000:
        raise RuntimeError(f"Too many events: {estimate.estimated_events}")

result = scene.ass.compile(
    budget=AssBudget(max_events=40_000),
    on_estimate=check_size,
)
```

Raising inside `on_estimate` cancels compilation cleanly without touching the source document.

Inspect `AssResult` to see why a scene costs what it does:

- `result.event_count`, `result.peak_active`, `result.byte_count`, and `result.estimated_events` summarize whole-scene cost (`event_count` counts generated `Dialogue` lines, not comment markers).
- `result.objects` holds one `AssObjectReport` per object with its `id`, compilation `strategy`, `events` count, `origin`, `peak_path_points`, and `peak_clip_points`.
- `result.diagnostics` and `result.event_origins` help trace warnings and generated events back to their source lines.

## Fonts and playback settings

`load_font(path)` registers font bytes only inside Python for layout measurement. It does not embed fonts into the saved `.ass` file. Provide the exact same font files to the player—either installed on the system, attached to the container (such as MKV font attachments), or via the player's font directory.

> [!IMPORTANT]
> Matching a font family name is not enough to guarantee identical layout. Different font versions or fallbacks can change character widths, line breaks, and outlines.

Rendered pixels also depend on `PlayRes`, video dimensions, timestamp, color matrix, and scaling. Keep all of these fixed when comparing renders. For pixel-exact material checks, use RGB or full-resolution chroma output; YUV420 chroma subsampling can create faint fringes along sharp colored edges.

## Renderer differences and mpv flags

Standard ASS syntax does not guarantee identical pixels across renderers. The [libass differences guide](https://github.com/libass/libass/wiki/Differences-between-Libass-and-VSFilters) documents differences from VSFilter-family renderers in outlines, transforms, fractional font sizes, border styles, font selection, and color handling.

When playing an RGB-authored script in mpv, disable user style overrides and VSFilter color remapping using the [ASS override option](https://mpv.io/manual/stable/#options-sub-ass-override) and [VSFilter color compatibility option](https://mpv.io/manual/stable/#options-sub-ass-vsfilter-color-compat):

```sh
mpv video.mkv --sub-file=effect.ass --sub-ass-override=no --sub-ass-vsfilter-color-compat=no
```

Test font discovery, scaling, entry and exit, repeated highlights, continuous playback, and seeking in your target delivery player.

## Preview and validate from a checkout

From a repository checkout with FFmpeg and the checks dependencies installed, you can render the ASS gallery fixture with the package's CPU preview:

```sh
python -m tools.render_gallery --case word-backgrounds
```

This writes the compiled ASS, copied preview fonts, and a report under `build/gallery`, and updates the GIF under `docs/examples/assets`. Pass `--output` and `--assets` to experiment locally without replacing tracked previews.

To verify that continuous playback and random seeks match in system libass on a built-in scene (`cues` or `native-tween`):

```sh
python -m tools.validate_scene_core --scene cues build/preview-cues
```

This writes the compiled ASS and a diagnostic report to the target directory. It validates the configured preview environment rather than every third-party player.

## Next steps

- [Choose an output](README.md)
- [Choose and register fonts](../guides/fonts.md)
- [Play and render a Hook](hook.md)
- [Troubleshooting](troubleshooting.md)
