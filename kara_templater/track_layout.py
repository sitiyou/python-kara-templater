"""Stateless row allocation and placement for a single lyric track."""

from dataclasses import replace

from .karaoke import KaraokeItem
from .model import Box, LaidOutLine
from .timeline import _finite


class Layout:
    """Base interface for reusable lyric row allocation and placement.

    Explicit layouts operate on measured lines without changing source text or
    singing clocks.
    """

    def __init__(
        self,
        *,
        rows: int = 1,
        position: tuple[float, float] | None = None,
        gap: float = 120,
    ) -> None:
        if type(rows) is not int or rows < 1:
            raise ValueError("layout rows must be positive")
        _finite(gap, "row gap")
        if gap <= 0:
            raise ValueError("row gap must be positive")
        if position is not None:
            for value in position:
                _finite(value, "layout position")
        self.rows, self.position, self.gap = rows, position, gap

    def allocate(self, items: tuple[KaraokeItem, ...]) -> dict[str, int]:
        """Assign source items to rows without modifying their lyric text or singing clocks."""
        ends = [-1] * self.rows
        result: dict[str, int] = {}
        next_row = 0
        for item in sorted(items, key=lambda item: item.window.start_ms):
            row = next(
                (
                    (next_row + offset) % self.rows
                    for offset in range(self.rows)
                    if ends[(next_row + offset) % self.rows] <= item.window.start_ms
                ),
                None,
            )
            if row is None:
                raise ValueError(f"{item.id}: all {self.rows} layout rows are occupied")
            result[item.id] = row
            ends[row] = item.window.end_ms
            next_row = (row + 1) % self.rows
        return result

    def place(self, layout: LaidOutLine, row: int) -> LaidOutLine:
        """Apply the configured row placement to a measured lyric line."""
        if not 0 <= row < self.rows:
            raise ValueError("layout row is outside its capacity")
        dx, dy = 0.0, row * self.gap
        if self.position is not None:
            dx = self.position[0] - layout.box.left
            dy += self.position[1] - layout.box.top

        def move(box: Box) -> Box:
            return replace(box, left=box.left + dx, top=box.top + dy)

        return replace(
            layout,
            box=move(layout.box),
            units=tuple(
                replace(
                    unit,
                    box=move(unit.box),
                    segments=tuple(
                        replace(
                            segment,
                            left=segment.left + dx,
                            right=segment.right + dx,
                            ruby=None if segment.ruby is None else move(segment.ruby),
                        )
                        for segment in unit.segments
                    ),
                )
                for unit in layout.units
            ),
        )


class SingleLine(Layout):
    """Place selected lyric lines on one configured row.

    Omitted position retains source positioning; explicit offsets and layout
    settings affect presentation only.
    """

    def __init__(self, *, position: tuple[float, float] | None = None) -> None:
        super().__init__(rows=1, position=position)


class DoubleLine(Layout):
    """Allocate two alternating lyric rows with explicit position and gap.

    TrackGroup can share this allocation across independently selected children.
    """

    def __init__(
        self,
        *,
        position: tuple[float, float] | None = None,
        gap: float = 120,
    ) -> None:
        super().__init__(rows=2, position=position, gap=gap)
