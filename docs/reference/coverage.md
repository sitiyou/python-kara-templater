# Coverage and raster output

Explicit coverage/material and whole-group RGBA output. These retain distinct composition semantics and require deliberate resource limits. See [materials](../guides/materials.md).

[All public symbols](README.md#symbol-index)

## Contents

- [CoveragePartition](#coveragepartition)
- [CoverageResult](#coverageresult)
- [GlowFunction](#glowfunction)
- [PreparedTrackCoverage](#preparedtrackcoverage)
- [RasterEstimate](#rasterestimate)
- [RasterSettings](#rastersettings)
- [RasterizedGroup](#rasterizedgroup)
- [ScopeOpacity](#scopeopacity)
- [compile_coverage](#compile_coverage)
- [prepare_track_coverage](#prepare_track_coverage)
- [rasterize_group](#rasterize_group)

## CoveragePartition

Fractional screen-x material ownership, applied before blur (not a clip).

[Source](../../kara_templater/coverage_animation.py#L82)

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

## CoverageResult

Compiled output and the actual midpoint samples (absolute seconds).

max_channel_error bounds spatial color quantization only. Temporal motion
is held between samples; no continuous-time image error bound is implied.

[Source](../../kara_templater/coverage_output.py#L31)

```python
CoverageResult(
    output: SceneResult,
    sample_times: tuple[float, ...],
    max_channel_error: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `output` | `SceneResult` | `required` |
| `sample_times` | `tuple[float, ...]` | `required` |
| `max_channel_error` | `int` | `required` |

### CoverageResult.document

The standard ASS Document produced by coverage compilation.

Type: `Document`.

## GlowFunction

Pure world-state/local-seconds glow callback with declared spatial bounds.

None hides only the glow. Width/radius are script pixels: scaling them with
the source geometry is explicit in the callback. Breakpoints use the visual
leaf's birth clock, just like its paint field and path animation.

[Source](../../kara_templater/coverage_animation.py#L12)

```python
GlowFunction(
    function: Callable[[VisualState, float], Glow | None],
    max_blur: float,
    max_border: float,
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float], Glow \| None]` | `required` |
| `max_blur` | `float` | `required` |
| `max_border` | `float` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### GlowFunction.sample

Evaluate a glow field while enforcing its declared blur and border bounds.

```python
GlowFunction.sample(
    state: VisualState,
    time: float,
) -> Glow | None
```

## PreparedTrackCoverage

Editable group plus explicit material bindings and retained source data.

Use dataclasses.replace to edit group geometry, or modify binding dictionaries
before compiling. IDs identify material ownership: copying/renaming nodes
requires remapping bindings and ScopeOpacity owners. Preparation never
evaluates dynamic property functions; compile uses the shared coverage exit.

[Source](../../kara_templater/track_coverage.py#L26)

```python
PreparedTrackCoverage(
    document: Document,
    group: ObjectGroup,
    components: tuple[str, ...],
    glows: dict[str, Glow | GlowFunction],
    glow_materials: dict[str, PaintField],
    partitions: dict[str, CoveragePartition],
    scope_opacities: dict[str, tuple[ScopeOpacity, ...]],
    diagnostics: tuple[str, ...],
    owner: str,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `document` | `Document` | `required` |
| `group` | `ObjectGroup` | `required` |
| `components` | `tuple[str, ...]` | `required` |
| `glows` | `dict[str, Glow \| GlowFunction]` | `required` |
| `glow_materials` | `dict[str, PaintField]` | `required` |
| `partitions` | `dict[str, CoveragePartition]` | `required` |
| `scope_opacities` | `dict[str, tuple[ScopeOpacity, ...]]` | `required` |
| `diagnostics` | `tuple[str, ...]` | `required` |
| `owner` | `str` | `required` |

### PreparedTrackCoverage.compile

Compile the editable group and ID-keyed material bindings with explicit raster and Scene limits.

```python
PreparedTrackCoverage.compile(
    *,
    settings: RasterSettings = RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128),
    budget: SceneBudget = SceneBudget(fps=50, max_events=25000, max_bytes=10485760, max_active=1000, max_path_points=4096, max_bands=1024, max_boolean_work=1000000),
) -> CoverageResult
```

## RasterEstimate

Preflight raster frames, target samples, canvas pixels, per-frame event limit, and declared spatial channel error.

Final encoded output is checked separately.

[Source](../../kara_templater/raster_settings.py#L47)

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

[Source](../../kara_templater/raster_settings.py#L10)

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

## RasterizedGroup

Baked standard-ASS scene and its explicit sampling/quantization costs.

[Source](../../kara_templater/scene_raster.py#L28)

```python
RasterizedGroup(
    scene: Scene,
    sampled_frames: int,
    source_events: int,
    max_channel_error: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `scene` | `Scene` | `required` |
| `sampled_frames` | `int` | `required` |
| `source_events` | `int` | `required` |
| `max_channel_error` | `int` | `required` |

## ScopeOpacity

A leaf contribution's extra alpha at a named leaf or ancestor scope.

The pure callback receives seconds since the owner's birth. Its factor is
multiplied by that owner's normal state opacity, without changing geometry
evaluation or material callbacks. Copying needs an explicit owner remap.

[Source](../../kara_templater/coverage_animation.py#L50)

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

## compile_coverage

Compile one self-contained group without modifying its input Document.

Sources survive unless explicitly selected by record index. Recompiling with
the same owner replaces that owner's generated events. Fill, stroke and
explicit glow share coverage before blur; ordinary groups close alpha scopes.
Configuration keys are object identities and must be remapped when copying.
All output is standard ASS, sampled at script resolution and held on an ASS
centisecond grid. Declared discontinuities split that grid before callbacks.

[Source](../../kara_templater/coverage_output.py#L111)

```python
compile_coverage(
    document: Document,
    group: ObjectGroup,
    *,
    glows: Mapping[str, Glow | GlowFunction] | None = None,
    glow_materials: Mapping[str, PaintField] | None = None,
    components: Collection[str] = (),
    scope_opacities: Mapping[str, tuple[ScopeOpacity, ...]] | None = None,
    partitions: Mapping[str, CoveragePartition] | None = None,
    replace_records: Collection[int] = (),
    owner: str = 'coverage',
    settings: RasterSettings = RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128),
    budget: SceneBudget = SceneBudget(fps=50, max_events=25000, max_bytes=10485760, max_active=1000, max_path_points=4096, max_bands=1024, max_boolean_work=1000000),
) -> CoverageResult
```

## prepare_track_coverage

Prepare editable coverage components with shared karaoke ownership rules.

Bounds are final script pixels, including caller-added scale. Imported source
lines become retained comments; explicit items leave dialogue unchanged.
Unselected lines and other owners survive. Geometry/property/material binding
happens now, callbacks only at compile. Track.sampling is not used here.
Track sweep fronts currently require positive axis-aligned uniform scale;
custom two-dimensional sweep ownership is not inferred from an affine edit.

[Source](../../kara_templater/track_coverage.py#L67)

```python
prepare_track_coverage(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    tracks: tuple[Track | TrackGroup, ...],
    max_glow_blur: float,
    max_glow_border: float,
    owner: str = 'default',
    import_settings: ImportSettings | None = None,
    max_objects: int = 25000,
) -> PreparedTrackCoverage
```

## rasterize_group

Bake a group's already-lowered picture, then apply its root opacity once.

The viewport-clipped RGBA picture is blurred in premultiplied space before
root opacity is applied. Child and root masks act before this group blur;
offscreen content beyond the viewport cannot contribute to the blur.
Descendant opacity retains ordinary Scene semantics. The root must be
self-contained: external references are diagnosed by the Scene compiler.
Geometry first uses the Scene sampling strategy, then pixel frames are
sampled at the declared output grid. No tighter temporal error is claimed.

[Source](../../kara_templater/scene_raster.py#L38)

```python
rasterize_group(
    group: ObjectGroup,
    *,
    resolution: tuple[int, int],
    blur_radius: float = 0,
    settings: RasterSettings = RasterSettings(max_channel_error=0, max_pixels=4000000, max_images=50000, max_frame_events=50000, max_rectangles=200000, max_frame_chars=8000000, max_output_chars=64000000, max_frames=1000, max_cached_masks=128),
    budget: SceneBudget = SceneBudget(fps=50, max_events=25000, max_bytes=10485760, max_active=1000, max_path_points=4096, max_bands=1024, max_boolean_work=1000000),
) -> RasterizedGroup
```
