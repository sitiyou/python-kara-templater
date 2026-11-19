"""Structured karaoke input with independent timing and immutable layout results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """A source singing interval in milliseconds with optional ruby text.

    Zero duration is allowed as source data; positive visual animation lifetimes are
    handled separately.
    """

    start_ms: int
    end_ms: int
    ruby: str = ""

    def __post_init__(self) -> None:
        if type(self.start_ms) is not int or type(self.end_ms) is not int:
            raise ValueError("segment times must be integer milliseconds")
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            raise ValueError(
                f"invalid segment interval: {self.start_ms}..{self.end_ms}"
            )


@dataclass(frozen=True)
class TextUnit:
    """One body text unit with ordered, nonoverlapping singing segments.

    Static units can have no segments and repeated singing retains a single body
    string. ruby_continuation joins the preceding annotated unit. ruby_spillback
    allows a wide joined reading to extend to the left as well as the right.
    """

    text: str
    segments: tuple[Segment, ...] = ()
    ruby_continuation: bool = False
    ruby_spillback: bool = True

    def __post_init__(self) -> None:
        for left, right in zip(self.segments, self.segments[1:], strict=False):
            if left.end_ms > right.start_ms:
                raise ValueError(
                    f"overlapping or reversed segments in {self.text!r}: "
                    f"{left.start_ms}..{left.end_ms} and {right.start_ms}..{right.end_ms} ms"
                )


@dataclass(frozen=True)
class KaraokeLine:
    """An ordered tuple of TextUnit values forming one lyric line.

    It contains source content and timing, independently of its measured layout.
    """

    units: tuple[TextUnit, ...]


@dataclass(frozen=True)
class Box:
    """An axis-aligned layout rectangle in script pixels.

    right, center, and middle are derived from left, top, width, and height.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """The rectangle left coordinate plus its width, in script pixels."""
        return self.left + self.width

    @property
    def center(self) -> float:
        """The horizontal midpoint of the layout rectangle."""
        return self.left + self.width / 2

    @property
    def middle(self) -> float:
        """The vertical midpoint of the layout rectangle."""
        return self.top + self.height / 2


@dataclass(frozen=True)
class LaidOutSegment:
    """A singing segment with its measured horizontal interval and optional reading box.

    Geometry belongs to layout; times belong to its source Segment.
    """

    source: Segment
    left: float
    right: float
    ruby: Box | None


@dataclass(frozen=True)
class LaidOutUnit:
    """A source TextUnit paired with a layout box and measured segments.

    Unit geometry can contain multiple repeated singing intervals.
    """

    source: TextUnit
    box: Box
    segments: tuple[LaidOutSegment, ...]


@dataclass(frozen=True)
class LaidOutLine:
    """The measured line box and ordered laid-out units.

    Each unit still references its original structured source.
    """

    box: Box
    units: tuple[LaidOutUnit, ...]
