# Troubleshooting

Diagnose common issues across installation, lyric input, layout, animation, Hook export, and standard ASS playback. Start from the failing object ID or record index and reproduce the error with the smallest input.

## Read the error context

Exceptions point directly to the structured model rather than physical line numbers in an `.ass` file:

- `ValueError` during `Document.load`, `Document.parse`, or `DocumentText.require_supported()` reports the record index in `Document.records` and the text offset of an unsupported tag or syntax issue.
- `SceneCompileError` reports `object_id` and an optional `origin`; Hook errors also report the failing timestamp in seconds.
- `SceneReferenceError` reports `object_id` and an optional `origin` for missing targets, dependency cycles, or failed reference lookups.
- `LayoutCapabilityError` and `OutputCapabilityError` indicate missing native library capabilities in your runtime environment.

Keep the full traceback and exception cause when debugging custom callbacks.

## Installation and imports

| Symptom | Fix |
| --- | --- |
| Unknown public import | Confirm your installed `kara-templater` version matches these docs, and check the [API reference](../reference/README.md) for current symbol names. |
| `No module named examples` or `tools` | `examples` and `tools` only exist in a repository checkout. Standalone templates import only `kara_templater`. |
| Native extension fails to load | Install the matching wheel for your Python version and platform along with required native runtime libraries. See [Development setup](../contributing/setup.md). |

## Lyric input and tracks

| Symptom | Fix |
| --- | --- |
| Imported lyrics ignore source ASS font, color, or margins | Imported ASS provides text and timing; template styling belongs on `Track` (`styles`, `theme`, `layout`, and `effects`). See [Lay out vocal tracks](../guides/tracks.md). |
| Unknown cue preset or invalid marker | Match cue preset names, marker keys, quoting, offsets, and cluster boundaries to [Ruby readings and cues](../guides/text-and-cues.md). |
| Text range or cue splits a glyph cluster | Select complete, independently drawable clusters rather than arbitrary Python string slices. |
| Multiple `Track` objects match the same line | Make `Track.source` predicates disjoint, or combine the effects into one `Track`. |
| Re-running duplicates or leaves old ASS effects | Pass a stable `owner` (`--owner` on the CLI) and preserve generated comment markers in the ASS file. |

## Layout and fonts

| Symptom | Fix |
| --- | --- |
| Missing or substituted glyph | Check the exact font family name, fallback behavior, and `load_font` registration. For ASS playback, supply the same font file to the player; Hooks bake coverage from the export machine. See [Choose and register fonts](../guides/fonts.md). |
| `PlayRes` mismatch | Verify `Document.meta.res_x` and `res_y` match the resolution expected by your renderer or preview. |
| Group opacity looks too dark or dense | `ObjectGroup` multiplies opacity onto each child separately rather than compositing offscreen. Lower or adjust opacity on overlapping child layers. |

## Animation and timing

| Symptom | Fix |
| --- | --- |
| Conflicting animation writes | Check channel declarations, overlapping time intervals, `hold` settings, and composition rules in [Animation and timing](../guides/animation.md). |
| Unexpected time offset | Check seconds vs milliseconds (`Line` uses ms; `Scene` and `Track` use seconds), local time from object birth vs absolute time, and display windows vs lyric timing clocks. |
| Object follows the wrong position | `object.at(t)` evaluates local state only. Use `scene.evaluator().at(id, t)` for world-space coordinates after parent transforms and references. |
| Callback behaves differently after seeking | Remove previous-frame state and global random calls; use deterministic seeded randomness and declare dependencies and breakpoints. |

## Hook output

| Symptom | Fix |
| --- | --- |
| `SceneCompileError` on Hook export | Hooks do not support `AssDialogue`, vector or inverse clips, group-local clips, deformed paths, gradients with more than 16 stops, overlapping varying animations on one node, or reference-dependent transforms. See [Play and render a Hook](hook.md). |
| Hook GPU work, atlas, or data texture limit exceeded | Reduce simultaneous overlapping planes, tighten motion bounds (check `ShaderMotion` Python poses), or export shorter frame-aligned intervals with `start` and `duration`. |
| Lyrics draw twice in mpv or FFmpeg | Pass `--sub-auto=no` in mpv and do not load a fallback `.ass` on top of the Hook. |
| Glow is cut off sharply at the wipe edge | Ensure `blend_glow=True` (the default on `LyricHighlights`) is still enabled and that both before and after `Glow` use the same `border` and positive `blur`. |

## Standard ASS output

| Symptom | Fix |
| --- | --- |
| `SceneCompileError` on ASS compile | Gradients, feathered or slanted wipes, soft scanlines, blended glow, extrusion, shader paint, and frame-sampled animations require a Hook. Switch to Hook export or use an ASS-compatible option such as `KaraokeEffects.duotone(feather=0)` or `Sparkle`. See [Choose an output](README.md). |
| Event, byte, active, path, or boolean budget exceeded | Inspect `AssResult` and `AssObjectReport` to find the heaviest object, simplify the effect, or raise the specific limit in `AssBudget`. See [Export standard ASS](ass.md). |
| Faint colored fringes along sharp edges | YUV420 chroma subsampling blurs color transitions across 2 × 2 pixel blocks. Compare renders in RGB or full-resolution chroma. |
| Another player renders differently | Confirm the player loads the exact same font files and check mpv flags and known libass/VSFilter differences in [Export standard ASS](ass.md). |

## Next steps

- [Choose an output](README.md)
- [Play and render a Hook](hook.md)
- [Export standard ASS](ass.md)
- [Choose and register fonts](../guides/fonts.md)
