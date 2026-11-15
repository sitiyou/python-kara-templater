"""Explicit budgets for the pre-blur material output path."""

from dataclasses import dataclass
from typing import Protocol

from .ass import Line
from .sources import EventOrigin


@dataclass(frozen=True, kw_only=True)
class RasterSettings:
    """Explicit limits for coverage/raster work, cached masks, frames, rectangles, output size, and spatial channel approximation.

    max_channel_error is in 0 through 255; temporal sampling is separate.
    """

    max_channel_error: int = 0
    max_pixels: int = 4_000_000
    max_images: int = 50_000
    max_frame_events: int = 50_000
    max_rectangles: int = 200_000
    max_frame_chars: int = 8_000_000
    max_output_chars: int = 64_000_000
    max_frames: int = 1000
    max_cached_masks: int = 128

    def __post_init__(self) -> None:
        if (
            type(self.max_channel_error) is not int
            or not 0 <= self.max_channel_error <= 255
        ):
            raise ValueError("max_channel_error must be an integer in 0..255")
        for value in (
            self.max_pixels,
            self.max_images,
            self.max_frame_events,
            self.max_rectangles,
            self.max_frame_chars,
            self.max_output_chars,
            self.max_frames,
            self.max_cached_masks,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("raster limits must be positive integers")


@dataclass(frozen=True)
class RasterEstimate:
    """Preflight raster frames, target samples, canvas pixels, per-frame event limit, and declared spatial channel error.

    Final encoded output is checked separately.
    """

    frames: int
    target_samples: int
    canvas_pixels: int
    frame_event_limit: int
    max_channel_error: int = 0


class RasterPlan(Protocol):
    estimate: RasterEstimate
    origin: EventOrigin
    layer_count: int

    def evaluate(
        self, *, style: str, layer: int, max_events: int, max_chars: int
    ) -> tuple[Line, ...]: ...
