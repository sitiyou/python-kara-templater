"""Round shader strokes on the shaped glyph's contour in local coordinates."""

from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from math import ceil, floor

from .geometry import VectorPath
from .paint_fields import ShaderPaint
from .path_geometry import flatten, path_bounds

_CELL = 16
_SOURCE = """
    ivec2 cell=ivec2(floor((local-pairAt(data))/16.));
    int bucket=data+refAt(data+4+cell.y*refAt(data+2)+cell.x);
    int count=refAt(bucket);
    float nearest=pen+1.;
    for(int j=0;j<count;j++) {
        int line=data+refAt(bucket+1+j);
        vec2 delta=local-pairAt(line), direction=pairAt(line+2);
        float t=clamp(dot(delta,direction)/dot(direction,direction),0.,1.);
        nearest=min(nearest,length(delta-t*direction));
    }
    coverage=clamp(0.5+pen-nearest,0.,1.);
"""


@dataclass(frozen=True)
class ContourStroke(ShaderPaint):
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)


@lru_cache(maxsize=512)
def contour_stroke(path: VectorPath, radius: float) -> ContourStroke:
    bounds, data = contour_grid(path, radius + 1)
    return ContourStroke(_SOURCE, data, bounds=bounds)


def contour_grid(
    path: VectorPath, pad: float
) -> tuple[tuple[int, int, int, int], tuple[float, ...]]:
    """Index flattened contour segments by local pixel cells."""
    box = path_bounds(path)
    x, y = floor(box.left - pad), floor(box.top - pad)
    w, h = ceil(box.right + pad) - x, ceil(box.top + box.height + pad) - y
    cols, rows = ceil(w / _CELL), ceil(h / _CELL)
    buckets: list[list[int]] = [[] for _ in range(cols * rows)]
    data: list[float] = [x, y, cols, rows] + [0] * len(buckets)
    for contour in path.contours:
        for a, b in pairwise(flatten(contour, tolerance=0.125).points):
            if a == b:
                continue
            i = len(data)
            data.extend((a.x, a.y, b.x - a.x, b.y - a.y))
            for row in range(
                max(0, floor((min(a.y, b.y) - pad - y) / _CELL)),
                min(rows, floor((max(a.y, b.y) + pad - y) / _CELL) + 1),
            ):
                for col in range(
                    max(0, floor((min(a.x, b.x) - pad - x) / _CELL)),
                    min(cols, floor((max(a.x, b.x) + pad - x) / _CELL) + 1),
                ):
                    buckets[row * cols + col].append(i)
    for i, bucket in enumerate(buckets):
        data[4 + i] = len(data)
        data.extend((len(bucket), *bucket))
    return (x, y, w, h), tuple(data)
