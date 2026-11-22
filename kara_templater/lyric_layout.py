"""Batch lyric allocation in seconds, independent of animation evaluation.

An override receives the entire ordered sequence and returns placements. Local
variables are sufficient for custom rotation, lead resets and exceptional lines.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace
from typing import Literal

from .document_text import CueMarker
from .geometry import Vec2, finite
from .model import Box
from .scene import Lifetime
from .scene_animation import TimeSpan
from .sources import SourceRef


@dataclass(frozen=True)
class _RowMetrics:
    baseline: float
    ascent: float
    descent: float
    ruby_headroom: float


@dataclass(frozen=True, kw_only=True)
class LayoutLine:
    """Immutable measured input, with original singing and desired visibility.

    entrance/exit are requested animation durations in seconds, outside singing.
    display includes optional preview/tail and any explicitly reserved cue time.
    tags and cue markers carry source data; their layout meaning is user-defined.
    bounds includes body, ruby and reserved decorations in local pixels.
    body_bounds gives the measured body alone for ASS style alignment.
    """

    id: str
    singing: TimeSpan
    display: Lifetime
    bounds: Box
    body_bounds: Box | None = None
    entrance: float = 0
    exit: float = 0
    sources: tuple[SourceRef, ...] = ()
    tags: frozenset[str] = frozenset()
    cues: tuple[CueMarker, ...] = ()
    lead: bool = False
    reserved: Lifetime | None = None
    em_size: float | None = None
    _adaptive_handoff: bool = False
    _row_metrics: _RowMetrics | None = None
    _vertical: bool = False
    _lyric_width: float | None = None
    body_font_size: float | None = None

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
        if self.body_font_size is not None:
            finite(self.body_font_size)
            if self.body_font_size <= 0:
                raise ValueError("body_font_size must be positive")
        if not self.id:
            raise ValueError("layout line needs a stable id")
        if self.entrance < 0 or self.exit < 0:
            raise ValueError(f"{self.id}: entrance/exit durations cannot be negative")
        if self.bounds.width < 0 or self.bounds.height < 0:
            raise ValueError(f"{self.id}: measured dimensions cannot be negative")
        if not self._adaptive_handoff and self.singing.start < self.entrance:
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
        """Fixed occupancy, including cues, authored intervals and rigid transitions."""
        start = self.singing.start if self._adaptive_handoff else self.singing.start - self.entrance
        end = self.singing.end if self._adaptive_handoff else self.singing.end + self.exit
        return TimeSpan(
            min(start, self.reserved.start) if self.reserved else start,
            max(end, self.reserved.end) if self.reserved else end,
        )


def _adaptive_windows(
    old: LayoutLine, before: Lifetime, new: LayoutLine, after: Lifetime, lane_gap: float = 0,
) -> tuple[Lifetime, Lifetime]:
    left, right = old.required.end, new.required.start
    if left > right:
        cues = ", ".join(cue.id for line in (old, new) for cue in line.cues)
        detail = f"; cues: {cues}" if cues else ""
        raise ValueError(f"{new.id}: required window overlaps {old.id} on the same row "
                         f"({left:.3f}s > {right:.3f}s{detail})")
    if before.end + lane_gap <= after.start:
        return before, after
    available = new.singing.start - old.singing.end
    motion = old.exit + new.entrance
    if available < motion:
        desired = old.singing.end + available * old.exit / motion
    else:
        desired = min(before.end, new.singing.start - new.entrance)
    # A real cue or an independently timed effect can constrain either side.
    boundary = max(left, min(right, desired))
    end = min(before.end, boundary)
    start = max(after.start, boundary)
    # Preserve an optional lane gap only from spare preview before the entry.
    start = max(start, min(right, new.singing.start - new.entrance, end + lane_gap))
    return Lifetime(before.start, end), Lifetime(start, after.end)


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


def _lane_distances(
    placements: tuple[Placement, ...], extents: dict[str, float], rows: int,
    body: float, clearance: float, *, from_bottom: bool = False,
) -> dict[str, float]:
    """Pack co-visible measured boxes outward from one edge, across page handoffs."""
    lanes: dict[int, list[Placement]] = {}
    for placement in placements:
        if placement.row is not None:
            lanes.setdefault(placement.row, []).append(placement)
    offsets: dict[str, float] = {}
    earlier: list[tuple[int, list[Placement], list[float]]] = []
    for slot in range(max(rows, max(lanes, default=-1) + 1)):
        row = rows - 1 - slot if from_bottom and slot < rows else slot
        current = sorted(lanes.get(row, ()), key=lambda p: p.display.start)
        for item in current:
            distances: list[float] = []
            for prior_slot, peers, ends in earlier:
                skipped = slot - prior_slot - 1
                index = bisect_right(ends, item.display.start)
                while index < len(peers) and peers[index].display.start < item.display.end:
                    peer = peers[index]
                    distances.append(offsets[peer.id] + extents[peer.id]
                                     + clearance + skipped * (body + clearance))
                    index += 1
            offsets[item.id] = max(distances, default=slot * (body + clearance))
        if current:
            earlier.append((slot, current, [p.display.end for p in current]))
    return offsets


type _Alignment = Literal["left", "center", "right"]


@dataclass(frozen=True, kw_only=True)
class Layout:
    """Allocate any positive number of rows, or override allocate entirely.

    Strict rotation is the default. 'available' searches from the next row for
    capacity. Optional preview/tail is shortened before required singing or
    animation could overlap. reset_after resets rotation after a singing gap;
    None preserves rotation across pauses. A lead starts a new rotation by default.
    Set reset_on_lead to False to continue the sequence across leads.

    position is the first row's top-left, defaulting to the context region.
    Alignment and offsets can be supplied per row.
    Alternating alignment places even rows on the left and odd rows on the right. Bounds already
    include ruby and inline cue reservations. Omit gap for measured row heights plus
    20% of the largest body font size. Set gap for a fixed distance between row origins.
    """

    rows: int = 1
    position: Vec2 | None = None
    gap: float | None = None
    alignment: _Alignment | Literal["alternating"] | tuple[_Alignment, ...] = "left"
    offsets: tuple[Vec2, ...] = ()
    policy: Literal["strict", "available"] = "strict"
    reset_after: float | None = None
    reset_on_lead: bool = True

    def __post_init__(self) -> None:
        if self.gap is not None:
            finite(self.gap)
        if type(self.rows) is not int or self.rows < 1 or (self.gap is not None and self.gap <= 0):
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

    def row_offsets(
        self,
        lines: tuple[LayoutLine, ...],
        placements: tuple[Placement, ...],
        *,
        from_bottom: bool = False,
    ) -> dict[str, float]:
        """Distance of each numbered row from the anchor edge, in script pixels.

        Supply placements with final display intervals and non-overlapping occupants
        per row. Automatic spacing fits the measured boxes visible together and adds
        20% of the track's body font size between boxes. An empty lane reserves body
        height only. Each line stays at one position throughout its display.
        """
        if self.gap is not None:
            return {p.id: self.gap * (self.rows - 1 - p.row if from_bottom and p.row < self.rows else p.row)
                    for p in placements if p.row is not None}
        sizes = (line.body_font_size for line in lines if line.body_font_size is not None)
        body = max(sizes, default=max(
            ((line.body_bounds or line.bounds).height for line in lines), default=0
        ))
        return _lane_distances(placements, {line.id: line.bounds.height for line in lines},
                               self.rows, body, body * 0.2, from_bottom=from_bottom)

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        """Plan the complete batch once, without modifying singing or input order.

        Chronological input is required; equal starts retain input order. For a
        handoff with automatic timing, trim extra preview, hold, then transitions.
        Overlapping fixed windows raise with both line identities.
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
            if (self.reset_on_lead and line.lead) or (
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
                if line._adaptive_handoff:
                    old_display, display = _adaptive_windows(prior_line, prior.display, line, display)
                    if old_display != prior.display:
                        result[previous] = replace(prior, display=old_display, adjustments=(
                            *prior.adjustments, f"tail shortened for {line.id}",
                        ))
                    if display != line.display:
                        reasons = (f"preview shortened after {prior.id}",)
                elif prior_line.required.end > line.required.start:
                    raise ValueError(
                        f"{line.id}: row {row} occupied by {prior_line.id}; "
                        "required singing/animation intervals overlap"
                    )
                elif prior.display.end > display.start:
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
                origin.y - line.bounds.top,
            )
            if self.offsets:
                position += self.offsets[row]
            result.append(Placement(line.id, position, display, row, reasons))
            occupied[row] = len(result) - 1
            next_row = (row + 1) % self.rows
            latest_end = max(line.singing.end, latest_end or line.singing.end)
        offsets = self.row_offsets(lines, tuple(result))
        placements = tuple(replace(p, position=p.position + Vec2(0, offsets[p.id])) for p in result)
        validate_placements(lines, placements)
        return placements


@dataclass(frozen=True, kw_only=True)
class KaraokeRows:
    """Studio row and vertical-column presets, scaled from 1080p to the script height.

    On a vertical track, rows sets the column count; anchor aligns each column
    along its height. Columns rotate right to left on every page.
    One horizontal row is centered, three use left/center/right, other counts alternate.
    Use anchor to place a stream at the top, center or bottom of its region. Row height
    follows measured body, reading and cue bounds for co-visible lines. Inline cues retain their horizontal reservation.
    smart_horizontal defaults to equal_margins, moving the left and right rows
    inward by half the page's spare width. An inline cue contributes its width
    when positioning its host row. Peers measure that row by its lyrics and ruby.
    center_position treats each row
    independently. none keeps the preset alignments against the region margins.
    A lead starts a section on the first lane by default, including on partial pages.
    Set reset_on_lead to False to keep ordinary paging across leads.
    section_gap starts a new rotation after a longer singing silence (0 disables
    splitting). lane_gap reserves seconds between occupants when available.
    sync_entry and sync_ending align the first and last pages respectively;
    sync_each_page applies enabled synchronization to every page. fill_section
    holds each row toward the next same-row preview and aligns final page tails.
    """

    rows: int = 2
    anchor: Literal["top", "center", "bottom"] = "bottom"
    smart_horizontal: Literal["equal_margins", "center_position", "none"] = (
        "equal_margins"
    )

    section_gap: float = 4.0
    lane_gap: float = 0.30
    sync_entry: bool = True
    sync_ending: bool = False
    sync_each_page: bool = False
    fill_section: bool = True
    reset_on_lead: bool = True

    def __post_init__(self) -> None:
        finite(self.section_gap, self.lane_gap)
        if min(self.section_gap, self.lane_gap) < 0:
            raise ValueError("section and lane gaps must be nonnegative seconds")
        if type(self.rows) is not int or not 1 <= self.rows <= 8:
            raise ValueError("Studio presets support one to eight rows")
        if self.smart_horizontal not in ("equal_margins", "center_position", "none"):
            raise ValueError("unknown smart horizontal placement")
        if self.anchor not in ("top", "center", "bottom"):
            raise ValueError("unknown karaoke row anchor")

    def break_before(
        self, previous: LayoutLine, line: LayoutLine
    ) -> Literal["none", "page", "section"]:
        """Choose a boundary before line. Override to use tags, lead or source data.

        A page restarts the row sequence. A section also restarts first/last-page
        timing. Returning "none" retains automatic paging at row capacity.
        """
        if (self.reset_on_lead and line.lead) or (
            self.section_gap
            and line.singing.start - previous.singing.end > self.section_gap
        ):
            return "section"
        return "none"

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        """Paginate the track, resolve handoffs, and align each measured row."""
        region = context.region
        scale = (context.script_height or region.height) / 1080
        spacing = (90, 45, 60, 40, 25, 15, 8, 0)[self.rows - 1] * scale
        margin = (60 if self.rows == 2 else 80) * scale
        if lines and lines[0]._vertical:
            return self._place_columns(lines, region, round(margin), round(spacing))
        inset = min(50 * scale, region.width / 4)
        metrics = tuple(
            line._row_metrics or _RowMetrics(line.bounds.top, 0, line.bounds.height, 0)
            for line in lines
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
        pages, windows = self._timed_pages(lines)
        adjusted: list[Placement] = []
        for page in pages:
            adjusted.extend(
                self._place_page(
                    lines,
                    page,
                    windows,
                    area,
                    alignments,
                )
            )
        placements = tuple(adjusted)
        extents = {line.id: m.ascent + m.descent + m.ruby_headroom
                   for line, m in zip(lines, metrics, strict=True)}
        body_height = max((m.ascent + m.descent for m in metrics), default=0)
        above = _lane_distances(placements, extents, self.rows, body_height, spacing)
        below = _lane_distances(placements, extents, self.rows, body_height, spacing, from_bottom=True)
        for i, (p, m) in enumerate(zip(placements, metrics, strict=True)):
            top = region.top + margin + above[p.id]
            bottom = region.top + region.height - margin - below[p.id] - extents[p.id]
            y = top if self.anchor == "top" else bottom if self.anchor == "bottom" else (top + bottom) / 2
            adjusted[i] = replace(p, position=Vec2(p.position.x, y + m.ruby_headroom + m.ascent - m.baseline))
        validate_placements(lines, tuple(adjusted))
        return tuple(adjusted)

    def _timed_pages(
        self, lines: tuple[LayoutLine, ...]
    ) -> tuple[list[range], list[Lifetime]]:
        """Resolve page occupancy and display windows independently of geometry."""
        sections: list[list[range]] = []
        page_start = 0
        pages: list[range] = []
        for i in range(1, len(lines)):
            if lines[i].singing.start < lines[i - 1].singing.start:
                raise ValueError("layout lines must be in singing order")
            boundary = self.break_before(lines[i - 1], lines[i])
            if boundary != "none" or i - page_start == self.rows:
                pages.append(range(page_start, i))
                page_start = i
            if boundary == "section":
                sections.append(pages)
                pages = []
        if lines:
            pages.append(range(page_start, len(lines)))
            sections.append(pages)

        windows = [line.display for line in lines]
        vertical = bool(lines and lines[0]._vertical)
        last_in_row: dict[int, int] = {}
        for pages in sections:
            self._page_windows(lines, pages, windows, vertical=vertical)
            # Reserved cues and tails may reach across pages or sections.
            for page in pages:
                for row, i in enumerate(
                    page, start=self._row_offset(len(page), lines[page.start], vertical=vertical)
                ):
                    j = last_in_row.get(row)
                    if (
                        j is not None
                        and windows[j].end + self.lane_gap > windows[i].start
                    ):
                        windows[j], windows[i] = self._handoff(
                            lines[j], windows[j], lines[i], windows[i]
                        )
                    last_in_row[row] = i

        for pages in sections:
            for page in pages:
                # Exit in reading order, preserving any authored singing, cue and transition.
                for i in reversed(page[:-1]):
                    end = max(lines[i].required.end, windows[i + 1].end)
                    if windows[i].end > end:
                        windows[i] = Lifetime(windows[i].start, end)
        return [page for pages in sections for page in pages], windows

    def _row_offset(self, count: int, first: LayoutLine, *, vertical: bool = False) -> int:
        if vertical or (self.reset_on_lead and first.lead):
            return 0
        if self.anchor == "bottom" and count > 1:
            return self.rows - count
        if self.anchor == "center":
            return (self.rows - count + 1) // 2
        return 0

    def _place_page(
        self,
        lines: tuple[LayoutLine, ...],
        indices: range,
        windows: list[Lifetime],
        area: Box,
        alignments: tuple[str, ...],
    ) -> list[Placement]:
        adjusted: list[Placement] = []
        page = lines[indices.start : indices.stop]
        lead_page = self.reset_on_lead and page[0].lead
        offset = self._row_offset(len(page), page[0])
        # Studio measures page widths using page-local lanes. At draw time the
        # same alignment lookup receives the physical lane of the placed line.
        slot_offset = self.rows - len(page) if self.anchor == "bottom" and not lead_page else 0
        widths = {"left": 0.0, "center": 0.0, "right": 0.0}
        for lane, line in enumerate(page):
            slot = alignments[slot_offset + lane]
            widths[slot] = max(widths[slot], line.bounds.width if line._lyric_width is None else line._lyric_width)
        head_em = page[0].em_size or page[0].bounds.height
        page_slack = area.width - sum(widths.values()) + head_em
        for i, line in zip(indices, page, strict=True):
            row = offset + i - indices.start
            slot = alignments[min(slot_offset + row, self.rows - 1)]
            width = line.bounds.width
            room = area.width - width
            if slot == "center" or (len(page) == 1 and self.smart_horizontal != "none" and not lead_page):
                x = room / 2
            else:
                inset_x = 0.0
                if self.smart_horizontal == "equal_margins":
                    # Studio measures peers as lyrics alone. Only the line being
                    # placed contributes its inline cue to the page widths.
                    measured_slot = alignments[slot_offset + i - indices.start]
                    extra = max(0, width - widths[measured_slot])
                    if widths["left"] and widths["right"]:
                        inset_x = max(0, page_slack - extra) / 2
                elif self.smart_horizontal == "center_position":
                    inset_x = max(
                        0,
                        (area.width + (line.em_size or line.bounds.height)) / 2 - width,
                    )
                x = inset_x if slot == "left" else room - inset_x
            position = Vec2(
                area.left + x - line.bounds.left,
                0,
            )
            adjusted.append(Placement(line.id, position, windows[i], row))
        return adjusted

    def _page_windows(
        self,
        lines: tuple[LayoutLine, ...],
        pages: list[range],
        windows: list[Lifetime],
        *,
        vertical: bool,
    ) -> None:
        """Resolve adjacent page occupants before synchronizing a section."""
        predecessors: dict[int, int] = {}
        successors: dict[int, int] = {}
        for before, after in zip(pages, pages[1:], strict=False):
            offset = self._row_offset(len(after), lines[after.start], vertical=vertical) - self._row_offset(
                len(before), lines[before.start], vertical=vertical
            )
            for i in after:
                j = before.start + offset + i - after.start
                if j in before:
                    predecessors[i] = j
                    successors[j] = i
                    windows[j], windows[i] = self._handoff(
                        lines[j], windows[j], lines[i], windows[i]
                    )
        for page in pages:
            first = min(lines[i].display.start for i in page)
            last = max(windows[i].end for i in page)
            for i in page:
                start, end = windows[i].start, windows[i].end
                if self.sync_entry and (page == pages[0] or self.sync_each_page):
                    floor = (
                        windows[predecessors[i]].end + self.lane_gap
                        if i in predecessors
                        else 0
                    )
                    start = min(start, max(floor, first))
                if self.sync_ending and (page == pages[-1] or self.sync_each_page):
                    ceiling = (
                        windows[successors[i]].start - self.lane_gap
                        if i in successors
                        else last
                    )
                    end = max(end, min(ceiling, last))
                windows[i] = Lifetime(start, end)
        if self.fill_section:
            section_end = max(windows[i].end for i in pages[-1])
            for page in pages:
                for i in page:
                    end = windows[i].end
                    if i in successors:
                        end = max(end, windows[successors[i]].start - self.lane_gap)
                    elif page == pages[-1]:
                        end = section_end
                    windows[i] = Lifetime(windows[i].start, end)

    def _handoff(
        self,
        previous: LayoutLine,
        before: Lifetime,
        following: LayoutLine,
        after: Lifetime,
    ) -> tuple[Lifetime, Lifetime]:
        if following._adaptive_handoff:
            return _adaptive_windows(previous, before, following, after, self.lane_gap)
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

    def _place_columns(
        self, lines: tuple[LayoutLine, ...], region: Box, margin: float, spacing: float
    ) -> tuple[Placement, ...]:
        if not all(line._vertical for line in lines):
            raise ValueError("a column layout requires vertical measurements for every line")
        pages, windows = self._timed_pages(lines)
        lanes = tuple(Placement(lines[i].id, Vec2(), windows[i], lane)
                      for page in pages for lane, i in enumerate(page))
        widths = {line.id: line.bounds.width for line in lines}
        body = max((line.body_bounds or line.bounds).width for line in lines)
        distances = _lane_distances(lanes, widths, self.rows, body, spacing)
        placements: list[Placement] = []
        for line, lane in zip(lines, lanes, strict=True):
            room = region.height - line.bounds.height
            top = margin if self.anchor == "top" else max(room // 2, 0) if self.anchor == "center" else room - margin
            x = region.width - margin - distances[line.id] - line.bounds.right
            origin = Vec2(region.left + round(x), region.top + top - line.bounds.top)
            placements.append(replace(lane, position=origin))
        result = tuple(placements)
        validate_placements(lines, result)
        return result
