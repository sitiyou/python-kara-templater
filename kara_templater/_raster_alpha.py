"""Encode a known continuous opacity curve on composited ASS pixels."""

import re
from itertools import pairwise
from math import floor


def apply_opacity(
    text: str, start_ms: int, curve: tuple[tuple[int, float], ...]
) -> str:
    original = re.search(r"\\alpha&H([0-9A-F]{2})&", text)
    if original is None:
        raise ValueError("raster event has no encoded alpha")
    coverage = 255 - int(original[1], 16)

    def alpha(value: float) -> str:
        # Match RasterCanvas rounding: quantize coverage before inverting alpha.
        return f"&H{255 - floor(coverage * value + 0.5):02X}&"

    initial = curve[0][1]
    transforms = ""
    for (start, before), (end, after) in pairwise(curve):
        if end <= start_ms:
            # Discard completed segments. Besides saving bytes, this avoids
            # ASS interpreting a relative t2=0 as the new event's duration.
            initial = after
        elif before != after:
            transforms += (
                rf"\t({start - start_ms},{end - start_ms},1,\alpha{alpha(after)})"
            )
    tags = rf"\alpha{alpha(initial)}" + transforms
    return text[: original.start()] + tags + text[original.end() :]
