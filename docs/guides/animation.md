# Animation and timing

Animate lyric targets and scene objects using rules, timelines, easing curves and custom GPU motions. Use this guide when built-in karaoke presets do not match the motion you want.

## Animate lyrics with rules

Pass `LyricRule` entries in `Track.effects` to attach the same reusable animations to lines, syllables, characters, readings or cues without manual loops.

```python
from kara_templater import DriftOut, LyricRule, ScalePulse

animations = (
    LyricRule("character", "timing", ScalePulse(peak=1.06, peak_at=0.42)),
    LyricRule("character", "after_timing", DriftOut(), offset=0.14, duration=0.56),
)
```

Here each character pulses during its own timing interval, waits 0.14 s after its final timing interval, and drifts away over 0.56 s. Layout automatically reserves the exit time and keeps highlight layers synchronised with every animated character. See [the pulse and drift example](../../examples/lyric_pulse_drift.py) for the complete runnable script.

Every `LyricRule(target, anchor, animation, ...)` combines three parts:

- **Target (`target`)**: Choose `"line"`, `"syllable"`, `"segment"`, `"character"`, `"ruby"`, `"cue"`, or explicit `LyricTarget` objects queried from a line. Filter with `tags=frozenset({...})`.
- **Anchor (`anchor`)**: Choose `"enter"` (line display start), `"exit"` (finishes at line display end), `"timing"` (each timed interval), `"after_timing"` (end of the final timed interval; select `"segment"` to fire after each repeat), `HighlightArrival` (when a highlight front crosses each character), another `LyricTarget`, or a callable `(line, target) -> tuple[TimeSpan, ...]`.
- **Timing options**: Set `duration` (defaults to the timing interval or an `AnimationSequence`'s authored length), `offset` (seconds shift), `hold=True` (keep the final value), and `stagger` (seconds between targets in selection order). For `"exit"`, the last target finishes at display end plus `offset` and layout reserves the full staggered span; for other anchors, `stagger` shifts later targets forward.

When `pivot` is omitted on `ScalePulse`, `DriftOut`, `CurveIn` or `Transform`, `LyricRule` automatically pivots around each target's measured centre (body centre for lines and syllables so ruby and glow do not skew the axis). On direct scene objects, an omitted pivot uses the local origin `(0, 0)`. Pass `pivot=Vec2()` to force the local origin inside a `LyricRule`.

> [!NOTE]
> Scene lifetimes, animations, timelines and `LyricRule` offsets all use **seconds** (whereas raw ASS `Line` timestamps use milliseconds). See [Core concepts](../concepts.md) for the complete time-unit summary.

## Scale parameters to note length and font size

Two mechanisms let one rule adapt to short notes, held notes, and different font sizes without writing per-line loops.

### Relative expressions

Use `Note.duration`, `Glyph.font_size`, `Canvas.height` and `Animation.duration` directly in rule fields and compatible effect widths. Call `.clamp(minimum, maximum)` to keep values within sensible bounds:

```python
from kara_templater import FadeOut, Glyph, KaraokeEffects, LyricRule, Note, ScalePulse

ink = KaraokeEffects.duotone(feather=Glyph.font_size / 8)
attack = LyricRule("character", "timing", ScalePulse(), duration=Note.duration / 2)
release = LyricRule(
    "character",
    "after_timing",
    FadeOut(),
    offset=(Note.duration / 4).clamp(0.06, 0.20),
    duration=0.18,
)
```

Expressions resolve once during preparation before layout allocation. `Note.duration` requires a timing-based anchor (`"timing"` or `"after_timing"`), and `Animation.duration` can only be used in `offset` once duration is known.

### Per-interval factories

When an animation's parameters depend on note length or line geometry, pass a callable receiving a `LyricAnimationContext`:

```python
from kara_templater import LyricAnimationContext, LyricRule, ScalePulse, smooth_rate

def pulse(timing: LyricAnimationContext) -> ScalePulse:
    return ScalePulse(
        peak=1 + 0.06 * smooth_rate(min(1, timing.duration / 0.6)),
        peak_at=0.42,
    )

rule = LyricRule("character", "timing", pulse)
```

The factory runs once per resolved interval (never per rendered frame). A character timed for 0.25 s and repeated for 1.0 s receives two independent pulses.

Inside a factory, `timing.duration` is the requested duration or current interval length (excluding pauses), `timing.interval` is the absolute `TimeSpan` (or `None` for `"enter"` / `"exit"` before layout), `timing.target` holds the full timing history, `timing.line` provides measured layout, and `timing.resolve(...)` evaluates any relative expression. A factory may also return a multi-step `Timeline.animation` sequence; see [the syllable pulse example](../../examples/syllable_pulse.py).

## Built-in animations, timelines and easing

All scene objects (`TextObject`, `PathObject`, `ObjectGroup`) and `LyricRule` bindings share the same `StateAnimation` classes:

| Animation | Purpose |
| --- | --- |
| `Tween(target, rate=linear_rate)` | Interpolates a sparse `StatePatch` from the incoming state |
| `FadeIn(rate=linear_rate)` / `FadeOut(rate=linear_rate)` | Fades incoming opacity from or to `0` |
| `Slide(offset, entering, fast_reveal=True, rate=smooth_rate)` | Translates by `offset` and fades; entrances reach full opacity in the first quarter by default |
| `Jump(height=12)` | Moves upward by `height` script pixels and returns |
| `ScalePulse(pivot=None, peak=1.1, peak_at=0.5, rate=smooth_rate)` | Scales up and back around a fixed local pivot |
| `DriftOut(offset=Vec2(0, -36), scale=0.96, pivot=None, rate=smooth_rate, travel_rate=None)` | Drifts, shrinks and fades; set `travel_rate=linear_rate` for constant-speed travel with eased fade/scale |
| `CurveIn(offset=..., bend=..., scale=0.85, rotation=-12, pivot=None, rate=smooth_rate)` | Arrives along a quadratic curve to the base pose |
| `ScatterOut(spread=24, rise=36, rotation=30, scale=0.85, seed=0)` | Seeded factory for per-target rotating, drifting exits in `LyricRule` |
| `MoveAlong(path, rate=linear_rate, orient=False)` | Moves along a `Contour` or `Polyline`, optionally rotating with its tangent |

### Clips and timelines

For a single animation on an object, call `obj.animate(anim, duration=..., at=0, hold=True)`. For multi-step schedules, build a `Timeline`:

- `timeline.play(*animations, duration=..., at=None, hold=True, breakpoints=())` plays one or more animations simultaneously on compatible channels.
- `timeline.wait(duration)` advances the local cursor.
- `timeline.keyframes(*frames, at=None)` chains `StateKeyframe(time, target, rate)` targets in local seconds.
- `timeline.repeat(count)` repeats the schedule while keeping clip-local clocks and breakpoints.
- Assign `timeline.clips` to an object's `animations`, or read `timeline.animation` to freeze a reusable `AnimationSequence` for `LyricRule` or `.animate(...)`.

See [the timeline tween example](../../examples/scene_native_tween.py) for a full sequential and parallel `Timeline`.

An `AnimationClip` holds its final value by default (`hold=True`); set `hold=False` to restore earlier channels when the clip ends. Overlapping writes to the same channel raise an error rather than depending on evaluation order.

Local clocks normally start at `lifetime.start`. If you crop or extend an object's visibility without shifting its animations, set `clock_start` to keep the original absolute origin (`obj.time_origin` reports it). If visibility begins before `clock_start`, geometry and paint callbacks receive negative local seconds while clips stay unstarted until their local `start`.

### Easing curves

Pass any easing curve as `rate`:

- Built-in smooth curves: `linear_rate`, `smooth_rate` (cubic, zero velocity at ends), `smoother_rate` (quintic, zero velocity and acceleration at ends), `ease_in`, `ease_out`, `ease_in_out`.
- `there_and_back(peak_at=0.25, return_at=0.5, rise=ease_in, fall=ease_out)`: returns a reusable rise-hold-fall rate for `Tween`.
- `ProgressCurve(knots)` and `ProgressCurve.cubic_bezier(x1, y1, x2, y2)`: piecewise-linear or measured cubic Bézier curves with controls in `0..1`. They store knots once and run identically in Python evaluation and Hook GPU shaders.

Easing functions may overshoot finitely: RGB colours clamp to `0..255` and geometry extrapolates, while opacity must remain within `0..1` and border/blur nonnegative.

## Custom motion and continuous phrases

For quick custom motion based only on normalised progress `p` in `0..1`, use `Transform`:

```python
from kara_templater import Transform, Vec2, smooth_rate

exit_motion = Transform(
    offset=lambda p: Vec2(24 * smooth_rate(p), -36 * p * p),
    scale=lambda p: 1 - 0.04 * smooth_rate(p),
    opacity=lambda p: 1 - smooth_rate(p),
)
```

Each field (`offset`, `scale`, `rotation`, `opacity`) accepts a constant or a pure function of `p`. Omitted fields leave their channels untouched, and `Transform` infers written channels automatically (including `position` when scaling or rotating around a `pivot`).

When you need the full incoming `VisualState`, wrap a pure `(base, progress) -> VisualState` function in `StateFunction(function, channels=...)`. Keep callbacks deterministic with no previous-frame state or global randomness, and pass `breakpoints` for abrupt jumps.

> [!IMPORTANT]
> Arbitrary Python callbacks in `Transform` and `StateFunction` work in `SceneEvaluator`, but shader and ASS exports reject uncompilable Python callbacks. For custom equations in shader output, use `ProgressCurve` or `ShaderMotion` below.

### Keep a cursor moving smoothly through a phrase

A flying cursor or ornament following a lyric line must hit each syllable boundary on time without jerky speed jumps. Straight segments between a 100 ms syllable and a 600 ms syllable drop speed sixfold in one frame, while easing every segment individually stops the mark at every syllable.

To keep flight continuous across measured syllable positions (from `line.layout`), treat the syllable times and positions as knots of one phrase:

1. Compute the forward speed across each syllable span. At each interior knot between adjacent forward speeds `a` and `b`, set a shared horizontal speed using the harmonic mean `2 * a * b / (a + b)` (use `0` at a stationary rest).
2. For each span of duration `dt` from `x0` to `x1` with endpoint speeds `v0` and `v1`, place cubic Bézier horizontal control points at `x0 + v0 * dt / 3` and `x1 - v1 * dt / 3`.
3. Shape the vertical arc across the whole phrase and bank the object along the path tangent.

Check consecutive frames around short-to-long transitions and at the start and release of held notes.

## Author a GPU motion

Use `ShaderMotion` when you need custom equations that run directly on the GPU in preview and playback. Provide both a GLSL snippet (`source`) and a matching Python evaluator (`function`) for state capture and tile indexing on the output frame grid:

```python
from dataclasses import replace

from kara_templater import (
    Document,
    Lifetime,
    Scene,
    ShaderMotion,
    TextObject,
    Vec2,
    VisualState,
)

late_fade = ShaderMotion(
    lambda base, p: replace(base, opacity=base.opacity * min(1.0, 2.0 * (1.0 - p))),
    frozenset({"opacity"}),
    "alpha *= p < 0.5 ? 1.0 : (1.0 - p) * 2.0;",
)

scene = Scene(Document.create(width=640, height=360)).add(
    TextObject(
        id="title",
        text="GPU motion",
        font_size=56,
        alignment=5,
        lifetime=Lifetime(0, 2),
        state=VisualState(position=Vec2(320, 180)),
    ).animate(late_fade, duration=2)
)
scene.export("gpu-motion.hook")
```

Inside `source`, the GPU shader provides:

- `p`: normalised clip progress (`progress_offset + progress * progress_scale`).
- `item(data + i)`: reads the `i`-th float from `parameters=(...)`.
- Mutable local channels: `pos` (`vec2`), `scale` (`vec2`), `skew` (`vec2`), `angle` (degrees), `alpha`, `pen` (outline radius), `fill` (`vec3` in `0..1`), and `outline` (`vec3` in `0..1`).
- Helper `basisOf(scale, skew, angle)` returning the local linear transform matrix.

Declare every channel your GLSL writes in `channels=frozenset({...})`. Supported channels are `position`, `scale`, `skew`, `rotation`, `opacity`, `border`, `fill` and `outline`. Whenever `ShaderMotion` changes geometry (`position`, `scale`, `rotation` or `skew`), keep `function` faithful to the GLSL pose throughout the clip so Hook export places the object in the right screen tiles.

Pass reusable GLSL helper functions via `functions="..."` (using unique function names across a template). If you prefer generating GLSL from Python, you can optionally install Metashade, generate helper code once at module import time, and pass it to `functions=`.

## Sampling and output notes

The scene shader evaluates built-in animations (`FadeIn`, `FadeOut`, `Slide`, `ScalePulse`, `DriftOut` with one easing, `Tween`), `ProgressCurve` knots, and `ShaderMotion` directly on the GPU. Each instance carries its own duration and pivot while sharing one shader.

Animation evaluation and channel-conflict checks use a `1e-10` s tolerance, so adjacent clips such as `0.1 + 0.2` and `0.3` meet cleanly without false conflicts.

For standard ASS export, enable `scene.ass.compile(native_tweens=True)` so eligible linear or eased `ScalePulse`, `DriftOut` and `Tween` clips emit compact native transforms on the 10 ms ASS grid. See [Export standard ASS](../output/ass.md) and [Play and render a Hook](../output/hook.md) for full backend rules and limits.

## Next steps

- Compose hierarchies and copies in [Scene objects and groups](objects.md).
- Emit particles and follow moving targets in [Particles, copies and echoes](particles.md).
- Build an animated effect step by step in [Write a custom animation](../tutorials/custom-animation.md).
- Study eight complete choreography patterns in [Motion studies](../tutorials/lyric-studies.md).
