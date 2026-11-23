"""Bounded premultiplied compositing and lossless pixel-run ASS encoding.

Internal foundation for the shared Scene coverage and raster output strategies.
"""

from array import array
from dataclasses import dataclass
from math import floor

from . import _ass_preview
from ._native_types import RasterImage
from .ass import Line
from .raster_settings import OutputCapabilityError
from .timeline import DisplayWindow, _finite


@dataclass(frozen=True, kw_only=True)
class RasterBudget:
    max_pixels: int = 4_000_000
    max_images: int = 10_000
    max_events: int = 10_000
    max_rectangles: int = 200_000
    max_path_chars: int = 8_000_000

    def __post_init__(self) -> None:
        for value in (
            self.max_pixels,
            self.max_images,
            self.max_events,
            self.max_rectangles,
            self.max_path_chars,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("raster budgets must be positive integers")

    def check_pixels(self, width: int, height: int) -> None:
        if type(width) is not int or type(height) is not int or min(width, height) < 1:
            raise ValueError("raster dimensions must be positive integers")
        if width * height > self.max_pixels:
            raise OutputCapabilityError("raster pixel budget exceeded")


_DEFAULT_BUDGET = RasterBudget()


@dataclass(frozen=True)
class RasterFrame:
    width: int
    height: int
    rgba: bytes

    def __post_init__(self) -> None:
        if (
            type(self.width) is not int
            or type(self.height) is not int
            or min(self.width, self.height) < 1
            or len(self.rgba) != self.width * self.height * 4
        ):
            raise ValueError("RGBA buffer size must match positive raster dimensions")
        if not isinstance(self.rgba, bytes):
            raise TypeError("raster frames require immutable RGBA bytes")


class RasterCanvas:
    """Accumulate premultiplied channels, then apply group opacity once."""

    def __init__(
        self, width: int, height: int, *, budget: RasterBudget = _DEFAULT_BUDGET
    ) -> None:
        budget.check_pixels(width, height)
        self.width, self.height, self.budget = width, height, budget
        self.channels = array("f", [0]) * (width * height * 4)
        self._images = 0
        self._coverage = 0

    def over(self, image: RasterImage) -> None:
        left, top, width, height, _, color, coverage = image
        if (
            width < 0
            or height < 0
            or len(coverage) != width * height
            or not 0 <= color <= 0xFFFFFFFF
        ):
            raise ValueError("invalid raster coverage")
        if (
            self._images + 1 > self.budget.max_images
            or self._coverage + width * height > self.budget.max_pixels
        ):
            raise OutputCapabilityError("raster coverage budget exceeded")
        self._images += 1
        self._coverage += width * height
        opacity = (255 - (color & 255)) / 255
        red, green, blue = ((color >> shift) & 255 for shift in (24, 16, 8))
        for y in range(max(0, -top), min(height, self.height - top)):
            for x in range(max(0, -left), min(width, self.width - left)):
                alpha = coverage[y * width + x] / 255 * opacity
                if not alpha:
                    continue
                offset = ((top + y) * self.width + left + x) * 4
                inverse = 1 - alpha
                self.channels[offset] = (
                    red / 255 * alpha + self.channels[offset] * inverse
                )
                self.channels[offset + 1] = (
                    green / 255 * alpha + self.channels[offset + 1] * inverse
                )
                self.channels[offset + 2] = (
                    blue / 255 * alpha + self.channels[offset + 2] * inverse
                )
                self.channels[offset + 3] = alpha + self.channels[offset + 3] * inverse

    def over_frame(self, frame: RasterFrame, left: int = 0, top: int = 0) -> None:
        if (
            self._images + 1 > self.budget.max_images
            or self._coverage + frame.width * frame.height > self.budget.max_pixels
        ):
            raise OutputCapabilityError("raster coverage budget exceeded")
        self._images += 1
        self._coverage += frame.width * frame.height
        for y in range(max(0, -top), min(frame.height, self.height - top)):
            for x in range(max(0, -left), min(frame.width, self.width - left)):
                source = (y * frame.width + x) * 4
                alpha = frame.rgba[source + 3] / 255
                if not alpha:
                    continue
                destination = ((top + y) * self.width + left + x) * 4
                for channel in range(3):
                    self.channels[destination + channel] = frame.rgba[
                        source + channel
                    ] / 255 * alpha + self.channels[destination + channel] * (1 - alpha)
                self.channels[destination + 3] = alpha + self.channels[
                    destination + 3
                ] * (1 - alpha)

    def add_frame(self, frame: RasterFrame, left: int = 0, top: int = 0) -> None:
        """Add disjoint material contributions after filtering; normalize on finish."""
        if (
            self._images + 1 > self.budget.max_images
            or self._coverage + frame.width * frame.height > self.budget.max_pixels
        ):
            raise OutputCapabilityError("raster coverage budget exceeded")
        self._images += 1
        self._coverage += frame.width * frame.height
        for y in range(max(0, -top), min(frame.height, self.height - top)):
            for x in range(max(0, -left), min(frame.width, self.width - left)):
                source = (y * frame.width + x) * 4
                alpha = frame.rgba[source + 3] / 255
                if not alpha:
                    continue
                destination = ((top + y) * self.width + left + x) * 4
                for channel in range(3):
                    self.channels[destination + channel] += (
                        frame.rgba[source + channel] / 255 * alpha
                    )
                self.channels[destination + 3] += alpha

    def finish(self, *, opacity: float = 1) -> RasterFrame:
        _finite(opacity, "group opacity")
        if not 0 <= opacity <= 1:
            raise ValueError("group opacity must be in 0..1")
        result = bytearray(self.width * self.height * 4)
        for offset in range(0, len(result), 4):
            alpha = self.channels[offset + 3]
            quantized = min(255, floor(min(1, alpha) * opacity * 255 + 0.5))
            if not quantized:
                continue
            for channel in range(3):
                result[offset + channel] = min(
                    255,
                    max(0, floor(self.channels[offset + channel] / alpha * 255 + 0.5)),
                )
            result[offset + 3] = quantized
        return RasterFrame(self.width, self.height, bytes(result))


def rasterize(
    script: str,
    time_ms: int,
    resolution: tuple[int, int],
    *,
    opacity: float = 1,
    budget: RasterBudget = _DEFAULT_BUDGET,
) -> RasterFrame:
    width, height = resolution
    canvas = RasterCanvas(width, height, budget=budget)
    images = _ass_preview.rasterize(
        script, time_ms, width, height, budget.max_pixels, budget.max_images
    )
    for image in images:
        canvas.over(image)
    return canvas.finish(opacity=opacity)


def quantize_frame(frame: RasterFrame, max_channel_error: int) -> RasterFrame:
    """Bound spatial color error on every opaque background, without resampling.

    For alpha a, color c and background b, displayed color is a*c+(1-a)*b.
    Allocating separate budgets dc and da bounds the change by dc+da, since
    |a'*(c'-c)+(a'-a)*(c-b)| <= dc+da in 8-bit units. Later ASS transform
    quantization and temporal sampling are separate from this spatial budget.
    """
    if type(max_channel_error) is not int or not 0 <= max_channel_error <= 255:
        raise ValueError("max_channel_error must be an integer in 0..255")
    if not max_channel_error:
        return frame
    color_error = max_channel_error // 2
    alpha_error = max_channel_error - color_error

    def table(error: int) -> bytes:
        step = 2 * error + 1
        return bytes(min(255, ((value + error) // step) * step) for value in range(256))

    values = bytearray(frame.rgba.translate(table(color_error)))
    values[3::4] = frame.rgba[3::4].translate(table(alpha_error))
    for index in range(0, len(values), 4):
        if not values[index + 3]:
            values[index : index + 3] = b"\0\0\0"
    return RasterFrame(frame.width, frame.height, bytes(values))


def encode_frame(
    frame: RasterFrame,
    window: DisplayWindow,
    *,
    style: str = "Default",
    position: tuple[int, int] = (0, 0),
    resolution: tuple[int, int] | None = None,
    neutral_style: bool = False,
    budget: RasterBudget = _DEFAULT_BUDGET,
) -> tuple[Line, ...]:
    """Encode disjoint integer rectangles without palette or spatial reduction.

    Adjacent identical runs merge vertically. Each rectangle uses a fully covered
    solid drawing and an integer rectangular clip: drawing the run itself gives
    libass's antialiased vector edges (up to 4/255 error for one-pixel runs).
    neutral_style requires the caller to install and validate a neutral ASS style;
    then its inherited defaults need not be repeated in each pixel event.
    """
    budget.check_pixels(frame.width, frame.height)
    rectangles: list[tuple[int, int, int, int, bytes]] = []
    active: dict[tuple[int, int, bytes], int] = {}
    count = 0
    for y in range(frame.height):
        current: dict[tuple[int, int, bytes], int] = {}
        x = 0
        while x < frame.width:
            offset = (y * frame.width + x) * 4
            rgba = frame.rgba[offset : offset + 4]
            start = x
            x += 1
            while (
                x < frame.width
                and frame.rgba[
                    (y * frame.width + x) * 4 : (y * frame.width + x + 1) * 4
                ]
                == rgba
            ):
                x += 1
            if not rgba[3]:
                continue
            key = (start, x, rgba)
            if key in active:
                current[key] = active.pop(key)
            else:
                count += 1
                if count > budget.max_rectangles:
                    raise OutputCapabilityError("raster rectangle budget exceeded")
                if count > budget.max_events:
                    raise OutputCapabilityError("raster event budget exceeded")
                current[key] = y
        rectangles.extend(
            (left, top, right, y, rgba) for (left, right, rgba), top in active.items()
        )
        active = current
    rectangles.extend(
        (left, top, right, frame.height, rgba)
        for (left, right, rgba), top in active.items()
    )
    events: list[Line] = []
    characters = 0
    dx, dy = position
    output_width, output_height = resolution or (frame.width, frame.height)
    path = f"m 0 0 l {output_width + 4} 0 {output_width + 4} {output_height + 4} 0 {output_height + 4}"
    defaults = (
        ""
        if neutral_style
        else r"\pbo0\bord0\shad0\blur0\be0\fscx100\fscy100\frz0\frx0\fry0\fax0\fay0"
    )
    for left, top, right, bottom, rgba in rectangles:
        text = (
            r"{\an7\pos(-2,-2)\p1"
            + defaults
            + rf"\clip({left + dx},{top + dy},{right + dx},{bottom + dy})\1c&H{rgba[2]:02X}{rgba[1]:02X}{rgba[0]:02X}&\alpha&H{255 - rgba[3]:02X}&}}"
            + path
        )
        characters += len(text)
        if characters > budget.max_path_chars:
            raise OutputCapabilityError("raster path budget exceeded")
        events.append(
            Line(
                text=text,
                style=style,
                start_time=window.start_ms,
                end_time=window.end_ms,
            )
        )
    return tuple(events)


type PositionedFrame = tuple[int, int, RasterFrame]


def compose_frames(
    frames: tuple[PositionedFrame, ...],
    *,
    opacity: float = 1,
    additive: bool = False,
    budget: RasterBudget = _DEFAULT_BUDGET,
) -> PositionedFrame | None:
    if not frames:
        return None
    left, top = min(x for x, _, _ in frames), min(y for _, y, _ in frames)
    right = max(x + frame.width for x, _, frame in frames)
    bottom = max(y + frame.height for _, y, frame in frames)
    canvas = RasterCanvas(right - left, bottom - top, budget=budget)
    for x, y, frame in frames:
        if additive:
            canvas.add_frame(frame, x - left, y - top)
        else:
            canvas.over_frame(frame, x - left, y - top)
    return left, top, canvas.finish(opacity=opacity)


def crop_frame(
    frame: PositionedFrame, resolution: tuple[int, int]
) -> PositionedFrame | None:
    x, y, pixels = frame
    left, top = max(0, x), max(0, y)
    right, bottom = (
        min(resolution[0], x + pixels.width),
        min(resolution[1], y + pixels.height),
    )
    if left >= right or top >= bottom:
        return None
    data = b"".join(
        pixels.rgba[
            ((row - y) * pixels.width + left - x) * 4 : (
                (row - y) * pixels.width + right - x
            )
            * 4
        ]
        for row in range(top, bottom)
    )
    return left, top, RasterFrame(right - left, bottom - top, data)
