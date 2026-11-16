# Geometry and paths

Script-space geometry, masks, deformation, path layout, and authored writing/morphing. Complexity bounds and topology requirements are explicit. See [geometry](../guides/geometry.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Affine2D](#affine2d)
- [Contour](#contour)
- [CubicSegment](#cubicsegment)
- [GeometryAnimation](#geometryanimation)
- [GeometryError](#geometryerror)
- [LineSegment](#linesegment)
- [MorphPath](#morphpath)
- [MoveAlong](#movealong)
- [PathBooleanOperation](#pathbooleanoperation)
- [PathFunction](#pathfunction)
- [PathItem](#pathitem)
- [Polyline](#polyline)
- [TextOutline](#textoutline)
- [Vec2](#vec2)
- [VectorPath](#vectorpath)
- [WritePath](#writepath)
- [WritingStroke](#writingstroke)
- [flatten](#flatten)
- [intersect_convex](#intersect_convex)
- [layout_path](#layout_path)
- [merge_geometry](#merge_geometry)
- [morph](#morph)
- [outline_text](#outline_text)
- [path_boolean](#path_boolean)
- [path_bounds](#path_bounds)
- [resample_path](#resample_path)
- [stroke](#stroke)
- [text_to_path](#text_to_path)

## Affine2D

Screen-coordinate affine map; ``outer @ inner`` applies inner first.

[Source](../../kara_templater/geometry.py#L55)

```python
Affine2D(
    a: float = 1,
    b: float = 0,
    c: float = 0,
    d: float = 1,
    tx: float = 0,
    ty: float = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `a` | `float` | `1` |
| `b` | `float` | `0` |
| `c` | `float` | `0` |
| `d` | `float` | `1` |
| `tx` | `float` | `0` |
| `ty` | `float` | `0` |

### Affine2D.apply

Transform a local Vec2 by this affine matrix and return the resulting Vec2.

```python
Affine2D.apply(
    point: Vec2,
) -> Vec2
```

## Contour

An ordered contour of line/cubic segments with explicit closure.

Geometry algorithms validate connectivity and require suitable topology for each
operation.

[Source](../../kara_templater/geometry.py#L126)

```python
Contour(
    start: Vec2,
    segments: tuple[LineSegment | CubicSegment, ...],
    closed: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `Vec2` | `required` |
| `segments` | `tuple[LineSegment \| CubicSegment, ...]` | `required` |
| `closed` | `bool` | `True` |

### Contour.point

Parameter-uniform sampling, not an arc-length claim.

```python
Contour.point(
    progress: float,
) -> Vec2
```

## CubicSegment

A cubic Bezier segment defined by start, two control points, and end.

Evaluation and splitting use normalized path progress.

[Source](../../kara_templater/geometry.py#L101)

```python
CubicSegment(
    control1: Vec2,
    control2: Vec2,
    end: Vec2,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `control1` | `Vec2` | `required` |
| `control2` | `Vec2` | `required` |
| `end` | `Vec2` | `required` |

### CubicSegment.point

Evaluate this cubic segment at normalized progress.

```python
CubicSegment.point(
    start: Vec2,
    progress: float,
) -> Vec2
```

## GeometryAnimation

Protocol for pure path deformation at local seconds.

Declare breakpoints and max_points before evaluation for deterministic sampling
and preflight.

[Source](../../kara_templater/path_animation.py#L15)

### GeometryAnimation.breakpoints

Object-local seconds at which deformation has a declared boundary.

Type: `tuple[float, ...]`.

### GeometryAnimation.max_points

Declared path complexity bound used before sampling the geometry callback.

Type: `int`.

### GeometryAnimation.sample

Evaluate path deformation at object-local seconds; return None for an empty path when supported.

```python
GeometryAnimation.sample(
    base: VectorPath,
    time: float,
) -> VectorPath | None
```

## GeometryError

A geometric operation cannot satisfy its declared topology or budget.

[Source](../../kara_templater/path_geometry.py#L21)

Construction: `GeometryError(*args)` using the inherited exception constructor.

## LineSegment

A straight path segment from start to end.

Coordinates are in the containing path space.

[Source](../../kara_templater/geometry.py#L87)

```python
LineSegment(
    end: Vec2,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `end` | `Vec2` | `required` |

### LineSegment.point

Interpolate between segment endpoints at normalized progress.

```python
LineSegment.point(
    start: Vec2,
    progress: float,
) -> Vec2
```

## MorphPath

Interpolate a path toward an explicitly corresponding target over local seconds.

Contours and segment topology must match; shape correspondence is not inferred.

[Source](../../kara_templater/path_animation.py#L61)

```python
MorphPath(
    target: VectorPath,
    start: float = 0,
    duration: float = 1,
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `VectorPath` | `required` |
| `start` | `float` | `0` |
| `duration` | `float` | `1` |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### MorphPath.breakpoints

Local start and completion times used to split geometry sampling.

Type: `tuple[float, ...]`.

### MorphPath.max_points

Declared point bound of the corresponding source/target interpolation.

Type: `int`.

### MorphPath.sample

Evaluate corresponding path interpolation at local seconds, retaining endpoint geometry outside the morph interval.

```python
MorphPath.sample(
    base: VectorPath,
    time: float,
) -> VectorPath
```

## MoveAlong

Offset the captured position by a path; optionally follow its tangent.

Contour uses its curve parameter. Polyline uses its approximate arc length.
The rate function chooses progress, which is clamped to the path endpoints.

[Source](../../kara_templater/path_motion.py#L12)

```python
MoveAlong(
    path: Contour | Polyline,
    rate: Callable[[float], float] = linear_rate,
    orient: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `path` | `Contour \| Polyline` | `required` |
| `rate` | `Callable[[float], float]` | `linear_rate` |
| `orient` | `bool` | `False` |

### MoveAlong.channels

The position and optional rotation channels written by this motion.

Type: `frozenset[Channel]`.

### MoveAlong.native_linear

Whether the declared path and rate support the compiler native linear-motion strategy.

Type: `bool`.

### MoveAlong.sample

Evaluate path position and optional tangent orientation at normalized progress.

```python
MoveAlong.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## PathBooleanOperation

Public type alias:

```python
type PathBooleanOperation = Literal['intersection', 'union', 'difference', 'xor']
```

## PathFunction

Author callback receives seconds relative to the clock origin; None is invisible.

Breakpoints may be negative local seconds; the owning object validates their
absolute times. This supports visibility extended before an existing clock.

[Source](../../kara_templater/path_animation.py#L37)

```python
PathFunction(
    function: Callable[[VectorPath, float], VectorPath | None],
    max_points: int,
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VectorPath, float], VectorPath \| None]` | `required` |
| `max_points` | `int` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### PathFunction.sample

Evaluate the custom path callback at local seconds and enforce its declared point bound.

```python
PathFunction.sample(
    base: VectorPath,
    time: float,
) -> VectorPath | None
```

## PathItem

A Scene object with explicit layout advance and local anchor for placement along a path.

Advance is in script pixels.

[Source](../../kara_templater/path_layout.py#L13)

```python
PathItem(
    object: SceneObject,
    advance: float,
    anchor: Vec2 = Vec2(x=0, y=0),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `object` | `SceneObject` | `required` |
| `advance` | `float` | `required` |
| `anchor` | `Vec2` | `Vec2(x=0, y=0)` |

## Polyline

A finite sequence of points supporting cumulative distance, interpolation, prefixes, and resampling.

It is the explicit flattened representation used by path algorithms.

[Source](../../kara_templater/path_geometry.py#L30)

```python
Polyline(
    points: tuple[Vec2, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `points` | `tuple[Vec2, ...]` | `required` |

### Polyline.distances

Cumulative flattened distance at every point, starting from zero.

Type: `tuple[float, ...]`.

### Polyline.length

The total cumulative length of the flattened point sequence.

Type: `float`.

### Polyline.point

Return the point at normalized distance along the polyline.

```python
Polyline.point(
    progress: float,
) -> Vec2
```

### Polyline.prefix

Return the polyline prefix through a normalized distance, including its interpolated final point.

```python
Polyline.prefix(
    progress: float,
) -> Polyline
```

### Polyline.resample

Return evenly spaced samples along the flattened path distance.

```python
Polyline.resample(
    count: int,
) -> Polyline
```

### Polyline.signed_area

Compute the signed polygon area of this point sequence.

Type: `float`.

## TextOutline

Measured text geometry with layout bounds and actual font faces.

path can be None for whitespace or empty ink; layout advance remains meaningful.

[Source](../../kara_templater/text_geometry.py#L13)

```python
TextOutline(
    path: VectorPath | None,
    layout_bounds: Box,
    fonts: tuple[FontFace, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `path` | `VectorPath \| None` | `required` |
| `layout_bounds` | `Box` | `required` |
| `fonts` | `tuple[FontFace, ...]` | `required` |

## Vec2

A finite two-dimensional vector used for script-space positions, offsets, and scales.

Vector operations return new values.

[Source](../../kara_templater/geometry.py#L15)

```python
Vec2(
    x: float = 0,
    y: float = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `x` | `float` | `0` |
| `y` | `float` | `0` |

### Vec2.length

The Euclidean vector magnitude.

Type: `float`.

### Vec2.lerp

Interpolate this vector toward another vector by the supplied fraction.

```python
Vec2.lerp(
    other: Vec2,
    progress: float,
) -> Vec2
```

### Vec2.rotated

Positive angles rotate clockwise in screen coordinates.

```python
Vec2.rotated(
    degrees: float,
) -> Vec2
```

## VectorPath

An immutable collection of contours for drawings, masks, glyph outlines, and motion paths.

Shape factories and transformations retain explicit geometry rather than player-
side callbacks.

[Source](../../kara_templater/geometry.py#L154)

```python
VectorPath(
    contours: tuple[Contour, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `contours` | `tuple[Contour, ...]` | `required` |

### VectorPath.circle

Four cubic arcs, centered at the origin (the usual circle approximation).

```python
VectorPath.circle(
    radius: float,
) -> VectorPath
```

### VectorPath.drawing

Standard ASS p1 path, preserving winding and all contours.

```python
VectorPath.drawing() -> str
```

### VectorPath.map

Apply a point function to all segment endpoints/control points and return a new path.

```python
VectorPath.map(
    transform: Callable[[Vec2], Vec2],
) -> VectorPath
```

### VectorPath.point_count

The contour control-point count used for geometry complexity budgets.

Type: `int`.

### VectorPath.polygon

Construct a closed polygon from ordered points.

```python
VectorPath.polygon(
    *points: Vec2,
) -> VectorPath
```

### VectorPath.rectangle

Construct a positive width/height rectangle starting at local (0, 0).

```python
VectorPath.rectangle(
    width: float,
    height: float,
) -> VectorPath
```

## WritePath

Ordered, author-supplied strokes. Font outlines do not imply writing order.

[Source](../../kara_templater/path_animation.py#L113)

```python
WritePath(
    strokes: tuple[WritingStroke, ...],
    width: float = 4,
    tolerance: float = 0.25,
    max_points: int = 4096,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `strokes` | `tuple[WritingStroke, ...]` | `required` |
| `width` | `float` | `4` |
| `tolerance` | `float` | `0.25` |
| `max_points` | `int` | `4096` |

### WritePath.breakpoints

The local stroke boundaries and explicit lift gaps needed for reveal sampling.

Type: `tuple[float, ...]`.

### WritePath.full_path

The complete stroked writing geometry after the final stroke finishes.

Type: `VectorPath`.

### WritePath.lines

The stroke contours flattened with the declared tolerance and point budget.

Type: `tuple[Polyline, ...]`.

### WritePath.pen_down

Whether the authored writing schedule has an active stroke at local seconds.

```python
WritePath.pen_down(
    time: float,
) -> bool
```

### WritePath.sample

Return the revealed stroke geometry at local seconds, including completed stroke prefixes.

```python
WritePath.sample(
    base: VectorPath,
    time: float,
) -> VectorPath | None
```

### WritePath.tip

During a pen-up pause, hold at the preceding stroke's endpoint.

```python
WritePath.tip(
    time: float,
) -> Vec2
```

## WritingStroke

An authored contour with local start and positive duration in seconds.

WritePath uses these stroke clocks for progressive reveal and lift gaps.

[Source](../../kara_templater/path_animation.py#L94)

```python
WritingStroke(
    path: Contour,
    start: float,
    duration: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `path` | `Contour` | `required` |
| `start` | `float` | `required` |
| `duration` | `float` | `required` |

## flatten

Adaptive de Casteljau subdivision; tolerance is in local path units.

Flatness bounds the control polygon's distance to its chord. This is not
an arc-length error bound, and later object scaling magnifies the distance.

[Source](../../kara_templater/path_geometry.py#L97)

```python
flatten(
    contour: Contour,
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
) -> Polyline
```

## intersect_convex

Intersect filled contours with a convex polygon, retaining hole winding.

Curves are flattened explicitly. This is a bounded intersection operation,
not a general union/difference engine for arbitrary self-intersecting paths.

[Source](../../kara_templater/path_geometry.py#L266)

```python
intersect_convex(
    path: VectorPath,
    boundary: tuple[Vec2, ...],
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
) -> VectorPath | None
```

## layout_path

Distribute advance centers over a curve interval, using local anchor groups.

Children retain their original coordinates, identity, lifetime, sources and
local animations. An annotation grouped with its base follows the same tangent
and parent transforms. The caller chooses spacing and the measured advance.

[Source](../../kara_templater/path_layout.py#L30)

```python
layout_path(
    items: Iterable[PathItem],
    path: Contour | Polyline,
    *,
    id: str = 'path-layout',
    start: float = 0,
    end: float = 1,
    orient: bool = True,
    position: Vec2 | None = None,
    max_items: int = 1000,
) -> ObjectGroup
```

## merge_geometry

Union child geometry, then paint one ordinary PathObject.

Child colors, opacity, border, blur and layer order do not participate in
this geometric operation. Root transforms, animations, opacity, clip and
reference are retained. Descendant clips/references require explicit prior
lowering and are rejected. This is not an offscreen alpha-composite group.

[Source](../../kara_templater/group_geometry.py#L17)

```python
merge_geometry(
    group: ObjectGroup,
    *,
    id: str | None = None,
    tolerance: float = 0.25,
    max_points: int = 4096,
    max_work: int = 1000000,
) -> PathObject
```

## morph

Interpolate explicitly paired contours and vertices, including hole winding.

This is not automatic glyph matching. Even valid endpoint correspondence can
self-intersect between endpoints; authors must preview their chosen mapping.

[Source](../../kara_templater/path_geometry.py#L233)

```python
morph(
    source: VectorPath,
    target: VectorPath,
    progress: float,
) -> VectorPath
```

## outline_text

Shape at the source font's nominal scale; object transforms stay independent.

[Source](../../kara_templater/text_geometry.py#L25)

```python
outline_text(
    node: TextObject,
    *,
    max_points: int = 4096,
) -> TextOutline
```

## path_boolean

Boolean closed filled paths under nonzero winding, including holes.

Curves flatten with the declared local tolerance. Polygon crossings split
the sweep into exact linear strips; shared vertices canonicalize at 1e-9
path units and collinear cleanup uses 1e-8. Output is stitched into actual
exterior/hole contours, so stroking does not reveal internal sweep strips.
max_points bounds combined flattened input and final output; scratch edges
are limited to 8*max_points. max_work bounds pair tests and sweep work.
None denotes empty area. Open contours are rejected.

[Source](../../kara_templater/path_boolean.py#L143)

```python
path_boolean(
    first: VectorPath,
    second: VectorPath,
    operation: PathBooleanOperation = 'intersection',
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
    max_work: int = 1000000,
) -> VectorPath | None
```

## path_bounds

Conservative control-point bounds, before appearance and transforms.

[Source](../../kara_templater/path_geometry.py#L335)

```python
path_bounds(
    path: VectorPath,
) -> Box
```

## resample_path

Explicit correspondence preparation; contour order and winding are retained.

[Source](../../kara_templater/path_geometry.py#L178)

```python
resample_path(
    path: VectorPath,
    points_per_contour: int,
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
) -> VectorPath
```

## stroke

Fill an open polyline with bevel joins and butt caps; empty length is invisible.

[Source](../../kara_templater/path_geometry.py#L150)

```python
stroke(
    line: Polyline,
    width: float,
    *,
    max_points: int = 4096,
) -> VectorPath | None
```

## text_to_path

Preserve source, state, lifetime and animations when replacing text by geometry.

[Source](../../kara_templater/text_geometry.py#L97)

```python
text_to_path(
    node: TextObject,
    *,
    id: str | None = None,
    max_points: int = 4096,
) -> PathObject
```
