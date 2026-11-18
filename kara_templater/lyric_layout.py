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
    em_size: float | None = None

    def __post_init__(self) -> None:
        finite(
            self.entrance,
            self.exit,
            self.bounds.left,
            self.bounds.top,
            self.bounds.width,
            self.bounds.height,
        )
        if self.em_size is not None:
            finite(self.em_size)
            if self.em_size <= 0:
                raise ValueError("em_size must be positive")
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
    script_height: float | None = None

    def __post_init__(self) -> None:
        if self.script_height is not None:
            finite(self.script_height)
            if self.script_height <= 0:
                raise ValueError("script height must be positive")
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


type _Alignment = Literal["left", "center", "right"]


@dataclass(frozen=True, kw_only=True)
class Layout:
    """Allocate any positive number of rows, or override allocate entirely.

    Strict rotation is the default. 'available' searches from the next row for
    capacity. Optional preview/tail is shortened before required singing or
    animation could overlap. reset_after resets rotation after a singing gap;
    None preserves rotation across pauses. Lead and tags have no built-in meaning.

    position is the first row's top-left, defaulting to the context region.
    Alignment and offsets can be supplied per row.
    Alternating alignment places even rows on the left and odd rows on the right. Bounds already
    include ruby and inline cue reservations. gap is row-origin spacing in pixels.
    """

    rows: int = 1
    position: Vec2 | None = None
    gap: float = 120
    alignment: _Alignment | Literal["alternating"] | tuple[_Alignment, ...] = "left"
    offsets: tuple[Vec2, ...] = ()
    policy: Literal["strict", "available"] = "strict"
    reset_after: float | None = None

    def __post_init__(self) -> None:
        finite(self.gap)
        if type(self.rows) is not int or self.rows < 1 or self.gap <= 0:
            raise ValueError("layout needs positive rows and gap")
        if isinstance(self.alignment, tuple):
            if len(self.alignment) != self.rows or any(
                a not in ("left", "center", "right") for a in self.alignment
            ):
                raise ValueError("provide one horizontal alignment per row")
        elif self.alignment not in ("left", "center", "right", "alternating"):
            raise ValueError("unknown layout alignment")
        if self.offsets and len(self.offsets) != self.rows:
            raise ValueError("provide one offset per row")
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
            align = (
                self.alignment[row]
                if isinstance(self.alignment, tuple)
                else self.alignment
            )
            fraction = {"left": 0, "center": 0.5, "right": 1, "alternating": row % 2}[
                align
            ]
            position = Vec2(
                origin.x
                + (context.region.width - line.bounds.width) * fraction
                - line.bounds.left,
                origin.y + row * self.gap - line.bounds.top,
            )
            if self.offsets:
                position += self.offsets[row]
            result.append(Placement(line.id, position, display, row, reasons))
            occupied[row] = len(result) - 1
            next_row = (row + 1) % self.rows
            latest_end = max(line.singing.end, latest_end or line.singing.end)
        placements = tuple(result)
        validate_placements(lines, placements)
        return placements


@dataclass(frozen=True, kw_only=True)
class KaraokeRows:
    """Studio horizontal row presets, scaled from 1080p to the script height.

    One row is centered, three use left/center/right, other counts alternate.
    Use anchor to place a stream at the top or bottom of its region. Row height
    includes the largest measured lyric, ruby and reserved inline cue in this track.
    smart_horizontal defaults to equal_margins, moving the left and right rows
    inward by half the page's spare width. center_position treats each row
    independently. none keeps the preset alignments against the region margins.
    section_gap starts a new rotation after a longer singing silence (0 disables
    splitting). lane_gap reserves seconds between occupants when available.
    sync_entry and sync_ending align the first and last pages respectively;
    sync_each_page applies enabled synchronization to every page. fill_section
    holds each row toward the next same-row preview and aligns final page tails.
    """

    rows: int = 2
    anchor: Literal["top", "bottom"] = "bottom"
    smart_horizontal: Literal["equal_margins", "center_position", "none"] = (
        "equal_margins"
    )

    section_gap: float = 4.0
    lane_gap: float = 0.30
    sync_entry: bool = True
    sync_ending: bool = False
    sync_each_page: bool = False
    fill_section: bool = True

    def __post_init__(self) -> None:
        finite(self.section_gap, self.lane_gap)
        if min(self.section_gap, self.lane_gap) < 0:
            raise ValueError("section and lane gaps must be nonnegative seconds")
        if type(self.rows) is not int or not 1 <= self.rows <= 8:
            raise ValueError("Studio presets support one to eight rows")
        if self.smart_horizontal not in ("equal_margins", "center_position", "none"):
            raise ValueError("unknown smart horizontal placement")
        if self.anchor not in ("top", "bottom"):
            raise ValueError("unknown karaoke row anchor")

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        """Reserve singing intervals through Layout and align each measured row."""
        region = context.region
        scale = (context.script_height or region.height) / 1080
        inset = min(50 * scale, region.width / 4)
        height = max((line.bounds.height for line in lines), default=0)
        spacing = (90, 45, 60, 40, 25, 15, 8, 0)[self.rows - 1] * scale
        pitch = max(height + spacing, 0.001)
        margin = (60 if self.rows == 2 else 80) * scale
        y = (
            region.top + margin
            if self.anchor == "top"
            else region.top + region.height - margin - height - (self.rows - 1) * pitch
        )
        area = Box(
            region.left + inset, region.top, region.width - 2 * inset, region.height
        )
        alignments = (
            ("center",)
            if self.rows == 1
            else ("left", "center", "right")
            if self.rows == 3
            else tuple("left" if i % 2 == 0 else "right" for i in range(self.rows))
        )
        layout = Layout(rows=self.rows, gap=pitch, position=Vec2(area.left, y))
        sections = [0]
        for i in range(1, len(lines)):
            if (
                self.section_gap
                and lines[i].singing.start - lines[i - 1].singing.end > self.section_gap
            ):
                sections.append(i)
        sections.append(len(lines))
        adjusted: list[Placement] = []
        for start, end in zip(sections, sections[1:], strict=False):
            section = lines[start:end]
            placements = layout.allocate(section, replace(context, region=area))
            adjusted.extend(self._place_section(section, placements, area, alignments))
        # Long authored leads/tails can still meet across an instrumental break.
        last_in_row: dict[int | None, int] = {}
        for i, placement in enumerate(adjusted):
            j = last_in_row.get(placement.row)
            if (
                j is not None
                and adjusted[j].display.end + self.lane_gap > placement.display.start
            ):
                earlier, later = self._handoff(
                    lines[j], adjusted[j].display, lines[i], placement.display
                )
                adjusted[j] = replace(adjusted[j], display=earlier)
                adjusted[i] = replace(placement, display=later)
            last_in_row[placement.row] = i
        validate_placements(lines, tuple(adjusted))
        return tuple(adjusted)

    def _place_section(
        self,
        lines: tuple[LayoutLine, ...],
        placements: tuple[Placement, ...],
        area: Box,
        alignments: tuple[str, ...],
    ) -> list[Placement]:
        windows = self._page_windows(lines, placements)
        adjusted: list[Placement] = []
        for i in range(0, len(lines), self.rows):
            page = lines[i : i + self.rows]
            slots = (
                alignments[-len(page) :]
                if self.anchor == "bottom"
                else alignments[: len(page)]
            )
            widths = {"left": 0.0, "center": 0.0, "right": 0.0}
            for line, slot in zip(page, slots, strict=True):
                widths[slot] = max(widths[slot], line.bounds.width)
            head_em = page[0].em_size or page[0].bounds.height
            slack = (
                max(0, area.width - sum(widths.values()) + head_em)
                if widths["left"] and widths["right"]
                else 0.0
            )
            for line, slot, placement in zip(
                page, slots, placements[i : i + self.rows], strict=True
            ):
                width = line.bounds.width
                room = area.width - width
                if slot == "center" or (
                    len(page) == 1 and self.smart_horizontal != "none"
                ):
                    x = room / 2
                else:
                    inset_x = 0.0
                    if self.smart_horizontal == "equal_margins":
                        inset_x = slack / 2
                    elif self.smart_horizontal == "center_position":
                        inset_x = max(
                            0,
                            (area.width + (line.em_size or line.bounds.height)) / 2
                            - width,
                        )
                    x = inset_x if slot == "left" else room - inset_x
                adjusted.append(
                    replace(
                        placement,
                        position=placement.position + Vec2(x, 0),
                        display=windows[len(adjusted)],
                    )
                )
        return adjusted

    def _page_windows(
        self, lines: tuple[LayoutLine, ...], placements: tuple[Placement, ...]
    ) -> list[Lifetime]:
        """Spend optional preview and tail around protected same-row handoffs."""
        windows = [p.display for p in placements]
        for i, line in enumerate(lines):
            if i < self.rows:
                continue
            j = i - self.rows
            windows[j], windows[i] = self._handoff(
                lines[j], windows[j], line, windows[i]
            )
        for i in range(0, len(lines), self.rows):
            stop = min(i + self.rows, len(lines))
            first = min(w.start for w in windows[i:stop])
            last = max(w.end for w in windows[i:stop])
            for j in range(i, stop):
                start, end = windows[j].start, windows[j].end
                if self.sync_entry and (i == 0 or self.sync_each_page):
                    floor = (
                        windows[j - self.rows].end + self.lane_gap
                        if j >= self.rows
                        else 0
                    )
                    start = min(start, max(floor, first))
                if self.sync_ending and (stop == len(lines) or self.sync_each_page):
                    ceiling = (
                        windows[j + self.rows].start - self.lane_gap
                        if j + self.rows < len(lines)
                        else last
                    )
                    end = max(end, min(ceiling, last))
                windows[j] = Lifetime(start, end)
        if self.fill_section and windows:
            last_page = (len(windows) - 1) // self.rows * self.rows
            section_end = max(w.end for w in windows[last_page:])
            for j, window in enumerate(windows):
                if j + self.rows < len(lines):
                    end = windows[j + self.rows].start - self.lane_gap
                elif j >= last_page:
                    end = section_end
                else:
                    continue
                windows[j] = Lifetime(window.start, max(window.end, end))
        return windows

    def _handoff(
        self,
        previous: LayoutLine,
        before: Lifetime,
        following: LayoutLine,
        after: Lifetime,
    ) -> tuple[Lifetime, Lifetime]:
        room = following.required.start - previous.required.end
        if room < 0:
            raise ValueError(
                f"{following.id}: required window overlaps {previous.id} on the same row"
            )
        gap = min(self.lane_gap, room)
        end = max(previous.required.end, min(before.end, after.start - gap))
        return Lifetime(before.start, end), Lifetime(
            max(after.start, min(following.required.start, end + gap)), after.end
        )
