"""Runtime-importable structural types shared with the native extension stubs."""

type Point = tuple[float, float]
type Outline = tuple[tuple[Point, ...], bytes, Point, tuple[str, str, int]]
# x, y, width, height, ASS image type, RRGGBBAA (inverted alpha), packed coverage.
type RasterImage = tuple[int, int, int, int, int, int, bytes]
