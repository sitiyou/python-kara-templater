"""Measured, source-mapped text objects for Document scene frontends."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .ass import Document, Line, Style
from .characters import FontFace, LayoutCapabilityError, layout_characters
from .composition import Color
from .document_text import DocumentText, TextRun, _packed_color, resolve_singing
from .document_text import SingingSpan as SingingSpan
from .geometry import Vec2, VectorPath
from .layout import text_extents
from .model import Box, LaidOutLine, LaidOutUnit, TextUnit
from .scene import Lifetime, ObjectGroup, PathObject, TextObject
from .scene_animation import AnimationClip, StateFunction, VisualState
from .sources import EventOrigin, SourceRef


@dataclass(frozen=True)
class PositionedText:
    """A drawable text cluster, decoded source range, measured advance/ink bounds, and selected font faces.

    Layout scale is retained when used for range measurements. baseline is the
    local y coordinate of the font baseline measured during shaping.
    """

    start: int
    end: int
    object: TextObject
    bounds: Box
    ink_bounds: Box | None
    fonts: tuple[FontFace, ...]
    layout_scale: Vec2 | None = None
    _gap_shift: float = 0
    baseline: float | None = None

    def __post_init__(self) -> None:
        scale = (
            self.object.state.scale if self.layout_scale is None else self.layout_scale
        )
        if min(scale.x, scale.y) <= 0:
            raise LayoutCapabilityError("measured layout scale must be positive")
        object.__setattr__(self, "layout_scale", scale)


@dataclass(frozen=True)
class DocumentLayout:
    """Measured editable text objects with decoded source ranges, singing spans, bounds, and source-record identity.

    Range backgrounds can optionally follow local text animation.
    """

    id: str
    record_index: int | None
    source: DocumentText
    lifetime: Lifetime
    characters: tuple[PositionedText, ...]
    singing: tuple[SingingSpan, ...]
    bounds: Box

    def group(self, *, position: Vec2 | None = None) -> ObjectGroup:
        """Collect measured text objects into an editable group with the layout lifetime."""
        return ObjectGroup(
            id=self.id,
            lifetime=self.lifetime,
            state=VisualState(position=Vec2() if position is None else position),
            children=tuple(item.object for item in self.characters),
        )

    def _sweep_bounds(self, start: int, end: int, glyph: PositionedText) -> Box:
        """Place the original advance interval at this glyph's corrected position."""
        selected = tuple(c for c in self.characters if start <= c.start and c.end <= end)
        return _union(tuple(
            replace(c.bounds, left=c.bounds.left - c._gap_shift + glyph._gap_shift)
            for c in selected
        ))

    def range_bounds(self, start: int, end: int, *, time: float | None = None) -> Box:
        """Bounds for an explicit word/range; reject splits within shaping clusters."""
        if start < 0 or end <= start or end > len(self.source.text):
            raise ValueError("text range must be a nonempty interval within the source")
        selected = tuple(
            item for item in self.characters if item.start < end and item.end > start
        )
        if not selected or selected[0].start != start or selected[-1].end != end:
            raise LayoutCapabilityError("range boundary splits a shaped cluster")
        if time is None:
            return _union(tuple(item.bounds for item in selected))
        boxes: list[Box] = []
        for item in selected:
            state = item.object.at(time)
            assert item.layout_scale is not None
            width = item.bounds.width / item.layout_scale.x
            height = item.bounds.height / item.layout_scale.y
            corners = tuple(
                state.transform.apply(point)
                for point in (
                    Vec2(),
                    Vec2(width, 0),
                    Vec2(width, height),
                    Vec2(0, height),
                )
            )
            left, top = min(p.x for p in corners), min(p.y for p in corners)
            boxes.append(
                Box(
                    left,
                    top,
                    max(p.x for p in corners) - left,
                    max(p.y for p in corners) - top,
                )
            )
        return _union(tuple(boxes))

    def background(
        self,
        start: int,
        end: int,
        *,
        id: str,
        color: Color,
        padding: Vec2 | None = None,
        layer: int = -1,
        follow: bool = False,
    ) -> PathObject:
        """Create a measured range background with padding and optional local animation following."""
        box = self.range_bounds(start, end)
        padding = Vec2(8, 4) if padding is None else padding
        if min(padding.x, padding.y) < 0:
            raise ValueError("background padding cannot be negative")
        animations: list[AnimationClip] = []
        if follow:
            points = {self.lifetime.start, self.lifetime.end}
            for item in self.characters:
                for clip in item.object.animations:
                    points.update(
                        t
                        for t in (
                            item.object.time_origin + clip.start,
                            item.object.time_origin + clip.end,
                            *(
                                item.object.time_origin + clip.start + point
                                for point in clip.breakpoints
                            ),
                        )
                        if self.lifetime.start < t < self.lifetime.end
                    )
            ordered = sorted(points)
            for a, b in zip(ordered, ordered[1:], strict=False):

                def track(
                    state: VisualState,
                    progress: float,
                    first: float = a,
                    last: float = b,
                ) -> VisualState:
                    current = self.range_bounds(
                        start, end, time=first + (last - first) * progress
                    )
                    return replace(
                        state,
                        position=Vec2(
                            current.left - padding.x, current.top - padding.y
                        ),
                        scale=Vec2(
                            (current.width + 2 * padding.x)
                            / (box.width + 2 * padding.x),
                            (current.height + 2 * padding.y)
                            / (box.height + 2 * padding.y),
                        ),
                    )

                animations.append(
                    AnimationClip(
                        a - self.lifetime.start,
                        b - a,
                        StateFunction(track, frozenset(("position", "scale"))),
                    )
                )
        return PathObject(
            id=id,
            lifetime=self.lifetime,
            path=VectorPath.rectangle(
                box.width + 2 * padding.x, box.height + 2 * padding.y
            ),
            state=VisualState(
                position=Vec2(box.left - padding.x, box.top - padding.y), fill=color
            ),
            layer=layer,
            animations=tuple(animations),
            origin=EventOrigin((SourceRef(self.id),), "word background"),
        )


def _union(boxes: tuple[Box, ...]) -> Box:
    if not boxes:
        return Box(0, 0, 0, 0)
    left, top = min(box.left for box in boxes), min(box.top for box in boxes)
    return Box(
        left,
        top,
        max(box.right for box in boxes) - left,
        max(box.top + box.height for box in boxes) - top,
    )


def _shape_key(style: Style) -> tuple[str, float, bool, bool, float, float, float, int]:
    return (
        style.fontname,
        style.fontsize,
        style.bold,
        style.italic,
        style.scale_x,
        style.scale_y,
        style.spacing,
        style.encoding,
    )


def _style_supported(style: Style) -> None:
    fields = {key.lower(): value for key, value in style.fields.items()}
    if fields.get("borderstyle", "1") != "1" or float(fields.get("angle", "0")) != 0:
        raise LayoutCapabilityError(
            "document text binding currently requires border style 1 and zero style angle"
        )
    if int(fields.get("underline", "0")) or int(fields.get("strikeout", "0")):
        raise LayoutCapabilityError(
            "document text binding does not yet lower underline/strikeout"
        )
    for name in ("primarycolour", "secondarycolour", "outlinecolour", "backcolour"):
        if _packed_color(fields.get(name, "&H00000000")) >> 24:
            raise LayoutCapabilityError(
                "per-channel style alpha requires channel-opacity lowering"
            )


def _layout_document_view(
    document: Document,
    source: DocumentText,
    record_index: int | None,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
    singing: tuple[SingingSpan, ...] | None = None,
) -> DocumentLayout:
    """Measure an event into verified drawable clusters without changing its times.

    Inline colors override style colors. Caller changes to returned TextObjects
    override those values; animations then override their declared channels.
    Font changes begin new shaping runs. Color/timing changes do not split a
    shaping run, and painting half of a ligature is explicitly rejected.
    """
    source.require_supported()
    if display is None or singing is None:
        if record_index is None:
            raise ValueError(
                "structured text needs explicit display and singing intervals"
            )
        record = document.records[record_index]
        if not isinstance(record, Line):
            raise TypeError("text binding requires an event record")
        if display is None:
            display = Lifetime(record.start_time / 1000, record.end_time / 1000)
        if singing is None:
            singing = resolve_singing(source, record.start_time / 1000)
    identifier = f"record:{record_index}" if id is None else id
    lifetime = display
    styles = document.styles
    groups: list[list[TextRun]] = []
    for run in source.runs:
        if groups and _shape_key(styles[groups[-1][-1].appearance.style]) == _shape_key(
            styles[run.appearance.style]
        ):
            groups[-1].append(run)
        else:
            groups.append([run])
    items: list[PositionedText] = []
    x = 0.0
    for runs in groups:
        style = styles[runs[0].appearance.style]
        text = "".join(run.text for run in runs)
        try:
            for run in runs:
                _style_supported(styles[run.appearance.style])
            width, height, descent, _ = text_extents(style, text)
            box = Box(x, 0, width, height)
            measured = layout_characters(
                LaidOutLine(box, (LaidOutUnit(TextUnit(text), box, ()),)), style=style
            )
        except LayoutCapabilityError as error:
            raise LayoutCapabilityError(
                f"record {record_index}, decoded text range {runs[0].start}:{runs[-1].end}, "
                f"style {style.name!r}: {error}"
            ) from error
        for character in measured:
            start, end = (
                runs[0].start + character.source.start,
                runs[0].start + character.source.end,
            )
            covered = [run for run in runs if run.start < end and run.end > start]
            appearance = covered[0].appearance
            if any(
                replace(run.appearance, inline_colors=frozenset())
                != replace(appearance, inline_colors=frozenset())
                for run in covered[1:]
            ):
                raise LayoutCapabilityError(
                    f"record {record_index}: color/reset boundary splits shaped cluster {start}:{end}"
                )
            source_style = styles[appearance.style]
            if source_style.shadow and appearance.shadow != Color(0, 0, 0):
                raise LayoutCapabilityError(
                    "colored shadows require separate shadow-color lowering"
                )
            origin = EventOrigin((SourceRef(identifier, len(items)),), "document text")
            obj = TextObject(
                id=f"{identifier}/text:{start}:{end}",
                text=character.text,
                lifetime=lifetime,
                font=style.fontname,
                font_size=style.fontsize,
                bold=style.bold,
                italic=style.italic,
                spacing=style.spacing,
                encoding=style.encoding,
                state=VisualState(
                    position=Vec2(character.box.left, character.box.top),
                    scale=Vec2(style.scale_x / 100, style.scale_y / 100),
                    fill=appearance.primary,
                    outline=appearance.outline,
                    border=source_style.outline,
                    shadow=Vec2(source_style.shadow, source_style.shadow),
                ),
                origin=origin,
            )
            items.append(
                PositionedText(
                    start,
                    end,
                    obj,
                    character.box,
                    character.ink_bounds,
                    character.font_faces,
                    baseline=(height - descent) / obj.state.scale.y,
                )
            )
        x += width
    return DocumentLayout(
        identifier,
        record_index,
        source,
        lifetime,
        tuple(items),
        singing,
        _union(tuple(item.bounds for item in items)),
    )


def layout_document_text(
    document: Document,
    record_index: int,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
) -> DocumentLayout:
    """Bind a plain line; use layout_document_lyrics for ruby/continuations."""
    source = document.text_at(record_index)
    if any(character in source.text for character in "\n\r|｜#＃"):
        raise LayoutCapabilityError(
            "this text binder handles a single plain line; ruby/continuations require the lyric binder"
        )
    return _layout_document_view(document, source, record_index, id=id, display=display)
