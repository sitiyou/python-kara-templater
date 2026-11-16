"""Geometry-independent pre-blur materials and coverage-owned composition."""

from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Literal

from ._coverage_stack import CoverageStack, compose_stacks
from ._material_raster import CoverageMask, MaterialBand, blur_frame, paint_coverage
from ._raster import PositionedFrame, RasterBudget, RasterFrame, compose_frames
from .geometry import finite
from .timeline import Region


@dataclass(frozen=True)
class MaterialLayer:
    """A coverage mask, its complete color partition and enclosing alpha weights.

    The first weight is intrinsic coverage (1). Further weights carry the same
    material through opacity scopes without allowing hidden layers to show.
    Geometry producers define these scopes; this compositor has no lyric model.
    """

    mask: CoverageMask
    bands: tuple[MaterialBand, ...]
    weights: tuple[float, ...] = (1,)
    blur_radius: float = 0
    axis: Literal["x", "y"] = "x"

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y"):
            raise ValueError("material axis must be x or y")
        finite(self.blur_radius, *self.weights)
        if not 0 <= self.blur_radius <= 100:
            raise ValueError("material blur radius must be in 0..100 ASS pixels")
        if (
            not self.weights
            or self.weights[0] != 1
            or any(not 0 <= value <= 1 for value in self.weights)
        ):
            raise ValueError(
                "material weights need intrinsic coverage followed by opacities"
            )

    def paint(self, *, budget: RasterBudget) -> CoverageStack:
        mask = self.mask
        if self.axis == "y":
            budget.check_pixels(mask.width, mask.height)
            mask = CoverageMask(
                mask.top,
                mask.left,
                mask.height,
                mask.width,
                bytes(
                    mask.data[y * mask.width + x]
                    for x in range(mask.width)
                    for y in range(mask.height)
                ),
            )
        planes = tuple(
            paint_coverage(
                mask,
                tuple(
                    replace(band, opacity=band.opacity * weight) for band in self.bands
                ),
                budget=budget,
            )
            for weight in self.weights
        )
        if self.axis == "x":
            return planes
        return tuple(
            (
                top,
                left,
                RasterFrame(
                    image.height,
                    image.width,
                    bytes(
                        image.rgba[(y * image.width + x) * 4 + channel]
                        for x in range(image.width)
                        for y in range(image.height)
                        for channel in range(4)
                    ),
                ),
            )
            for left, top, image in planes
        )


def _join_partitions(layers: tuple[MaterialLayer, ...]) -> tuple[MaterialLayer, ...]:
    """Quantize disjoint materials on identical coverage once, not per fragment."""
    groups: dict[
        tuple[CoverageMask, tuple[float, ...], float, str], list[MaterialLayer]
    ] = {}
    for layer in layers:
        key = (layer.mask, layer.weights, layer.blur_radius, layer.axis)
        groups.setdefault(key, []).append(layer)
    result: list[MaterialLayer] = []
    for group in groups.values():
        first = group[0]
        start = first.mask.left if first.axis == "x" else first.mask.top
        end = start + (first.mask.width if first.axis == "x" else first.mask.height)
        # Preserve paint_coverage's validation of malformed input partitions.
        if len(group) == 1 or any(
            not layer.bands
            or layer.bands[0].region.left != start
            or layer.bands[-1].region.right != end
            or any(a.region.right != b.region.left for a, b in pairwise(layer.bands))
            for layer in group
        ):
            result.extend(group)
            continue
        bands = sorted(
            (band for layer in group for band in layer.bands if band.opacity),
            key=lambda band: band.region.left,
        )
        if not bands or any(a.region.right > b.region.left for a, b in pairwise(bands)):
            result.extend(group)
            continue
        joined: list[MaterialBand] = []
        cursor = start
        for band in bands:
            if cursor < band.region.left:
                joined.append(
                    MaterialBand(Region(cursor, band.region.left), band.color, 0)
                )
            if (
                joined
                and joined[-1].region.right == band.region.left
                and (joined[-1].color, joined[-1].opacity) == (band.color, band.opacity)
            ):
                joined[-1] = replace(
                    band, region=Region(joined[-1].region.left, band.region.right)
                )
            else:
                joined.append(band)
            cursor = band.region.right
        if cursor < end:
            joined.append(MaterialBand(Region(cursor, end), bands[-1].color, 0))
        result.append(replace(first, bands=tuple(joined)))
    return tuple(result)


def compose_material_layers(
    *,
    fills: tuple[MaterialLayer, ...] = (),
    strokes: tuple[MaterialLayer, ...] = (),
    glows: tuple[MaterialLayer, ...] = (),
    budget: RasterBudget,
) -> CoverageStack:
    """Partition → combine equal-radius glow → blur → stroke → fill.

    Contributions within each role are additive and normalized using intrinsic
    coverage; roles occlude in the order above. The caller closes opacity scopes
    by discarding their leading planes after composition. With one plane, use
    the established RGBA fast path. No font, Track, time or output-event state
    is involved in this operation.
    """
    layers = (*fills, *strokes, *glows)
    if not layers:
        return ()
    count = len(layers[0].weights)
    if any(len(layer.weights) != count for layer in layers):
        raise ValueError("material layers must have matching opacity scopes")
    if any(layer.blur_radius for layer in (*fills, *strokes)):
        raise ValueError("fill and stroke blur must be expressed as a glow layer")
    if len(layers) > budget.max_images:
        raise ValueError("material layer budget exceeded")

    fills = _join_partitions(fills)
    strokes = _join_partitions(strokes)
    glows = _join_partitions(glows)

    def combine(parts: tuple[CoverageStack, ...], *, additive: bool) -> CoverageStack:
        if count > 1:
            return compose_stacks(parts, additive=additive, budget=budget)
        result = compose_frames(
            tuple(part[0] for part in parts), additive=additive, budget=budget
        )
        return () if result is None else (result,)

    glow_groups: dict[float, list[CoverageStack]] = {}
    for layer in glows:
        glow_groups.setdefault(layer.blur_radius, []).append(layer.paint(budget=budget))
    blurred: list[CoverageStack] = []
    for radius, parts in glow_groups.items():
        combined = combine(tuple(parts), additive=True)
        planes: list[PositionedFrame] = []
        for left, top, pixels in combined:
            dx, dy, image = blur_frame(pixels, radius, budget=budget)
            planes.append((left + dx, top + dy, image))
        if planes:
            blurred.append(tuple(planes))
    roles = tuple(
        part
        for part in (
            combine(tuple(blurred), additive=True),
            combine(
                tuple(layer.paint(budget=budget) for layer in strokes), additive=True
            ),
            combine(
                tuple(layer.paint(budget=budget) for layer in fills), additive=True
            ),
        )
        if part
    )
    return combine(roles, additive=False)
