"""Structured karaoke input with independent timing and immutable layout results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    ruby: str = ""

    def __post_init__(self):
        if type(self.start_ms) is not int or type(self.end_ms) is not int:
            raise ValueError("segment times must be integer milliseconds")
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            raise ValueError(f"invalid segment interval: {self.start_ms}..{self.end_ms}")


@dataclass(frozen=True)
class TextUnit:
    text: str
    segments: tuple[Segment, ...] = ()

    def __post_init__(self):
        for left, right in zip(self.segments, self.segments[1:], strict=False):
            if left.end_ms > right.start_ms:
                raise ValueError(
                    f"overlapping or reversed segments in {self.text!r}: "
                    f"{left.start_ms}..{left.end_ms} and {right.start_ms}..{right.end_ms} ms"
                )


@dataclass(frozen=True)
class KaraokeLine:
    units: tuple[TextUnit, ...]


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self):
        return self.left + self.width

    @property
    def center(self):
        return self.left + self.width / 2

    @property
    def middle(self):
        return self.top + self.height / 2


@dataclass(frozen=True)
class LaidOutSegment:
    source: Segment
    left: float
    right: float
    ruby: Box | None


@dataclass(frozen=True)
class LaidOutUnit:
    source: TextUnit
    box: Box
    segments: tuple[LaidOutSegment, ...]


@dataclass(frozen=True)
class LaidOutLine:
    box: Box
    units: tuple[LaidOutUnit, ...]
