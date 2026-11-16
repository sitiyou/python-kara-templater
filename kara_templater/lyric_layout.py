"""Batch lyric allocation in seconds, independent of animation evaluation.

An override receives the entire ordered sequence and returns placements. Local
variables are sufficient for custom rotation, lead resets and exceptional lines.
"""

from dataclasses import dataclass, replace
from typing import Literal

from .document_text import CueMarker
from .geometry import Vec2, finite
from .model import Box
from .scene import Lifetime
from .scene_animation import TimeSpan
from .sources import SourceRef


@dataclass(frozen=True, kw_only=True)
class LayoutLine:
    """Immutable measured input, with original singing and desired visibility.

    entrance/exit are required animation durations in seconds, outside singing.
    display includes optional preview/tail and any explicitly reserved cue time.
    tags and cue markers carry source data; their layout meaning is user-defined.
    bounds includes body, ruby and reserved inline decorations in local pixels.
    """

    id: str
    singing: TimeSpan
    display: Lifetime
    bounds: Box
    entrance: float = 0
    exit: float = 0
    sources: tuple[SourceRef, ...] = ()
    tags: frozenset[str] = frozenset()
    cues: tuple[CueMarker, ...] = ()
    lead: bool = False
    reserved: Lifetime | None = None

    def __post_init__(self) -> None:
        finite(
            self.entrance,
            self.exit,
            self.bounds.left,
            self.bounds.top,
            self.bounds.width,
            self.bounds.height,
        )
        if not self.id:
            raise ValueError("layout line needs a stable id")
        if self.entrance < 0 or self.exit < 0:
            raise ValueError(f"{self.id}: entrance/exit durations cannot be negative")
        if self.bounds.width < 0 or self.bounds.height < 0:
            raise ValueError(f"{self.id}: measured dimensions cannot be negative")
        if self.singing.start < self.entrance:
            raise ValueError(f"{self.id}: entrance animation would start before zero")
        if (
            self.display.start > self.required.start
            or self.display.end < self.required.end
        ):
            raise ValueError(
                f"{self.id}: requested display omits required animation/singing"
            )

    @property
    def required(self) -> TimeSpan:
        """The minimum interval containing singing and entrance/exit animation."""
        return TimeSpan(
            min(
                self.singing.start - self.entrance,
                self.reserved.start if self.reserved else self.singing.start,
            ),
            max(
                self.singing.end + self.exit,
                self.reserved.end if self.reserved else self.singing.end,
            ),
        )


@dataclass(frozen=True)
class LayoutContext:
    """Read-only placement region and explicitly supplied cross-track references.

    Other tracks are information for overrides, never implicitly allocated by the
    built-in algorithm. Coordinates and measurements use script pixels.
    """

    region: Box
    other_lines: tuple[LayoutLine, ...] = ()

    def __post_init__(self) -> None:
        finite(self.region.left, self.region.top, self.region.width, self.region.height)
        if self.region.width <= 0 or self.region.height <= 0:
            raise ValueError("layout region must have positive dimensions")


@dataclass(frozen=True)
class Placement:
    """A visual origin and absolute display interval for one stable line id.

    row is optional metadata; free-form layouts do not need numbered slots.
    adjustments explains deliberate changes to desired visibility.
    """

    id: str
    position: Vec2
    display: Lifetime
    row: int | None = None
    adjustments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("placement needs a stable id")
        if self.row is not None and (type(self.row) is not int or self.row < 0):
            raise ValueError(f"{self.id}: row must be a nonnegative integer or None")


def validate_placements(
    lines: tuple[LayoutLine, ...], placements: tuple[Placement, ...]
) -> None:
    """Check complete source association and required time, allowing overlap.

    Custom allocators may use arbitrary positions, rows, and overlapping windows.
    No row capacity or collision policy is imposed here.
    """
    sources = {line.id: line for line in lines}
    if len(sources) != len(lines):
        raise ValueError("duplicate layout input ids")
    seen: set[str] = set()
    for placement in placements:
        if placement.id in seen:
            raise ValueError(f"{placement.id}: duplicate placement")
        seen.add(placement.id)
        if placement.id not in sources:
            raise ValueError(f"{placement.id}: placement has no source line")
        required = sources[placement.id].required
        if (
            placement.display.start > required.start + 1e-9
            or placement.display.end < required.end - 1e-9
        ):
            raise ValueError(
                f"{placement.id}: placement truncates required animation/singing"
            )
    missing = sources.keys() - seen
    if missing:
        raise ValueError(f"missing placements: {', '.join(sorted(missing))}")


@dataclass(frozen=True, kw_only=True)
class Layout:
    """Allocate any positive number of rows, or override allocate entirely.

    Strict rotation is the default. 'available' searches from the next row for
    capacity. Optional preview/tail is shortened before required singing or
    animation could overlap. reset_after resets rotation after a singing gap;
    None preserves rotation across pauses. Lead and tags have no built-in meaning.

    position is the first row's top-left, defaulting to the context region.
    alignment controls horizontal alignment within that region. Bounds already
    include ruby and inline cue reservations. gap is row-origin spacing in pixels.
    """

    rows: int = 1
    position: Vec2 | None = None
    gap: float = 120
    alignment: Literal["left", "center", "right"] = "left"
    policy: Literal["strict", "available"] = "strict"
    reset_after: float | None = None

    def __post_init__(self) -> None:
        finite(self.gap)
        if type(self.rows) is not int or self.rows < 1 or self.gap <= 0:
            raise ValueError("layout needs positive rows and gap")
        if self.alignment not in ("left", "center", "right"):
            raise ValueError("unknown layout alignment")
        if self.policy not in ("strict", "available"):
            raise ValueError("unknown row allocation policy")
        if self.reset_after is not None:
            finite(self.reset_after)
            if self.reset_after <= 0:
                raise ValueError("reset interval must be positive")

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        """Plan the complete batch once, without modifying singing or input order.

        Chronological input is required; equal starts retain input order. For a
        handoff, shorten the prior tail first, then the next preview. Required
        intervals that cannot fit raise with both line identities and the row.
        """
        if len({line.id for line in lines}) != len(lines):
            raise ValueError("duplicate layout input ids")
        if any(
            a.singing.start > b.singing.start
            for a, b in zip(lines, lines[1:], strict=False)
        ):
            raise ValueError("layout lines must be in singing order")
        result: list[Placement] = []
        occupied: dict[int, int] = {}
        next_row = 0
        latest_end: float | None = None
        origin = self.position or Vec2(context.region.left, context.region.top)
        for line in lines:
            if (
                self.reset_after is not None
                and latest_end is not None
                and line.singing.start - latest_end >= self.reset_after
            ):
                next_row = 0
            row = next_row
            if self.policy == "available":
                candidates = (
                    (next_row + offset) % self.rows for offset in range(self.rows)
                )
                row = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate not in occupied
                        or lines[occupied[candidate]].required.end
                        <= line.required.start
                    ),
                    next_row,
                )
            previous = occupied.get(row)
            display = line.display
            reasons: tuple[str, ...] = ()
            if previous is not None:
                prior_line, prior = lines[previous], result[previous]
                if prior_line.required.end > line.required.start:
                    raise ValueError(
                        f"{line.id}: row {row} occupied by {prior_line.id}; "
                        "required singing/animation intervals overlap"
                    )
                if prior.display.end > display.start:
                    boundary = max(prior_line.required.end, display.start)
                    if prior.display.end > boundary:
                        result[previous] = replace(
                            prior,
                            display=Lifetime(prior.display.start, boundary),
                            adjustments=(
                                *prior.adjustments,
                                f"tail shortened for {line.id}",
                            ),
                        )
                    if display.start < boundary:
                        display = Lifetime(boundary, display.end)
                        reasons = (f"preview shortened after {prior.id}",)
            fraction = {"left": 0, "center": 0.5, "right": 1}[self.alignment]
            position = Vec2(
                origin.x
                + (context.region.width - line.bounds.width) * fraction
                - line.bounds.left,
                origin.y + row * self.gap - line.bounds.top,
            )
            result.append(Placement(line.id, position, display, row, reasons))
            occupied[row] = len(result) - 1
            next_row = (row + 1) % self.rows
            latest_end = max(line.singing.end, latest_end or line.singing.end)
        placements = tuple(result)
        validate_placements(lines, placements)
        return placements
