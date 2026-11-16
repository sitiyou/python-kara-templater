"""Carry opacity ownership through a stack without revealing hidden layers.

The first plane contains intrinsic coverage. Subsequent planes contain the same
material weighted by enclosing opacity scopes. Occlusion and additive saturation
always use the first plane, so a uniform opacity factors out of the whole stack.
After finishing a scope, discard its coverage plane to enter the next scope.
"""

from ._raster import PositionedFrame, RasterBudget, RasterCanvas
from .raster_settings import OutputCapabilityError

type CoverageStack = tuple[PositionedFrame, ...]


def compose_stacks(
    stacks: tuple[CoverageStack, ...], *, additive: bool, budget: RasterBudget
) -> CoverageStack:
    if not stacks:
        return ()
    count = len(stacks[0])
    if not count or any(len(stack) != count for stack in stacks):
        raise ValueError("coverage stacks must have matching nonempty planes")
    for stack in stacks:
        x, y, frame = stack[0]
        if any(
            (px, py, image.width, image.height) != (x, y, frame.width, frame.height)
            for px, py, image in stack
        ):
            raise ValueError("coverage planes must share geometry")
    if (
        len(stacks) > budget.max_images
        or sum(stack[0][2].width * stack[0][2].height for stack in stacks)
        > budget.max_pixels
    ):
        raise OutputCapabilityError("raster coverage budget exceeded")
    left = min(stack[0][0] for stack in stacks)
    top = min(stack[0][1] for stack in stacks)
    right = max(stack[0][0] + stack[0][2].width for stack in stacks)
    bottom = max(stack[0][1] + stack[0][2].height for stack in stacks)
    canvases = tuple(
        RasterCanvas(right - left, bottom - top, budget=budget) for _ in range(count)
    )
    for stack in stacks:
        x, y, coverage = stack[0]
        for row in range(coverage.height):
            for column in range(coverage.width):
                src = (row * coverage.width + column) * 4
                dst = ((y - top + row) * (right - left) + x - left + column) * 4
                inverse = 1 if additive else 1 - coverage.rgba[src + 3] / 255
                for canvas, (_, _, frame) in zip(canvases, stack, strict=True):
                    alpha = frame.rgba[src + 3] / 255
                    for channel in range(3):
                        canvas.channels[dst + channel] = (
                            frame.rgba[src + channel] / 255 * alpha
                            + canvas.channels[dst + channel] * inverse
                        )
                    canvas.channels[dst + 3] = (
                        alpha + canvas.channels[dst + 3] * inverse
                    )
    if additive:
        for offset in range(0, len(canvases[0].channels), 4):
            normalization = max(1, canvases[0].channels[offset + 3])
            for canvas in canvases:
                for channel in range(4):
                    canvas.channels[offset + channel] /= normalization
    return tuple((left, top, canvas.finish()) for canvas in canvases)
