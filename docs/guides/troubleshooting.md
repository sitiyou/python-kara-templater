# Troubleshooting

Start from the error's object/source context and the smallest input that
reproduces it. Keep the traceback and exception cause when debugging callbacks.

| Symptom | What to inspect and change |
| --- | --- |
| Unknown public import | Ensure the installed package matches these current-checkout docs; use the final API reference rather than old implementation plans |
| `No module named examples` or `tools` | These are checkout utilities; standalone tutorial scripts use only kara_templater |
| Native extension fails to load | Install the matching Python/platform wheel and required native runtime libraries; see development setup |
| Missing or substituted glyph | Check the actual font family, fallback faces, and load_font registration; supply the same font to the ASS player. A hook carries coverage from the export machine |
| A text range or cue splits a cluster | Select complete independently drawable clusters, not arbitrary Python character boundaries |
| ASS appearance differs from the source | Imported lyrics use template appearance. Configure the font, colors and layout in the Track |
| Unknown cue preset/invalid marker | Match preset names, marker keys, quoting, offsets, and cluster boundaries to the input marker contract |
| Multiple Tracks match a source | Make selectors disjoint, or combine the intended appearance into one Track |
| Animation writes conflict | Check channel declarations, overlapping intervals, hold/release, and composition rules |
| Unexpected time offset | Check seconds versus milliseconds, object birth versus absolute time, and separate display/timing clocks |
| Object follows the wrong position | Distinguish local object evaluation from world-space SceneEvaluator references |
| PlayRes mismatch | Check Document script dimensions and the resolution used by the renderer or preview |
| A pulse disappears or a soft wipe looks sharper after export | Check which ASS path produced the file. [Check the supported effects](choosing-output.md) before changing the timing or colors. |
| Glow is cut off at a color front | Set `blend_glow=True` on an automatic wipe with matching halo blur and border |
| Group alpha looks too dense | Groups apply alpha to each drawing. Check the opacity of overlapping child layers |
| Event, byte, active, path or boolean budget fails | Inspect AssResult/AssObjectReport, simplify the effect, or deliberately raise the relevant AssBudget limit |
| Raster colors differ by tiny rectangles | Check RGB/full-resolution chroma composition, color matrix, and spatial error settings before comparing YUV420 output |
| Regeneration duplicates or leaves effects | Use a stable owner and preserve generated source/provenance markers |
| Same callback differs after seeking | Remove previous-frame state and global random draws; declare dependencies and breakpoints |
| Another player renders differently | Verify fonts, ASS support, and the known renderer differences in ASS and playback |

AssImportError identifies a Document record index, style, and optional origin.
SceneCompileError identifies an object_id and optional origin. Native output
errors can identify source references and time_ms. These indices refer to the
structured source model, not physical ASS file line numbers.

See [compilation](compilation.md), [fonts and preview](fonts-and-preview.md), and
[ASS and playback](../ass-and-playback.md) for reproduction steps.
