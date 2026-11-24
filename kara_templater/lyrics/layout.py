"""Document lyric binding: shared shaped body, scoped ruby and source anchors."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import ceil, floor

from ..ass import Document, Line, Style
from ..characters import LayoutCapabilityError
from ..document_lyrics import DocumentLyrics, LyricUnit, RubyText
from ..document_text import DocumentText, TimedTextSpan, _appearance
from ..geometry import Box, Vec2, VectorPath, finite
from ..path_geometry import flatten
from ..scene import Lifetime, ObjectGroup
from ..scene_animation import VisualState
from ..sources import EventOrigin, SourceRef
from ..text.layout import PositionedText, TextLayout, _layout_document_view, _union
from ..text_geometry import TextOutline, _VectorGuideText


@dataclass(frozen=True)
class VectorGuide:
    """A timed lyric glyph with a baseline-relative path and horizontal advance in units of size.

    Positive y points down. One unit defaults to the authored font size at the marker; size overrides it in script pixels.
    Track.guide_symbols maps individual body characters to guide glyphs.
    """

    path: VectorPath
    advance: float = 1
    size: float | None = None

    def __post_init__(self) -> None:
        finite(self.advance)
        if self.size is not None:
            finite(self.size)
        if self.size is not None and self.size <= 0:
            raise ValueError("guide size must be positive")
        if self.advance < 0:
            raise ValueError("guide advance must be nonnegative")

    def _place(self, item: PositionedText) -> PositionedText:
        node = item.object
        baseline = Vec2(0, (item.baseline or 0) * node.state.scale.y)
        size = node.font_size if self.size is None else self.size
        path = self.path.map(lambda point: point * size + baseline)
        # The wipe follows the curve itself. Its Bézier handles can lie outside the ink.
        points = tuple(p for contour in path.contours for p in flatten(contour, tolerance=0.1).points)
        xmin, xmax = min(p.x for p in points), max(p.x for p in points)
        ymin, ymax = min(p.y for p in points), max(p.y for p in points)
        advance = max(1, round(self.advance * size))
        pos = Vec2(item.bounds.left, node.state.position.y)
        bounds = replace(item.bounds, width=advance)
        measured = TextOutline(path, Box(0, 0, advance, bounds.height), item.fonts)
        drawing = _VectorGuideText(**vars(node), outline=measured)
        return replace(
            item,
            object=replace(drawing, state=replace(node.state, position=pos, scale=Vec2(1, 1))),
            bounds=bounds,
            ink_bounds=Box(pos.x + xmin, pos.y + ymin, xmax - xmin, ymax - ymin),
        )


@dataclass(frozen=True, kw_only=True)
class StudioSpacing:
    """Studio lyric cell metrics for the body and its readings.

    space_width_percent sets an ASCII space's width as a percentage of the
    selected font em (10 to 100). allow_biting includes negative side bearings
    when measuring overhanging glyphs. Hard-outline clearance applies afterward.
    """

    space_width_percent: int = 20
    allow_biting: bool = False

    def __post_init__(self) -> None:
        if type(self.space_width_percent) is not int or not 10 <= self.space_width_percent <= 100:
            raise ValueError("space_width_percent must be an integer from 10 to 100")


@dataclass(frozen=True)
class PositionedRuby:
    """A reading layout associated with a source unit/segment and decoded body range.

    Its own text view retains source mappings and timing timing.
    """

    unit_index: int
    segment_index: int
    body_start: int
    body_end: int
    layout: TextLayout


@dataclass(frozen=True)
class LyricLayout:
    """Measured body and positioned readings for projected DocumentLyrics.

    unit_group builds editable body/ruby groups using the body center as pivot.
    """

    lyrics: DocumentLyrics
    body: TextLayout
    ruby: tuple[PositionedRuby, ...]
    bounds: Box
    script_height: int = 1080
    _vertical: bool = False

    def _body_wipe(
        self, unit: LyricUnit, *, reading_units: bool, reverse: bool,
    ) -> tuple[tuple[TimedTextSpan, float, float], ...]:
        parts = unit._body_parts(reading_units=reading_units)
        if (not reading_units or self._vertical or unit.end - unit.start < 2
                or not any(s.ruby and s.ruby.source.text for s in unit.segments)
                or len(unit._body_timing()) != 1):
            return parts
        glyphs = [c for c in self.body.characters if unit.start <= c.start and c.end <= unit.end]
        if len(glyphs) < 2:
            return parts
        glyphs.sort(key=lambda c: c.bounds.center, reverse=reverse)
        extent = self.body._sweep_bounds(unit.start, unit.end, glyphs[0])
        if extent.width == 0:
            return parts
        # Studio sweeps each glyph's primary ink, then crosses its side bearing
        # at the handoff. The offsets exclude clearance added after shaping.
        slots: list[tuple[float, float]] = []
        for glyph in glyphs:
            box = self.body._sweep_bounds(glyph.start, glyph.end, glyph)
            shift = glyphs[0]._gap_shift - glyph._gap_shift
            x0, x1 = box.left + shift - extent.left, box.right + shift - extent.left
            if reverse:
                x0, x1 = extent.width - x1, extent.width - x0
            left = max(slots[-1][1] if slots else 0.0, min(1.0, x0 / extent.width))
            slots.append((left, max(left, min(1.0, x1 / extent.width))))
        count = len(slots)

        def position(progress: float) -> float:
            if progress == 0 or progress == 1:
                return progress
            # At the exact switch Studio still shows the outgoing release.
            index = ceil(progress * count) - 1
            left, right = slots[index]
            return left + (right - left) * (progress * count - index)

        result = []
        for span, a, b in parts:
            duration = span.end - span.start
            # Keep native linear ASS motion within each glyph. Only its handoff
            # needs two additional poses, on the surrounding centiseconds.
            times = {span.end}
            for i in range(1, count):
                if a <= i / count <= b and b > a:
                    handoff = span.start + duration * (i / count - a) / (b - a)
                    tick = floor(handoff * 100 + 1e-9)
                    times.update(t for t in (tick / 100, (tick + 1) / 100) if span.start < t < span.end)
            start, entry = span.start, position(a)
            for end in sorted(times):
                progress = b if end == span.end else a + (b - a) * (end - span.start) / duration
                release = position(progress)
                result.append((replace(span, start=start, end=end), entry, release))
                start, entry = end, release
        return tuple(result)

    def group(self, *, position: Vec2 | None = None) -> ObjectGroup:
        """Combine measured body and positioned ruby objects into an editable group."""
        return ObjectGroup(
            id=self.body.id,
            lifetime=self.body.lifetime,
            state=VisualState(position=Vec2() if position is None else position),
            children=(
                *tuple(item.object for item in self.body.characters),
                *tuple(
                    item.object for ruby in self.ruby for item in ruby.layout.characters
                ),
            ),
        )

    def unit_group(self, index: int) -> ObjectGroup:
        """Body and associated ruby around their shared body-center pivot."""
        unit = self.lyrics.units[index]
        box = self.body.range_bounds(unit.start, unit.end)
        pivot = Vec2(box.center, box.middle)
        objects = [
            item.object
            for item in self.body.characters
            if item.start >= unit.start and item.end <= unit.end
        ]
        objects.extend(
            item.object
            for ruby in self.ruby
            if ruby.unit_index == index
            for item in ruby.layout.characters
        )
        return ObjectGroup(
            id=f"{self.body.id}/unit:{index}",
            lifetime=self.body.lifetime,
            state=VisualState(position=pivot),
            children=tuple(
                obj.copy(id=obj.id, offset=Vec2() - pivot) for obj in objects
            ),
        )


def _shift(item: PositionedText, dx: float, dy: float = 0) -> PositionedText:
    return replace(
        item,
        object=item.object.copy(id=item.object.id, offset=Vec2(dx, dy)),
        bounds=replace(
            item.bounds, left=item.bounds.left + dx, top=item.bounds.top + dy
        ),
        ink_bounds=None
        if item.ink_bounds is None
        else replace(
            item.ink_bounds,
            left=item.ink_bounds.left + dx,
            top=item.ink_bounds.top + dy,
        ),
    )


def _place_guides(layout: TextLayout, guides: Mapping[str, VectorGuide]) -> TextLayout:
    """Replace the measured cells before clearance, ruby placement and RTL ordering."""
    delta = 0.0
    items = []
    for original in layout.characters:
        item = _shift(original, delta) if delta else original
        guide = guides.get(item.object.text)
        if guide is not None:
            item = guide._place(item)
            delta += item.bounds.width - original.bounds.width
        items.append(item)
    return replace(layout, characters=tuple(items), bounds=_union(tuple(item.bounds for item in items)))


def _rtl_cells(layout: TextLayout, axis: float) -> TextLayout:
    """Reflect cell centers across the line, keeping each shaped glyph upright."""
    characters = tuple(
        replace(_shift(item, 2 * (axis - item.bounds.center)), _gap_shift=-item._gap_shift)
        for item in layout.characters
    )
    return replace(layout, characters=characters, _right_to_left=True,
                   bounds=replace(layout.bounds, left=2 * axis - layout.bounds.right))


def _studio_cells(layout: TextLayout, settings: StudioSpacing) -> TextLayout:
    """Measure N3 character cells around the ink of each already-shaped cluster."""
    x = layout.bounds.left
    characters = []
    for item in layout.characters:
        ink = item.ink_bounds
        scale = item.object.state.scale.x
        spacing = item.object.spacing * scale
        edge = round(2 * item.object.state.border)
        advance = max(1, round(item.bounds.width - spacing))
        if ink is None:
            em = round(item.em_size * scale)
            percent = settings.space_width_percent
            width = em * percent // 100 if item.object.text == " " else em * percent * 25 // 1000 + edge
            dx = x - item.bounds.left
        else:
            # A single glyph's pixel bearings include any partial overhang.
            # Studio falls back to truncating path bounds for a shaped cluster.
            bearing = floor if len(item.object.text) == 1 else int
            left = bearing(ink.left - item.bounds.left)
            right = bearing(advance - (ink.right - item.bounds.left))
            if not settings.allow_biting:
                left, right = max(left, 0), max(right, 0)
            ink_width = int(ink.width)
            width = max(0, int(ink_width * (advance + left + right) / advance)) + edge
            dx = x + int(ink_width * left / advance) + edge / 2 - ink.left
        placed = _shift(item, dx)
        bounds = replace(item.bounds, left=x, width=width)
        characters.append(replace(placed, bounds=bounds, _font_advance=advance))
        x += max(0, width + spacing)
    return replace(
        layout, characters=tuple(characters), _studio_spacing=True,
        bounds=_union(tuple(c.bounds for c in characters)),
    )


def _clear_outlines(
    items: tuple[PositionedText, ...],
    gap: float | None,
    reserved_border: float,
    right_to_left: bool,
    secondary_width: float = 0,
) -> tuple[PositionedText, ...]:
    if gap is None:
        return items
    shift = 0.0
    previous_edge: float | None = None
    previous_border = 0.0
    characters = []
    for item in items:
        ink = item.ink_bounds
        if ink is not None:
            if right_to_left:
                # The cell will move across the row but the ink stays upright.
                ink = replace(ink, left=2 * item.bounds.center - ink.right)
            border = max(reserved_border, item.object.state.border + secondary_width)
            if previous_edge is not None and (border or previous_border):
                shift = max(shift, previous_edge + gap - (ink.left - border))
            previous_border = border
            previous_edge = ink.right + border + shift
        characters.append(
            replace(_shift(item, shift), _gap_shift=shift) if shift else item
        )
    return tuple(characters)


def _reading_row(
    readings: list[TextLayout], gap: float | None,
    reserved_border: float, right_to_left: bool, secondary_width: float,
) -> list[TextLayout]:
    """Apply outline clearance across all timing fragments of a horizontal annotation."""
    cells: list[PositionedText] = []
    cursor = 0.0
    for reading in readings:
        cells.extend(_shift(c, cursor) for c in reading.characters)
        cursor += reading.bounds.width
    cells_with_clearance = _clear_outlines(tuple(cells), gap, reserved_border, right_to_left, secondary_width)
    result: list[TextLayout] = []
    start = 0
    for reading in readings:
        end = start + len(reading.characters)
        group = cells_with_clearance[start:end]
        result.append(replace(reading, characters=group, bounds=_union(tuple(c.bounds for c in group))))
        start = end
    return result


def _move(layout: TextLayout, dx: float, dy: float) -> TextLayout:
    return replace(
        layout,
        characters=tuple(_shift(item, dx, dy) for item in layout.characters),
        bounds=replace(
            layout.bounds, left=layout.bounds.left + dx, top=layout.bounds.top + dy
        ),
    )


def _after_onset(start: float, display_end: float) -> float:
    """First ASS tick after Studio's inclusive waiting frame."""
    return min(display_end, (round(start * 1000) // 10 + 1) / 100)


def _reading_intervals(
    reading: PositionedRuby, unit: LyricUnit, *, wipe: bool = True,
) -> tuple[TimedTextSpan, ...]:
    """Divide one reading checkpoint among shaped clusters on the source millisecond clock."""
    layout = reading.layout
    source = unit.segments[reading.segment_index].timing
    if not wipe:
        spans = unit._body_timing()
        end = spans[0].end if len(spans) == 1 else source.end
        return (replace(source, start=end, end=end, start_offset=0, end_offset=len(layout.source.text)),)
    clusters = layout.characters
    count = len(clusters)
    start_ms, end_ms = round(1000 * source.start), round(1000 * source.end)
    cuts = [
        source.start,
        *(
            max(
                source.start,
                min(source.end, (start_ms + (end_ms - start_ms) * i // count) / 1000),
            )
            for i in range(1, count)
        ),
        source.end,
    ]
    # The first visual segment is still waiting at its exact onset in Studio.
    # Interior zero-duration checkpoints take effect immediately.
    onset = next((s.timing.start for s in unit.segments if s.ruby and s.ruby.source.text.strip()), None)
    intervals = []
    for i, glyph in enumerate(clusters):
        start, end = cuts[i:i + 2]
        if start == end == onset:
            start = end = _after_onset(start, layout.lifetime.end)
        intervals.append(replace(source, start_offset=glyph.start, end_offset=glyph.end,
                                 start=start, end=end))
    return tuple(intervals)


def _ruby_style(styles: Mapping[str, Style], parent_name: str) -> Style:
    name = parent_name + "-furigana"
    if name in styles:
        return styles[name]
    parent = styles[parent_name]
    return replace(parent, name=name, fontsize=parent.fontsize / 2,
                   outline=parent.outline / 2, shadow=parent.shadow / 2)


def _ruby_view(document: Document, ruby: RubyText) -> tuple[Document, RubyText]:
    styles = document.styles
    replacements: dict[str, Style] = {}
    runs = []
    for run in ruby.source.runs:
        style = _ruby_style(styles, run.appearance.style)
        replacements[style.name] = style
        baseline = _appearance(style)
        appearance = replace(
            baseline,
            primary=run.appearance.primary
            if "primary" in run.appearance.inline_colors
            else baseline.primary,
            secondary=run.appearance.secondary
            if "secondary" in run.appearance.inline_colors
            else baseline.secondary,
            outline=run.appearance.outline
            if "outline" in run.appearance.inline_colors
            else baseline.outline,
            shadow=run.appearance.shadow
            if "shadow" in run.appearance.inline_colors
            else baseline.shadow,
            inline_colors=run.appearance.inline_colors,
        )
        runs.append(replace(run, appearance=appearance))
    # This temporary view is for measurement only; the source Document stays intact.
    view = Document([*document.records, *replacements.values()], document.meta)
    return view, replace(ruby, source=replace(ruby.source, runs=tuple(runs)))


def layout_document_lyrics(
    document: Document,
    record_index: int,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
    ruby_gap: float = 6,
    studio_spacing: bool | StudioSpacing = False,
    palt: bool = False,
    guide_symbols: Mapping[str, VectorGuide] | None = None,
    right_to_left: bool = False,
    vertical: bool = False,
    min_outline_gap: float | None = None,
    reserved_border: float = 0,
) -> LyricLayout:
    """Bind body/ruby without changing original timing or decoded source ranges.

    Body text is shaped together before ruby spacing is applied. Unit boundaries
    crossing a shaping cluster are rejected when independent placement is needed.
    vertical stacks cells downward around x=0, with readings on the right.
    Joined ruby runs share a row; explicit break/spill markers start a new group.
    """
    record = document.records[record_index]
    if not isinstance(record, Line):
        raise TypeError("lyric binding requires an event record")
    return layout_lyrics(
        document,
        document.lyrics_at(record_index),
        id=f"record:{record_index}" if id is None else id,
        display=Lifetime(record.start_time / 1000, record.end_time / 1000)
        if display is None
        else display,
        ruby_gap=ruby_gap,
        studio_spacing=studio_spacing,
        palt=palt,
        guide_symbols=guide_symbols,
        right_to_left=right_to_left, vertical=vertical,
        min_outline_gap=min_outline_gap,
        reserved_border=reserved_border,
    )


def layout_lyrics(
    document: Document,
    lyrics: DocumentLyrics,
    *,
    id: str,
    display: Lifetime,
    ruby_gap: float = 6,
    studio_spacing: bool | StudioSpacing = False,
    palt: bool = False,
    guide_symbols: Mapping[str, VectorGuide] | None = None,
    right_to_left: bool = False,
    vertical: bool = False,
    min_outline_gap: float | None = None,
    reserved_border: float = 0,
    secondary_width: float = 0,
) -> LyricLayout:
    """Measure structured or parsed lyrics using Document styles and resolution.

    studio_spacing measures character cells from ink width, bearings and the primary
    outline before applying minimum outline clearance. The default uses shaped advances.
    secondary_width reserves additional hard outline outside each primary stroke.
    palt applies the horizontal proportional metrics in each selected body or ruby font.
    ruby_gap sets the vertical clearance between the hard ink bounds of a
    reading group and its body before animation. Negative values allow overlap.
    vertical stacks glyphs in measured font cells. ruby_gap then separates the body
    and reading cells horizontally, in script pixels.
    No ASS event is required or synthesized. Timing intervals retain their full
    seconds precision; record indices, if present, are provenance only.
    """
    finite(ruby_gap, reserved_border, secondary_width, min_outline_gap or 0)
    if secondary_width < 0 or reserved_border < 0 or (min_outline_gap is not None and min_outline_gap < 0):
        raise ValueError("outline clearance must be nonnegative")

    def validate_text(source: DocumentText) -> None:
        source.require_supported()
        offset = 0
        for run in source.runs:
            if run.start != offset or run.end != run.start + len(run.text):
                raise ValueError(
                    f"{id}: text runs must cover contiguous decoded ranges"
                )
            offset = run.end
        if "\n" in source.text or "\r" in source.text:
            raise ValueError(f"{id}: multiline lyric layout is not yet supported")
        if any(cue.offset > offset for cue in source.cues):
            raise ValueError(f"{id}: cue lies outside decoded text")

    validate_text(lyrics.source)
    validate_text(lyrics.body)
    end = 0
    for unit in lyrics.units:
        if unit.start != end or unit.end < unit.start:
            raise ValueError(f"{id}: lyric units must cover contiguous body ranges")
        end = unit.end
        for segment in unit.segments:
            if (segment.timing.start_offset, segment.timing.end_offset) != (
                unit.start,
                unit.end,
            ):
                raise ValueError(f"{id}: timing offsets do not match their lyric unit")
            if (
                not 0
                <= segment.source_start
                <= segment.source_end
                <= len(lyrics.source.text)
            ):
                raise ValueError(f"{id}: timing source range lies outside source text")
            if segment.ruby is not None:
                validate_text(segment.ruby.source)
    if end != len(lyrics.body.text):
        raise ValueError(f"{id}: lyric units must cover the complete body")
    record_index = lyrics.source.record_index
    timing = tuple(
        segment.timing for unit in lyrics.units for segment in unit.segments
    )
    if guide_symbols and any(len(key) != 1 or key.isspace() for key in guide_symbols):
        raise ValueError("each vector guide marker must be one nonblank character")
    body = _layout_document_view(
        document, lyrics.body, record_index, id=id, display=display, timing=timing,
        guide_markers=guide_symbols or (), palt=palt and not vertical,
    )
    cells = StudioSpacing() if studio_spacing is True else studio_spacing
    if cells and not vertical:
        body = _studio_cells(body, cells)
    if guide_symbols and body.characters:
        body = _place_guides(body, guide_symbols)
    if min_outline_gap is not None and not vertical:
        body_cells = _clear_outlines(body.characters, min_outline_gap, reserved_border, right_to_left, secondary_width)
        body = replace(body, characters=body_cells, bounds=_union(tuple(c.bounds for c in body_cells)))
    rubies: list[PositionedRuby] = []
    for ui, unit in enumerate(lyrics.units):
        for si, segment in enumerate(unit.segments):
            if segment.ruby is None or not segment.ruby.source.text:
                continue
            view, ruby = _ruby_view(document, segment.ruby)
            layout = _layout_document_view(
                view,
                ruby.source,
                record_index,
                id=f"{body.id}/ruby:{ui}:{si}",
                palt=palt and not vertical,
                display=body.lifetime,
                timing=(
                    replace(
                        segment.timing,
                        start_offset=0,
                        end_offset=len(ruby.source.text),
                    ),
                ),
            )
            if cells and not vertical:
                layout = _studio_cells(layout, cells)
            origin = EventOrigin((SourceRef(body.id, ui, si),), "document ruby")
            layout = replace(
                layout,
                characters=tuple(
                    replace(item, object=replace(item.object, origin=origin))
                    for item in layout.characters
                ),
            )
            rubies.append(PositionedRuby(ui, si, unit.start, unit.end, layout))

    characters = [
        replace(
            item,
            object=replace(
                item.object,
                origin=EventOrigin(
                    tuple(
                        SourceRef(body.id, ui)
                        for ui, unit in enumerate(lyrics.units)
                        if unit.start < item.end and unit.end > item.start
                    ),
                    "document lyric body",
                ),
            ),
        )
        for item in body.characters
    ]
    if vertical:
        from .._vertical_lyrics import _vertical_from_font

        measured = LyricLayout(
            lyrics, replace(body, characters=tuple(characters)), tuple(rubies),
            body.bounds, document.meta.res_y,
        )
        return _vertical_from_font(measured, ruby_gap)

    # Consecutive unbroken ruby-bearing units share one run. Continuation ruby
    # stays with its existing body unit, including explicit ruby breaks.
    groups: list[list[LyricUnit]] = []
    group_rubies: list[list[int]] = []
    boundaries = {c.start for c in body.characters}
    for ui, unit in enumerate(lyrics.units):
        indices = [i for i, ruby in enumerate(rubies) if ruby.unit_index == ui]
        first = next(
            (
                segment.ruby
                for segment in unit.segments
                if segment.ruby is not None and segment.ruby.source.text
            ),
            None,
        )
        join = bool(indices and groups and group_rubies[-1] and first and first.mode == "join")
        # Adjacent bare syllables can share a single shaped cluster.
        if not indices and groups and not group_rubies[-1] and unit.start not in boundaries:
            join = True
        if join:
            groups[-1].append(unit)
            group_rubies[-1].extend(indices)
        else:
            groups.append([unit])
            group_rubies.append(indices)
    shift = 0.0
    spill: float | None = None
    previous_right = 0.0
    for units, indices in zip(groups, group_rubies, strict=True):
        start, end = units[0].start, units[-1].end
        if start == end:
            continue
        box = body.range_bounds(start, end)
        readings = [rubies[i].layout for i in indices]
        readings = _reading_row(readings, min_outline_gap, reserved_border, right_to_left, secondary_width) if readings else []
        width = _union(tuple(r.bounds for r in readings)).width if readings else 0.0
        spillback = any(s.ruby and s.ruby.mode == "spill" for unit in units for s in unit.segments)
        if spill is not None and spill > 0:
            spill -= max(0.0, box.left - previous_right)
        extra, offset, spill = _ruby_group(box.width, width, spillback, spill)
        shift += extra
        left = box.left + shift
        previous_right = box.right
        body_top = float("inf")
        for i, item in enumerate(characters):
            if start <= item.start and item.end <= end:
                characters[i] = _shift(item, shift)
                if indices and item.ink_bounds is not None:
                    border = max(reserved_border, item.object.state.border + secondary_width)
                    body_top = min(body_top, item.ink_bounds.top - border)
            elif item.start < end and item.end > start:
                raise LayoutCapabilityError(
                    "ruby placement boundary splits a shaped cluster"
                )
        if not indices:
            continue
        if body_top == float("inf"):
            body_top = box.top
        # Align joined fragments as one row. Measure their lowest hard ink
        # relative to a common layout-box bottom, including mixed font sizes.
        reading_bottom = max(
            (
                item.ink_bounds.top
                + item.ink_bounds.height
                + max(reserved_border, item.object.state.border + secondary_width)
                - reading.bounds.top
                - reading.bounds.height
                for reading in readings
                for item in reading.characters
                if item.ink_bounds is not None
            ),
            default=0.0,
        )
        row_bottom = body_top - ruby_gap - reading_bottom
        for index, reading in zip(indices, readings, strict=True):
            ruby = rubies[index]
            moved = _move(reading, left + offset, row_bottom - reading.bounds.top - reading.bounds.height)
            rubies[index] = replace(ruby, layout=moved)
    body = replace(
        body,
        characters=tuple(characters),
        bounds=_union(tuple(item.bounds for item in characters)),
    )
    if right_to_left:
        axis = body.bounds.center
        body = _rtl_cells(body, axis)
        rubies = [replace(r, layout=_rtl_cells(r.layout, axis)) for r in rubies]
    return LyricLayout(
        lyrics,
        body,
        tuple(rubies),
        _union((body.bounds, *(r.layout.bounds for r in rubies))),
        document.meta.res_y,
    )


def _ruby_group(
    body: float, reading: float, spillback: bool, previous: float | None,
) -> tuple[float, float, float | None]:
    """Return body shift, reading offset and carried spill, as in karaskel.do_furigana_layout."""
    if not reading:
        return 0, 0, previous - body if previous is not None and previous > 0 else None
    shift = max(0.0, previous or 0.0)
    excess = reading - body
    if excess <= 0:
        return shift, -excess / 2, excess / 2
    if spillback:
        # Lua distinguishes an absent spill from zero (a flush preceding annotation).
        return shift + (excess / 2 if previous is not None else 0), -excess / 2, excess / 2
    return shift, 0, excess
