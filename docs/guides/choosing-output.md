# Choose an output for your song

| Output | Python entry point | Supported examples |
| --- | --- | --- |
| Standard ASS for subtitle players | `scene.ass.compile().document.save("song.ass")` | Text, vector drawings, hard karaoke wipes, native moves and eligible transforms such as fades |
| Standalone libplacebo shader | `scene.export("song.hook", fps=60)` | Feathered wipes, glyph and outline gradients, procedural particle motion |

ASS compilation raises `SceneCompileError` with the object ID when an effect
requires frame sampling, color strips (including soft scanlines and blended halos). Increasing
the event budget does not enable these effects. For a duotone hard wipe use
`KaraokeEffects.duotone(feather=0)`. A Sparkle built from a native tween can
also export to ASS. Petal motion requires a hook.

The hook exporter has its own limits. For example, native ASS events, vector
and inverse clips are unsupported in hooks.
See [ASS playback](../ass-and-playback.md), [ASS compilation](compilation.md)
and [hook playback and limits](gpu-rendering.md).
