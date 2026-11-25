# Shapes, clips and masks

Build vector shapes, extract and split text outlines, add extruded 3D-style sides, and clip drawings with static or animated masks. Use this guide when you need custom vector geometry or masking.

## Build shapes and convert text to paths

`VectorPath` stores contours made of `LineSegment` and `CubicSegment` curves. Create common shapes with `VectorPath.rectangle(w, h)`, `VectorPath.circle(r)` and `VectorPath.polygon(*points)`, then place them in a `Scene` with `PathObject`. Set `filled=False` for an outline-only stroke. Use `Vec2` and `Affine2D` for coordinate math.

Convert text to vector geometry when you need to split letters, merge silhouettes or swap in a custom glyph outline:

- `outline_text(node)` measures the font and returns a `TextOutline(path, layout_bounds, fonts)`. Whitespace has `path=None` while keeping a valid `layout_bounds`.
- `text_to_path(node, path=None)` converts a `TextObject` into a `PathObject` in the same local coordinates while preserving visibility, animations and clip clocks. Pass `path=` to draw a custom outline in script pixels; for a baseline-relative outline in em units, scale by the glyph's `em_size` and add its local `baseline` to every `y` coordinate.

Use the built-in geometry helpers to measure, arrange, cut and combine paths:

| Function | Purpose |
| --- | --- |
| `path_bounds(path)` | Returns conservative control-point bounds (`Box`) before transforms |
| `flatten(contour, tolerance=0.25)` | Converts a curved `Contour` into a `Polyline` |
| `resample_path(path, points_per_contour)` | Produces evenly sampled contours with matching topology |
| `layout_path(items, path, orient=True)` | Arranges `PathItem` objects along a curve with optional tangent rotation |
| `path_boolean(a, b, operation)` | Runs `"intersection"`, `"union"`, `"difference"` or `"xor"` under explicit point and work limits |
| `intersect_convex(path, boundary)` | Clips filled contours against a convex polygon while preserving holes |
| `split_path(source, columns=..., rows=...)` | Cuts a static filled `PathObject` into grid tiles or custom convex `cells=` polygons |
| `merge_geometry(group)` | Unions child shapes into one `PathObject` for a shared silhouette, outline or glow |

When shattering a shape with `split_path`, pass `cells=` as convex `Vec2` polygons in local coordinates for diagonal bands or shards. Keep the uncut object visible during holds so anti-aliased cut edges do not show seams.

## Extruded lettering and shapes

Attach an `Extrusion` to a `Track`, `TextObject` or `PathObject` to sweep a solid 3D-style side from the drawing's silhouette. `offset` points from the front face to the back in local script pixels.

```python
from kara_templater import (
    Color,
    Document,
    Extrusion,
    KaraokeEffects,
    Line,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=58, bold=True, outline=2, shadow=0),),
)
document.records.append(Line(start_time=500, end_time=2800, text=r"{\k60}Bold {\k170}depth"))

side = Extrusion(
    Vec2(6, 11),
    Color.hex("#CEDAD1"),
    back_color=Color.hex("#929F86"),
)
scene = build_lyric_scene(
    document,
    tracks=(Track(id="lead", extrusion=side, effects=(KaraokeEffects.duotone(),)),),
)
scene.export("extruded.hook")
```

Omit `back_color` for a flat single-colour side. Supplying `back_color` shades smoothly from `color` at the front face to `back_color` at full depth around every contour, including holes inside letters.

Key extrusion behaviour:

- Sweeps the filled silhouette and its hard primary border together (or only the stroke when `filled=False`).
- Moves, scales and fades together with the front face; within a layer, all extruded sides draw behind the faces.
- On a `Track`, applies to both body text and ruby while keeping karaoke wipe colours on the front face and leaving layout metrics unchanged.
- Supported in browser preview and playback shader export. Standard ASS compilation raises an error for extruded objects.

## Clip and mask drawings

Attach `RectangleClip` or `VectorClip` to any visual object to restrict where it draws:

- `space="screen"` (default) keeps the mask fixed in canvas coordinates while the object moves inside it.
- `space="local"` anchors the mask to the object so it moves and scales with the object's hierarchy.
- `inverse=False` (default) draws only inside the mask; `inverse=True` cuts a hole where the mask sits. An empty normal mask hides the object; an empty inverse mask reveals everything.

Animate a `RectangleClip` with `RectangleKeyframes` using `(local_seconds, (left, top, right, bottom))` pairs:

```python
from kara_templater import RectangleClip, RectangleKeyframes

mask = RectangleClip(
    0,
    0,
    100,
    40,
    deform=RectangleKeyframes((
        (0.0, (0, 0, 0, 40)),
        (1.0, (0, 0, 50, 40)),
        (1.5, (0, 0, 50, 40)),  # hold in place
        (2.0, (0, 0, 100, 40)),
    )),
)
```

Repeat identical bounds to pause, place two keys at the same timestamp for an instant reset, or use zero width or height for an empty mask. End values hold outside the key range.

For custom procedural bounds in `SceneEvaluator`, pass `RectangleFunction(function, breakpoints=())` returning `(left, top, right, bottom)` or `None`.

### Group masks and backend support

For shader rendering, a normal screen-space `RectangleClip` (static or `RectangleKeyframes`) on an `ObjectGroup` intersects the clip of every descendant drawing, including lyric colour layers and extrusion sides. The group's keyframes run on the group's own clock while each child keeps its own clip coordinates and clock.

> [!NOTE]
> The scene shader supports normal screen-space and local `RectangleClip` masks, `RectangleKeyframes`, and screen-space group rectangles. `VectorClip`, `inverse=True`, group-local clips and `RectangleFunction` callbacks are not supported by Hook export; see [Play and render a Hook](../output/hook.md) and [Export standard ASS](../output/ass.md) for backend details.

## Path trails, writing and morphing

Attach a `GeometryAnimation` to `PathObject.deform` (or `VectorClip.deform`) to reshape a path over local seconds:

- **`TrailPath`**: Reveals a moving arc-length slice of a `Contour` or `Polyline`, extending at its head over `duration` and retracting behind a tail delayed by `lag`.

```python
from kara_templater import (
    Contour,
    CubicSegment,
    Lifetime,
    PathObject,
    TrailPath,
    Vec2,
)

trail = TrailPath(
    Contour(
        Vec2(),
        (CubicSegment(Vec2(10, -60), Vec2(60, -40), Vec2(80, 0)),),
        closed=False,
    ),
    duration=0.6,
    lag=0.2,
    width=2,
)
strand = PathObject(
    id="strand",
    lifetime=Lifetime(1.0, 1.8),
    path=trail.full_path,
    deform=trail,
)
```

Here the head travels from local `0.0` s to `0.6` s and the tail follows from `0.2` s to `0.8` s; outside that window the path is empty. Pass `trail.line` to `MoveAlong` to move another object along the exact same arc-length curve, call `trail.tip(time)` for the head position, or call `Polyline.slice(start, end)` directly. Strokes use bevel joins and butt caps.

- **`WritePath` and `WritingStroke(path, start, duration)`**: Progressively reveals author-supplied pen strokes in order (stroke order is never inferred from a font). Read `pen_down(time)` and `tip(time)` to drive a separate pen object, including lift gaps.
- **`MorphPath` and `morph(source, target, progress)`**: Interpolates matching contours and vertices between two paths. Prepare compatible topology with `resample_path` first; shape correspondence is always explicit.
- **`PathFunction(function, max_points, breakpoints=())`**: Evaluates a custom `(base_path, local_seconds) -> VectorPath | None` callback under an explicit point budget.

> [!WARNING]
> Per-frame deformed path geometry (`TrailPath`, `WritePath`, `MorphPath`, `PathFunction`) is evaluated in `SceneEvaluator` and is unsupported in shader and standard ASS exports.

## Next steps

- Compose `PathObject` drawings inside groups in [Scene objects and groups](objects.md).
- Use path geometry in custom particles in [Particles, copies and echoes](particles.md).
- Check shader clip and atlas limits in [Play and render a Hook](../output/hook.md).
- Browse every geometry signature in [Geometry API reference](../reference/geometry.md).
