"""Assign material to coverage before applying the preview blur kernel."""

from dataclasses import dataclass
from itertools import pairwise
from math import floor

from . import _ass_preview
from ._raster import RasterBudget, RasterFrame
from .composition import Color
from .timeline import Region, _finite


@dataclass(frozen=True)
class CoverageMask:
    left: int
    top: int
    width: int
    height: int
    data: bytes

    def __post_init__(self) -> None:
        if (
            any(
                type(v) is not int
                for v in (self.left, self.top, self.width, self.height)
            )
            or min(self.width, self.height) < 1
            or len(self.data) != self.width * self.height
        ):
            raise ValueError("coverage dimensions must match its packed buffer")
        if not isinstance(self.data, bytes):
            raise TypeError("coverage must be immutable bytes")


@dataclass(frozen=True)
class MaterialBand:
    region: Region
    color: Color
    opacity: float = 1

    def __post_init__(self) -> None:
        _finite(self.opacity, "material opacity")
        if not 0 <= self.opacity <= 1:
            raise ValueError("material opacity must be in 0..1")


_DEFAULT_BUDGET = RasterBudget()


def paint_coverage(
    mask: CoverageMask,
    bands: tuple[MaterialBand, ...],
    *,
    blur_radius: float = 0,
    budget: RasterBudget = _DEFAULT_BUDGET,
) -> tuple[int, int, RasterFrame]:
    """Color a complete, nonoverlapping horizontal material partition.

    Pixel coverage is partitioned by the fractional horizontal overlap of bands.
    Four premultiplied 8-bit planes are then filtered with the same Gaussian blur.
    Alpha is blurred once, independently of the number of material regions.
    Returned offsets include the filter's exact finite working-region expansion.
    """
    budget.check_pixels(mask.width, mask.height)
    _finite(blur_radius, "blur radius")
    if not 0 <= blur_radius <= 100:
        raise ValueError("blur radius must be in 0..100 ASS pixels")
    if len(bands) > budget.max_images:
        raise ValueError("material band budget exceeded")
    ordered = sorted(bands, key=lambda band: band.region.left)
    if (
        not ordered
        or ordered[0].region.left > mask.left
        or ordered[-1].region.right < mask.left + mask.width
        or any(a.region.right != b.region.left for a, b in pairwise(ordered))
    ):
        raise ValueError("material bands must partition the complete mask width")
    columns: list[tuple[float, float, float, float]] = []
    current_band = 0
    for x in range(mask.left, mask.left + mask.width):
        while current_band < len(ordered) and ordered[current_band].region.right <= x:
            current_band += 1
        red = green = blue = alpha = 0.0
        index = current_band
        while index < len(ordered) and ordered[index].region.left < x + 1:
            band = ordered[index]
            index += 1
            fraction = (
                max(0, min(x + 1, band.region.right) - max(x, band.region.left))
                * band.opacity
            )
            red += band.color.red * fraction
            green += band.color.green * fraction
            blue += band.color.blue * fraction
            alpha += 255 * fraction
        columns.append((red / 255, green / 255, blue / 255, alpha / 255))
    planes = tuple(
        bytes(
            min(255, floor(value * columns[index % mask.width][channel] + 0.5))
            for index, value in enumerate(mask.data)
        )
        for channel in range(4)
    )
    left = top = 0
    width, height = mask.width, mask.height
    if blur_radius:
        results = tuple(
            _ass_preview.blur_mask(plane, width, height, blur_radius, budget.max_pixels)
            for plane in planes
        )
        left, top, width, height, _ = results[0]
        assert all(result[:4] == (left, top, width, height) for result in results)
        planes = tuple(result[4] for result in results)
    rgba = bytearray(width * height * 4)
    for index, alpha in enumerate(planes[3]):
        if alpha:
            for channel in range(3):
                rgba[index * 4 + channel] = min(
                    255, floor(planes[channel][index] * 255 / alpha + 0.5)
                )
            rgba[index * 4 + 3] = alpha
    return mask.left + left, mask.top + top, RasterFrame(width, height, bytes(rgba))


def blur_frame(
    frame: RasterFrame, radius: float, *, budget: RasterBudget = _DEFAULT_BUDGET
) -> tuple[int, int, RasterFrame]:
    if not radius:
        return 0, 0, frame
    budget.check_pixels(frame.width, frame.height)
    planes = tuple(
        bytes(
            floor(frame.rgba[index + channel] * frame.rgba[index + 3] / 255 + 0.5)
            for index in range(0, len(frame.rgba), 4)
        )
        for channel in range(3)
    ) + (frame.rgba[3::4],)
    results = tuple(
        _ass_preview.blur_mask(plane, frame.width, frame.height, radius, budget.max_pixels)
        for plane in planes
    )
    left, top, width, height, alpha = results[3]
    rgba = bytearray(width * height * 4)
    for index, value in enumerate(alpha):
        if value:
            for channel in range(3):
                rgba[index * 4 + channel] = min(
                    255, floor(results[channel][4][index] * 255 / value + 0.5)
                )
            rgba[index * 4 + 3] = value
    return left, top, RasterFrame(width, height, bytes(rgba))
