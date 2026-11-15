"""Document lyric binding: shared shaped body, scoped ruby and source anchors."""

from dataclasses import dataclass, replace

from .ass import Document, Line, Style
from .characters import LayoutCapabilityError
from .document_lyrics import DocumentLyrics, LyricUnit, RubyText
from .document_text import _appearance
from .geometry import Vec2
from .model import Box
from .scene import Lifetime, ObjectGroup
from .scene_animation import VisualState
from .scene_text import DocumentLayout, PositionedText, _layout_document_view, _union
from .sources import EventOrigin, SourceRef


@dataclass(frozen=True)
class PositionedRuby:
    """A reading layout associated with a source unit/segment and decoded body range.

    Its own text view retains source mappings and singing timing.
    """

    unit_index: int
    segment_index: int
    body_start: int
    body_end: int
    layout: DocumentLayout


@dataclass(frozen=True)
class LyricLayout:
    """Measured body and positioned readings for projected DocumentLyrics.

    unit_group builds editable body/ruby groups using the body center as pivot.
    """

    lyrics: DocumentLyrics
    body: DocumentLayout
    ruby: tuple[PositionedRuby, ...]
    bounds: Box

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


def _move(layout: DocumentLayout, dx: float, dy: float) -> DocumentLayout:
    return replace(
        layout,
        characters=tuple(_shift(item, dx, dy) for item in layout.characters),
        bounds=replace(
            layout.bounds, left=layout.bounds.left + dx, top=layout.bounds.top + dy
        ),
    )


def _ruby_view(document: Document, ruby: RubyText) -> tuple[Document, RubyText]:
    styles = document.styles
    replacements: dict[str, Style] = {}
    runs = []
    for run in ruby.source.runs:
        name = run.appearance.style + "-furigana"
        parent = styles[run.appearance.style]
        style = styles.get(
            name,
            replace(
                parent,
                name=name,
                fontsize=parent.fontsize / 2,
                outline=parent.outline / 2,
                shadow=parent.shadow / 2,
            ),
        )
        replacements[name] = style
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
    ruby_gap: float = 0,
) -> LyricLayout:
    """Bind body/ruby without changing original singing or decoded source ranges.

    Body text is shaped together before ruby spacing is applied. Unit boundaries
    crossing a shaping cluster are rejected when independent placement is needed.
    Joined ruby runs share a row; explicit break/spill markers start a new group.
    """
    from .geometry import finite

    finite(ruby_gap)
    if ruby_gap < 0:
        raise ValueError("ruby gap cannot be negative")
    record = document.records[record_index]
    if not isinstance(record, Line):
        raise TypeError("lyric binding requires an event record")
    lyrics = document.lyrics_at(record_index)
    singing = tuple(
        segment.singing for unit in lyrics.units for segment in unit.segments
    )
    body = _layout_document_view(
        document, lyrics.body, record_index, id=id, display=display, singing=singing
    )
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
                display=body.lifetime,
                singing=(
                    replace(
                        segment.singing,
                        start_offset=0,
                        end_offset=len(ruby.source.text),
                    ),
                ),
            )
            origin = EventOrigin((SourceRef(body.id, ui, si),), "document ruby")
            layout = replace(
                layout,
                characters=tuple(
                    replace(item, object=replace(item.object, origin=origin))
                    for item in layout.characters
                ),
            )
            rubies.append(PositionedRuby(ui, si, unit.start, unit.end, layout))

    # Consecutive unbroken ruby-bearing units share one run. Continuation ruby
    # stays with its existing body unit, including explicit ruby breaks.
    groups: list[list[LyricUnit]] = []
    group_rubies: list[list[int]] = []
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
        join = bool(
            (not indices and groups and not group_rubies[-1])
            or (
                indices
                and groups
                and group_rubies[-1]
                and first is not None
                and first.mode == "join"
            )
        )
        if join:
            groups[-1].append(unit)
            group_rubies[-1].extend(indices)
        else:
            groups.append([unit])
            group_rubies.append(indices)
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
    shift = 0.0
    ruby_right: float | None = None
    for units, indices in zip(groups, group_rubies, strict=True):
        start, end = units[0].start, units[-1].end
        if start == end:
            continue
        box = body.range_bounds(start, end)
        width = sum(rubies[i].layout.bounds.width for i in indices)
        first_ruby = next(
            (
                s.ruby
                for unit in units
                for s in unit.segments
                if s.ruby is not None and s.ruby.source.text
            ),
            None,
        )
        offset = (
            (box.width - width) / 2
            if first_ruby is not None
            and (first_ruby.mode == "spill" or width <= box.width)
            else 0
        )
        left = box.left + shift
        if indices and ruby_right is not None:
            left = max(left, ruby_right - min(0, offset))
        shift = left - box.left
        for i, item in enumerate(characters):
            if start <= item.start and item.end <= end:
                characters[i] = _shift(item, shift)
            elif item.start < end and item.end > start:
                raise LayoutCapabilityError(
                    "ruby placement boundary splits a shaped cluster"
                )
        cursor = left + offset
        for index in indices:
            ruby = rubies[index]
            moved = _move(
                ruby.layout, cursor, box.top - ruby.layout.bounds.height - ruby_gap
            )
            rubies[index] = replace(ruby, layout=moved)
            cursor += ruby.layout.bounds.width
        if indices:
            ruby_right = cursor
    body = replace(
        body,
        characters=tuple(characters),
        bounds=_union(tuple(item.bounds for item in characters)),
    )
    return LyricLayout(
        lyrics,
        body,
        tuple(rubies),
        _union((body.bounds, *(r.layout.bounds for r in rubies))),
    )
