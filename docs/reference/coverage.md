# Coverage and raster output

Explicit coverage/material and whole-group RGBA output. These retain distinct composition semantics and require deliberate resource limits. See [materials](../guides/materials.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Coverage](#coverage)
- [CoveragePartition](#coveragepartition)
- [GlowFunction](#glowfunction)
- [OutputCapabilityError](#outputcapabilityerror)
- [RasterEstimate](#rasterestimate)
- [RasterSettings](#rastersettings)
- [ScopeOpacity](#scopeopacity)

## Coverage

Explicit pre-blur material composition for a visual group.

Attach to ObjectGroup.coverage (including LyricLine) and compile the normal
Scene. Ordinary drawing groups retain per-layer alpha; this strategy closes
component/group alpha scopes after composing coverage. Sampling and spatial
approximation are explicit and bounded, never selected automatically.
Ordinary ancestors retain their transforms, masks, opacity and clocks; their
other children remain separate drawing contributions. Geometry references use
the shared Scene context. Nested Coverage declarations and opacity references
require explicit ownership and are rejected.

[Source](../../kara_templater/coverage_animation.py#L27)

```python
Coverage(
    *,
    components: tuple[str, ...] = (),
    glows: Mapping[str, Glow | GlowFunction] = _HAS_DEFAULT_FACTORY_CLASS(),
    glow_materials: Mapping[str, PaintField] = _HAS_DEFAULT_FACTORY_CLASS(),
    partitions: Mapping[str, CoveragePartition] = _HAS_DEFAULT_FACTORY_CLASS(),
    scope_opacities: Mapping[str, tuple[ScopeOpacity, ...]] = _HAS_DEFAULT_FACTORY_CLASS(),
    settings: RasterSettings = RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `components` | `tuple[str, ...]` | `()` |
| `glows` | `Mapping[str, Glow \| GlowFunction]` | `dict()` |
| `glow_materials` | `Mapping[str, PaintField]` | `dict()` |
| `partitions` | `Mapping[str, CoveragePartition]` | `dict()` |
| `scope_opacities` | `Mapping[str, tuple[ScopeOpacity, ...]]` | `dict()` |
| `settings` | `RasterSettings` | `RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128)` |

### Coverage.retarget

Retarget all material ownership when copying a visual tree.

```python
Coverage.retarget(
    names: Mapping[str, str],
) -> Coverage
```

## CoveragePartition

Fractional screen-x material ownership, applied before blur (not a clip).

Breakpoints are signed local seconds; compilation validates their absolute
times against the owning object's clock and display end.

[Source](../../kara_templater/coverage_animation.py#L249)

```python
CoveragePartition(
    function: Callable[[VisualState, float], tuple[Region, ...]],
    max_regions: int,
    inside: bool = True,
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float], tuple[Region, ...]]` | `required` |
| `max_regions` | `int` | `required` |
| `inside` | `bool` | `True` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### CoveragePartition.sample

Evaluate the declared region partition and enforce the configured maximum region count.

```python
CoveragePartition.sample(
    state: VisualState,
    time: float,
) -> tuple[Region, ...]
```

## GlowFunction

Pure world-state/local-seconds glow callback with declared spatial bounds.

None hides only the glow. Width/radius are script pixels: scaling them with
the source geometry is explicit in the callback. Breakpoints use the visual
leaf's local clock, just like its paint field and path animation. Signed
local intervals are validated against Scene zero and the leaf's display end.
required_interval optionally declares authored local time that lyric layout
must preserve; it is not inferred from sampling breakpoints. from_animation
supplies the animation interval automatically.

[Source](../../kara_templater/coverage_animation.py#L73)

```python
GlowFunction(
    function: Callable[[VisualState, float], Glow | None],
    max_blur: float,
    max_border: float,
    breakpoints: tuple[float, ...] = (),
    required_interval: TimeSpan | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float], Glow \| None]` | `required` |
| `max_blur` | `float` | `required` |
| `max_border` | `float` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |
| `required_interval` | `TimeSpan \| None` | `None` |

### GlowFunction.from_animation

Use a common paint animation as a local-seconds glow field.

fill maps to glow color; blur, border and opacity map directly. Other
channels are rejected. Sequences default to their authored duration;
other animations need duration. Before start and after a released clip,
base is returned. This field does not extend the owning leaf's lifetime.

Linear Tween targets and nested sequences infer conservative spatial
maxima without sampling callbacks. Custom spatial animations/rates need
explicit bounds, checked at every sample. Values are script pixels and
do not implicitly scale with the drawing's world transform.

```python
GlowFunction.from_animation(
    animation: StateAnimation,
    *,
    base: Glow = Glow(color=Color(red=255, green=255, blue=255), blur=0, border=0, opacity=1),
    duration: float | None = None,
    start: float = 0,
    hold: bool = True,
    max_blur: float | None = None,
    max_border: float | None = None,
) -> GlowFunction
```

### GlowFunction.sample

Evaluate a glow field while enforcing its declared blur and border bounds.

```python
GlowFunction.sample(
    state: VisualState,
    time: float,
) -> Glow | None
```

## OutputCapabilityError

An output failure with optional source and absolute-time context.

[Source](../../kara_templater/raster_settings.py#L10)

```python
OutputCapabilityError(
    message: str,
    *,
    origin: EventOrigin | None = None,
    time_ms: float | None = None,
)
```

## RasterEstimate

Preflight raster frames, target samples, canvas pixels, per-frame event limit, and declared spatial channel error.

Final encoded output is checked separately.

[Source](../../kara_templater/raster_settings.py#L67)

```python
RasterEstimate(
    frames: int,
    target_samples: int,
    canvas_pixels: int,
    frame_event_limit: int,
    max_channel_error: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `frames` | `int` | `required` |
| `target_samples` | `int` | `required` |
| `canvas_pixels` | `int` | `required` |
| `frame_event_limit` | `int` | `required` |
| `max_channel_error` | `int` | `0` |

## RasterSettings

Explicit limits for coverage/raster work, cached masks, frames, rectangles, output size, and spatial channel approximation.

max_channel_error is in 0 through 255; temporal sampling is separate.

[Source](../../kara_templater/raster_settings.py#L30)

```python
RasterSettings(
    *,
    max_channel_error: int = 0,
    max_pixels: int = 4000000,
    max_images: int = 50000,
    max_frame_events: int = 50000,
    max_rectangles: int = 200000,
    max_frame_chars: int = 8000000,
    max_output_chars: int = 64000000,
    max_frames: int = 1000,
    max_cached_masks: int = 128,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `max_channel_error` | `int` | `0` |
| `max_pixels` | `int` | `4000000` |
| `max_images` | `int` | `50000` |
| `max_frame_events` | `int` | `50000` |
| `max_rectangles` | `int` | `200000` |
| `max_frame_chars` | `int` | `8000000` |
| `max_output_chars` | `int` | `64000000` |
| `max_frames` | `int` | `1000` |
| `max_cached_masks` | `int` | `128` |

## ScopeOpacity

A leaf contribution's extra alpha at a named leaf or ancestor scope.

The pure callback receives signed seconds from the owner's clock origin.
Breakpoints must lie between Scene zero and the owner's display end. Its factor is
multiplied by that owner's normal state opacity, without changing geometry
evaluation or material callbacks. Copying needs an explicit owner remap.

[Source](../../kara_templater/coverage_animation.py#L218)

```python
ScopeOpacity(
    owner: str,
    function: Callable[[float], float],
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `owner` | `str` | `required` |
| `function` | `Callable[[float], float]` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### ScopeOpacity.sample

Evaluate scope opacity at seconds time and validate the 0 through 1 result.

```python
ScopeOpacity.sample(
    time: float,
) -> float
```
