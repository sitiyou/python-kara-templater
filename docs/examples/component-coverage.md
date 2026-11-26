# Gallery cards and editable components

This index maps all 124 component library cards to editable controls or example requirements. Several comparison cards can demonstrate the same control. Read `effect_components()` for parameter declarations and script-resolution defaults.

Bound inputs on the solid-color scanline update shader uniforms directly. Other listed controls rebuild the scene. Source examples specify the geometry, timing, code, or renderer their effects require.

## Built-in presets

| Category | Card and component IDs |
| --- | --- |
| Entry (20) | `entry-none`, `entry-fade`, `entry-slide-in`, `entry-rise`, `entry-char-fade`, `entry-char-drip`, `entry-spin-flip`, `entry-utopia`, `entry-tilt-pop`, `entry-tracking-in`, `entry-wave-in`, `entry-stretch-in`, `entry-glow-in`, `entry-assemble-in`, `entry-sparkle`, `entry-ripple`, `entry-note`, `entry-petal`, `entry-snow`, `entry-snow-solid` |
| Exit (19) | `exit-none`, `exit-fade`, `exit-slide-out`, `exit-rise`, `exit-char-fade`, `exit-char-drip`, `exit-spin-flip`, `exit-utopia`, `exit-scatter-out`, `exit-converge-out`, `exit-stretch-out`, `exit-glow-out`, `exit-dissolve-out`, `exit-sparkle`, `exit-ripple`, `exit-note`, `exit-petal`, `exit-snow`, `exit-snow-solid` |
| Highlight (7) | `highlight-none`, `highlight-no-wipe`, `highlight-utopia`, `highlight-scanline`, `highlight-utopia-scanline`, `highlight-zoom-pulse`, `highlight-zoom-pulse-scanline` |
| Decoration (8) | `decoration-none`, `decoration-twinkle`, `decoration-twinkle-classic`, `decoration-note`, `decoration-ripple`, `decoration-petal`, `decoration-snow`, `decoration-snow-solid` |

## Individual examples

| Card ID | Component, parameter, or requirement |
| --- | --- |
| `default-recipe` | `entry-fade`, `exit-fade`, `highlight-utopia`, `decoration-none` |
| `duotone` | `lyric-colors.dual_outline` |
| `stroke-flash` | `stroke-flash` |
| `soft-front` | `soft-front` |
| `bars-cue` | `bars-cue` |
| `volume-cue` | `volume-cue` |
| `signal-cue` | `signal-cue` |
| `text-cue` | `text-cue` |
| `fade-in` | `fade-in` |
| `fade-out` | `fade-out` |
| `slide` | `slide` |
| `jump` | `jump` |
| `scale-pulse` | `scale-pulse` |
| `curve-in` | This clip uses sampled easing along a custom curve. |
| `drift-out` | `drift-out` |
| `scatter-out` | This clip assigns each glyph a sampled departure path. The entry and exit presets include built-in scatter and dissolve. |
| `tween` | `tween-scale.scale` sets the end scale. The example also supplies a destination and a two-stage curve. |
| `move-along` | Requires an authored path and a target for that path. |
| `lyric-highlights` | `lyric-colors` |
| `karaoke-theme` | `lyric-colors` |
| `lyric-gradient` | `lyric-gradient` |
| `linear-gradient` | `lyric-gradient.axis` |
| `glow` | `glow` |
| `secondary-outline` | `outline` |
| `extrusion` | `extrusion` |
| `material-effect` | Requires WGSL and a binding for each visibly editable input. |
| `shader-paint` | Uses authored GLSL and custom arguments. |
| `sparkle` | `sparkle` |
| `petal` | `petal` |
| `ribbon` | Requires the ribbon path and a timed particle factory. |
| `lyric-echo` | `echo` |
| `echoes` | Copies whole objects using an authored object and clock. |
| `ruby` | `ruby-layout` |
| `karaoke-rows` | `karaoke-rows` |
| `vector-guide` | Requires a character-to-vector-path mapping. |
| `rectangle-clip` | The example defines a clip in scene coordinates with explicit keyframes. |
| `trail-path` | Requires an authored path and a trail length. |
| `write-path` | Requires ordered strokes for the drawing. |
| `morph-path` | Requires source and destination paths that can be interpolated. |
| `timeline` | Requires ordered, authored time anchors and animation intervals. |
| `shader-motion` | Requires paired shader code and a Python evaluator. |
| `transform` | The example supplies a transform callback. |
| `state-function` | Requires a state callback and declares which state values it can change. |
| `follow-object` | Requires a specific scene object as the reference target. |
| `object-group` | Requires a scene hierarchy with authored child objects. |
| `rectangle-function` | Uses an authored function for the moving rectangle. |
| `path-function` | Uses an authored function for the changing path. |
| `vector-clip` | This example uses standard ASS vector clipping. |
| `type-family` | `typography.fontname` |
| `type-size` | `typography.fontsize` |
| `type-bold` | `typography.bold` |
| `type-italic` | `typography.italic` |
| `type-spacing` | `typography.spacing` |
| `type-scale` | `typography.scale_x`, `typography.scale_y` |
| `type-border` | `typography.outline` |
| `type-blur` | `glyph-blur.blur` |
| `type-shadow` | `offset-shadow.x`, `offset-shadow.y` |
| `sweep-color` | `highlight-scanline.scanline_color` (supports live binding) |
| `sweep-brighten` | `band-brighten` |
| `sweep-follow-before` | `band-follow-before` |
| `sweep-follow-after` | `band-follow-after` |
| `sweep-width` | `highlight-scanline.scanline_width` (supports live binding) |
| `sweep-softness` | `highlight-scanline.scanline_softness` (supports live binding) |
| `sweep-strength` | `highlight-scanline.scanline_strength` (supports live binding) |
| `sweep-gradient` | `band-gradient` |
| `sweep-feather` | `soft-front.hook_feather` |
| `sweep-front-tint` | `soft-front.front_color` |
| `sweep-angle` | `highlight-scanline.sweep_angle` |
| `sweep-reverse` | `highlight-scanline.reverse_wipe` |
| `sweep-ruby` | `highlight-scanline.ruby_scanline` |
