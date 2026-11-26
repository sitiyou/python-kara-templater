# Colour and materials

Style lyrics and shapes with RGB colours, gradients, outlines, glows and custom WGSL shaders. Use this guide to move beyond flat fills and write per-pixel effects.

## Colours and visual roles

Author all colours in RGB using `Color(r, g, b)`, `Color.hex("#RRGGBB")`, or named constants such as `WHITE`, `CYAN`, `YELLOW`, `PINK`, `ORANGE`, `RED`, `GREEN`, `BLUE`, `PURPLE`, `MAGENTA`, `GRAY` and `BLACK`. Opacity runs from `0` (transparent) to `1` (opaque). Standard ASS BGR encoding and inverted alpha are handled automatically on export.

`VisualState` controls an object's appearance channels: `fill`, `outline`, `border`, `blur`, `shadow`, `opacity`, `face_opacity` and `shadow_opacity`. Border and blur widths are measured in script pixels. Scaling an object does not scale its blur or border unless you set `scale_border=True` on the object (for borders) or animate `border` and `blur` explicitly.

For layered lettering without managing manual copies, pair two helpers:

- `SecondaryOutline(color, width)` adds a solid outer rim beyond the primary border. A zero width hides it.
- `Glow(color, blur, border, opacity)` draws a soft halo behind both outlines. Use `Glow.from_studio(color, radius=10, outline=5)` to match a single-pass Gaussian halo whose pen extends `outline` script pixels beyond the glyph.

When fill, outline and glow need independent lifetimes, animation clocks or colour fronts, place them on separate scene objects.

## Gradients on lyrics and objects

Apply `LyricGradient` as `material` (highlight state) or `base_material` (waiting state) on `KaraokeEffects` or `LyricHighlights.from_timing`. You do not need to measure glyph boxes manually.

```python
from kara_templater import Color, LyricGradient, LyricHighlights, StatePatch

highlight = LyricHighlights.from_timing(
    StatePatch(),
    material=LyricGradient((
        Color.hex("#FFE7A0"),
        Color.hex("#F660A2"),
        Color.hex("#826AFF"),
    )),
)
```

With the default `axis="y"`, colours span each measured glyph vertically and follow its scale and translation. Body text and ruby readings each resolve their own height.

Set `axis="x"` to spread a gradient across all visible body ink in the line. Ruby readings sample the same horizontal positions, so adjacent syllables continue the ramp smoothly during a wipe.

For duets, pass a mapping from ASS style names (switched inline with `{\rLead}` and `{\rReply}`) to `LyricGradient` values:

```python
from kara_templater import Color, KaraokeEffects, LyricGradient

duet = KaraokeEffects(
    base_material=LyricGradient((Color.hex("#FFF1D8"), Color.hex("#ADE4F0"))),
    material={
        "Lead": LyricGradient((Color.hex("#FF0040"), Color.hex("#0040FF")), axis="x"),
        "Reply": LyricGradient((Color.hex("#FFCC00"), Color.hex("#00EE77")), axis="x"),
    },
)
```

Each singer's horizontal ramp spans all ink belonging to that style, even when singers alternate mid-line. Styles omitted from the mapping fall back to the recipe's solid highlight fill. You can also pass a custom factory `(line, target) -> LinearGradient | None` that runs once during preparation and can inspect `target.source_style`.

On direct `TextObject` and `PathObject` nodes, assign a `LinearGradient` built from `ColorRamp` and ordered `ColorStop` positions in script pixels:

```python
from kara_templater import Color, ColorRamp, ColorStop, LinearGradient

grad = LinearGradient(
    axis="y",
    space="local",
    fill=ColorRamp((
        ColorStop(5, Color.hex("#60E8FF")),
        ColorStop(65, Color.hex("#F075CB")),
    )),
)
```

Hook evaluates `fill` and `outline` ramps independently with up to 16 stops per ramp. Set `space="local"` to move the gradient with the object; the default `space="screen"` locks stops to canvas coordinates. See [the gradient example](../../examples/gpu_gradient.py) for a complete runnable script.

## Lyric highlight passes and halos

For standard karaoke sweeps with custom paint layers, use `LyricHighlights.from_timing` instead of manually building animated clip rectangles:

```python
from kara_templater import WHITE, YELLOW, Glow, LyricHighlights, StatePatch

paint = LyricHighlights.from_timing(
    StatePatch(fill=YELLOW, outline=WHITE, border=5),
    base_glow=Glow(WHITE, blur=8, border=10),
    glow=Glow(YELLOW, blur=12, border=14),
)
```

Pass `paint` in `Track.effects`. Source timing maps strictly onto undecorated measured text bounds, so thick outlines and glows never slow down the sweep. For a single linear interval, the engine automatically reserves short shoulders (`edge_duration=0.02` s by default) before and after timing to cross the decorative margins.

Useful options on `LyricHighlights.from_timing`:

- `base_paint`: overrides the waiting text appearance (for example `StatePatch(opacity=0)` to reveal text from invisible instead of recolouring it).
- `segment_colors`: maps `(unit_index, reading_index)` to a highlight `Color` for per-word palettes.
- `ruby_fill`: overrides the highlight fill for all ruby readings.
- `hook_feather`, `front_color`, `sweep_angle`, `reverse` and `wipe=False`: control the Hook wipe edge and direction just like on `KaraokeEffects`.
- `blend_glow`: `True` by default. When `base_glow` and `glow` share the same `blur` and `border`, Hook blends their colour and opacity smoothly across the front on one blurred glyph mask. Set `blend_glow=False` for separate clipped halos (required for ASS export).

When you need custom multi-pass wipes, pauses or overlapping highlight layers, construct `LyricHighlights(highlights=..., mode=...)` with explicit `Highlight` and `HighlightPass` declarations:

- `HighlightPass(time, region, round=0, rate=linear_rate, breakpoints=(), inverse_rate=None, reverse=False)` defines one horizontal sweep over measured line-local `x` bounds in absolute seconds. Set `reverse=True` to sweep right to left. For nonlinear speed with exact character arrivals (`HighlightArrival`), pass `ProgressCurve.at` as `rate`, `ProgressCurve.arrival` as `inverse_rate`, and the curve's time knots as pass-local `breakpoints`.
- `Highlight` combines passes with `repeat="hold"` (keep completed regions on new rounds) or `repeat="reset"` (clear prior rounds), and `end="hold"` or `end="hide"`.
- `LyricHighlights(mode=...)` chooses how overlapping highlights combine: `"union"` merges coverage, `"priority"` picks the winning highlight, and `"layer"` composites contributions in order.

## Write a WGSL material

Use a `MaterialEffect` when an object's shape and timing are already right and you want to compute each covered pixel's colour or opacity in WGSL.

Define a subclass of `MaterialEffect` with a `wgsl` string containing a `shade` function, return any extra parameters from `parameters()`, and attach it with `MaterialClip` to a `TextObject` or `PathObject`:

```python
from dataclasses import dataclass

from kara_templater import (
    Color,
    Document,
    Lifetime,
    MaterialClip,
    MaterialEffect,
    PaintInput,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)


@dataclass(frozen=True)
class TintPulse(MaterialEffect):
    color: Color
    strength: float

    wgsl = """
fn shade(ink: vec4<f32>, ctx: KaraPaintContext, color: vec3<f32>, strength: f32) -> vec4<f32> {
    let amount = strength * sin(3.14159265 * ctx.progress);
    return vec4<f32>(mix(ink.rgb, color, amount), ink.a);
}
"""

    def parameters(self) -> tuple[PaintInput, float]:
        return PaintInput("tint", self.color), self.strength


scene = Scene(Document.create(width=640, height=360)).add(
    TextObject(
        id="title",
        text="Shader ink",
        font_size=60,
        alignment=5,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(320, 180), fill=Color.hex("#7D6BF2")),
        material_effects=(MaterialClip(effect=TintPulse(Color.hex("#E8BD66"), 0.6)),),
    )
)
scene.export("tint-pulse.hook")
```

`shade` receives the current straight RGBA `ink`, a `KaraPaintContext`, and every value returned by `parameters()` in order. Return straight RGB and opacity in `0..1` (returning `ink.a` preserves glyph anti-aliasing).

| `KaraPaintContext` field | WGSL type | Meaning |
| --- | --- | --- |
| `local` | `vec2<f32>` | Object-local coordinates in script pixels |
| `screen` | `vec2<f32>` | Canvas coordinates in script pixels |
| `coverage` | `f32` | Native mask coverage in `0..1` |
| `time` | `f32` | Seconds since the `MaterialClip` started |
| `progress` | `f32` | Normalised clip progress in `0..1` |
| `component` | `u32` | Coverage plane: `0` fill, `1` outline, `2` shadow, `3` extrusion |

Python parameter types map to WGSL automatically: `float` becomes `f32`, `Color` becomes `vec3<f32>` in `0..1`, and `Vec2` becomes `vec2<f32>`.

Configure `MaterialClip(effect=..., start=0.0, duration=None, target="fill")` to choose when and where the shader runs:

- `start` is seconds from the object's clock origin; omitting `duration` runs until the end of the object's lifetime.
- `target` selects `"fill"` (default), `"outline"`, `"shadow"`, or `"all"`.
- Multiple clips active on the same plane run in declaration order, each receiving the previous clip's output.

During preview or shader export, Naga validates WGSL and translates the material functions to GLSL. Compilation errors include the affected scene object ID. See [the ribbon material example](../../examples/gallery_material.py) for another complete shader. If you need low-level raw GLSL instead of WGSL, see [`ShaderPaint`](../reference/paint.md#shaderpaint).

## Live parameters with PaintInput

Wrap a `float`, `Color`, or `Vec2` in `PaintInput("name", default_value)` inside `MaterialEffect.parameters()`. On a solid-colour `KaraokeEffects` scanline, you can bind the colour, strength, width, and softness.

Add a `PaintControl` to give the browser a label, unit, bounds, or slider step. Width and softness need explicit bounds in script pixels because the compiler uses the largest allowed width to reserve coverage. Strength stays between zero and one. At draw time, softness is limited to half the current width.

```python
from kara_templater import KaraokeEffects, PaintControl, PaintInput

scanline = KaraokeEffects(
    highlight="scanline",
    scanline_width=PaintInput(
        "band_width", 16, PaintControl(bounds=(2, 40), step=0.5, unit="px", label="Width")
    ),
    scanline_softness=PaintInput(
        "band_softness", 5, PaintControl(bounds=(0, 20), step=0.5, unit="px", label="Softness")
    ),
)
```

Reuse a name to link controls with matching types, defaults, and metadata. Give independent controls different names. Layout, timing, and effects that change precomputed masks still require a rebuild. Rebuild the `Scene` with your chosen values to carry them from an offline trial into an exported Hook.

Call `scene.preview()` to try the controls and restore their defaults offline. The player keeps edits in the current browser tab. To build a player, use `scene.prepare_hook().paint_inputs()` to discover inputs across the scene. Each window's `textures.json` lists the uniforms it actually uses and their optional `control` metadata. Keep the current values between windows and apply them to the uniforms present in each new window. [Play and render a Hook](../output/hook.md)

## Next steps

- Apply gradients and halos with presets in [Built-in karaoke effects](karaoke-effects.md).
- Animate position, scale and custom GPU motions in [Animation and timing](animation.md).
- Open a live preview or choose a playback target in [Preview and export](../output/README.md).
- Browse all colour and paint signatures in [Paint API reference](../reference/paint.md).
