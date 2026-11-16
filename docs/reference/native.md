# Regions and progress curves

Horizontal regions, normalized progress curves, and millisecond input display windows. HighlightPass and Scene animation clocks use seconds. Output goes through the common Scene compiler.

[All public symbols](README.md#symbol-index)

## Contents

- [DisplayWindow](#displaywindow)
- [ProgressCurve](#progresscurve)
- [Region](#region)
- [union_regions](#union_regions)

## DisplayWindow

An absolute millisecond visibility interval independent of source singing time.

Animation padding changes this window rather than lyric segment clocks.

[Source](../../kara_templater/timeline.py#L28)

```python
DisplayWindow(
    start_ms: int,
    end_ms: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `int` | `required` |
| `end_ms` | `int` | `required` |

## ProgressCurve

Monotone piecewise linear (normalized time, progress) knots.

Repeated progress values represent pauses. Repeated times are forbidden;
instantaneous singing is represented by a zero-duration HighlightPass.

[Source](../../kara_templater/timeline.py#L73)

```python
ProgressCurve(
    knots: tuple[tuple[float, float], ...] = ((0, 0), (1, 1)),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `knots` | `tuple[tuple[float, float], ...]` | `((0, 0), (1, 1))` |

### ProgressCurve.arrival

Earliest normalized time reaching progress, including plateau starts.

```python
ProgressCurve.arrival(
    progress: float,
) -> float
```

### ProgressCurve.at

Evaluate normalized sweep progress from this piecewise-linear curve.

```python
ProgressCurve.at(
    time_fraction: float,
) -> float
```

### ProgressCurve.two_stage

Construct a piecewise-linear progress curve through one explicit time/progress breakpoint.

```python
ProgressCurve.two_stage(
    *,
    time_fraction: float,
    progress_fraction: float,
) -> Self
```

## Region

A horizontal interval in script pixels; an empty interval is valid.

[Source](../../kara_templater/timeline.py#L45)

```python
Region(
    left: float,
    right: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `left` | `float` | `required` |
| `right` | `float` | `required` |

### Region.at

Interpolate a position across the region using normalized progress.

```python
Region.at(
    progress: float,
) -> float
```

### Region.center

The midpoint of the horizontal region.

Type: `float`.

### Region.width

The horizontal region extent in script pixels.

Type: `float`.

## union_regions

Merge coverage without filling gaps or painting overlaps twice.

[Source](../../kara_templater/timeline.py#L129)

```python
union_regions(
    regions: Iterable[Region],
) -> tuple[Region, ...]
```
