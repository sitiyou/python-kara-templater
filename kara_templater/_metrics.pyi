"""Types for the native libass metrics extension (native/metrics.cpp)."""

from ._native_types import Outline as Outline
from ._native_types import Point as Point
from ._native_types import RasterImage as RasterImage

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


def rasterize(
    script: str,
    time_ms: int,
    width: int,
    height: int,
    max_pixels: int,
    max_images: int,
    /,
) -> list[RasterImage]: ...

# Returned left/top offsets include the expanded finite blur working region.
def blur_mask(
    data: bytes,
    width: int,
    height: int,
    radius: float,
    max_pixels: int,
    /,
) -> tuple[int, int, int, int, bytes]: ...
def blur_padding(radius: float) -> int: ...
