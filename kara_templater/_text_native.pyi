"""Types for the native text metrics extension (native/metrics.cpp)."""

from ._native_types import Outline as Outline
from ._native_types import Point as Point

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
    palt: bool = False,
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
    palt: bool = False,
    /,
) -> tuple[float, float, float, float, list[Outline]]: ...
def add_font(name: str, data: bytes, /) -> str: ...
