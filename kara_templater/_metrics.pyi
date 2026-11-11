"""Types for the native libass metrics extension (native/metrics.cpp)."""

type Point = tuple[float, float]
type Outline = tuple[tuple[Point, ...], bytes, Point, tuple[str, str, int]]

def text_extents(
    font: str,
    size: float,
    bold: int,
    italic: int,
    scale_x: float,
    scale_y: float,
    spacing: float,
    encoding: int,
    text: str,
    placement_x: float = 0,
    /,
) -> tuple[float, float, float, float]: ...
def text_shape(
    font: str,
    size: float,
    bold: int,
    italic: int,
    scale_x: float,
    scale_y: float,
    spacing: float,
    encoding: int,
    text: str,
    placement_x: float = 0,
    /,
) -> tuple[float, float, float, float, list[Outline]]: ...
def add_font(name: str, data: bytes, /) -> str: ...
