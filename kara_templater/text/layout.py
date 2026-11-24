"""Measured, source-mapped text objects for Document scene frontends."""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import groupby
from math import ceil, floor

from ..ass import Document, Line, Style
from ..characters import (
    DrawableCharacter,
    FontFace,
    LayoutCapabilityError,
    _measure_clusters,
)
from ..composition import Color
from ..document_text import (
    DocumentText,
    TextRun,
    TimedTextSpan,
    _packed_color,
    resolve_timing,
)
from ..geometry import Box, Vec2, VectorPath
from ..scene import Lifetime, ObjectGroup, PathObject, TextObject
from ..scene_animation import AnimationClip, StateFunction, VisualState
from ..sources import EventOrigin, SourceRef
from .measurement import text_extents


@dataclass(frozen=True)
class PositionedText:
    """A drawable text cluster, decoded source range, measured advance/ink bounds, and selected font faces.

    bounds is the allocated cell. The pen origin is object.state.position.
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
    source_style: str | None = None
    _font_advance: float | None = None

    @property
    def em_size(self) -> float:
        """Local size of one em of the cluster's primary shaped face, in script pixels."""
        return self.object.font_size * (self.fonts[0].em_ratio if self.fonts else 1.0)

    def __post_init__(self) -> None:
        scale = (
            self.object.state.scale if self.layout_scale is None else self.layout_scale
        )
        if min(scale.x, scale.y) <= 0:
            raise LayoutCapabilityError("measured layout scale must be positive")
        object.__setattr__(self, "layout_scale", scale)


@dataclass(frozen=True)
class TextLayout:
    """Measured editable text objects with decoded source ranges, timing spans, bounds, and source-record identity.

    Range backgrounds can optionally follow local text animation.
    """

    id: str
    record_index: int | None
    source: DocumentText
    lifetime: Lifetime
    characters: tuple[PositionedText, ...]
    timing: tuple[TimedTextSpan, ...]
    bounds: Box
    _cue_gradient_edge: float | None = None
    _right_to_left: bool = False
    _studio_spacing: bool = False
    _palt: bool = False
    _vertical: bool = False

    def group(self, *, position: Vec2 | None = None) -> ObjectGroup:
        """Collect measured text objects into an editable group with the layout lifetime."""
        return ObjectGroup(
            id=self.id,
            lifetime=self.lifetime,
            state=VisualState(position=Vec2() if position is None else position),
            children=tuple(item.object for item in self.characters),
        )

    def _sweep_bounds(self, start: int, end: int, glyph: PositionedText) -> Box:
        """Measure the moving front, excluding clearance, extra outlines and blur."""
        selected = tuple(c for c in self.characters if start <= c.start and c.end <= end)
        boxes = []
        for c in selected:
            box = c.bounds
            if self._studio_spacing:
                if c.ink_bounds is None:
                    continue
                edge = round(2 * c.object.state.border) // 2
                left = c.bounds.left + floor(c.ink_bounds.left - c.bounds.left) - edge
                right = c.bounds.left + ceil(c.ink_bounds.right - c.bounds.left) + edge
                box = replace(c.ink_bounds, left=left, width=right - left)
            boxes.append(replace(box, left=box.left - c._gap_shift + glyph._gap_shift))
        if not boxes:
            return replace(glyph.bounds, width=0)
        sweep = _union(tuple(boxes))
        if self._studio_spacing and end < len(self.source.text):
            following = next((c for c in self.characters if c.start == end), None)
            if following is not None:
                # N3 AdjustWipeEnd evaluates overlap in inclusive layout cells,
                # then applies the fraction to the visible primary stroke.
                if self._right_to_left:
                    start_x = selected[0].bounds.right - selected[0]._gap_shift
                    end_x = selected[-1].bounds.left - selected[-1]._gap_shift
                    next_x = following.bounds.right - following._gap_shift
                else:
                    start_x = selected[0].bounds.left - selected[0]._gap_shift
                    end_x = selected[-1].bounds.right - selected[-1]._gap_shift
                    next_x = following.bounds.left - following._gap_shift
                if min(start_x, end_x) <= next_x <= max(start_x, end_x):
                    fraction = abs(next_x - start_x) / (abs(end_x - start_x) + 1)
                    width = sweep.width * fraction
                    left = sweep.right - width if self._right_to_left else sweep.left
                    sweep = replace(sweep, left=left, width=width)
        return sweep

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
            left = (item.bounds.left - item.object.state.position.x) / item.layout_scale.x
            corners = tuple(
                state.transform.apply(point)
                for point in (
                    Vec2(left, 0),
                    Vec2(left + width, 0),
                    Vec2(left + width, height),
                    Vec2(left, height),
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


@lru_cache(maxsize=1024)
def _measure_run(
    key: tuple[str, float, bool, bool, float, float, float, int], text: str, x: float, palt: bool,
) -> tuple[float, float, float, tuple[DrawableCharacter, ...]]:
    family, size, bold, italic, sx, sy, spacing, encoding = key
    style = Style(fontname=family, fontsize=size, bold=bold, italic=italic,
                  scale_x=sx, scale_y=sy, spacing=spacing, encoding=encoding, outline=0)
    width, height, descent, _ = text_extents(style, text, palt=palt)
    box = Box(x, 0, width, height)
    chars = _measure_clusters(text, box, style=style, palt=palt)
    return width, height, descent, chars


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
    for name in ("primarycolour", "secondarycolour", "outlinecolour"):
        if _packed_color(fields.get(name, "&H00000000")) >> 24:
            raise LayoutCapabilityError(
                "per-channel style alpha requires channel-opacity lowering"
            )


def _guide_runs(runs: tuple[TextRun, ...], markers: Collection[str]) -> Iterator[TextRun]:
    """Isolate vector slots so neighboring text shapes normally on either side."""
    for run in runs:
        start = 0
        for index, char in enumerate(run.text):
            if char not in markers:
                continue
            if start < index:
                yield replace(run, text=run.text[start:index], start=run.start + start, end=run.start + index)
            yield replace(run, text=char, start=run.start + index, end=run.start + index + 1)
            start = index + 1
        if start < len(run.text):
            yield replace(run, text=run.text[start:], start=run.start + start)


def _layout_document_view(
    document: Document,
    source: DocumentText,
    record_index: int | None,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
    timing: tuple[TimedTextSpan, ...] | None = None,
    guide_markers: Collection[str] = (),
    palt: bool = False,
) -> TextLayout:
    """Measure an event into verified drawable clusters without changing its times.

    Inline colors override style colors. Caller changes to returned TextObjects
    override those values; animations then override their declared channels.
    Font changes begin new shaping runs. Color/timing changes do not split a
    shaping run, and painting half of a ligature is explicitly rejected.
    """
    source.require_supported()
    if display is None or timing is None:
        if record_index is None:
            raise ValueError(
                "structured text needs explicit display and timing intervals"
            )
        record = document.records[record_index]
        if not isinstance(record, Line):
            raise TypeError("text binding requires an event record")
        if display is None:
            display = Lifetime(record.start_time / 1000, record.end_time / 1000)
        if timing is None:
            timing = resolve_timing(source, record.start_time / 1000)
    identifier = f"record:{record_index}" if id is None else id
    lifetime = display
    styles = document.styles
    runs = _guide_runs(source.runs, guide_markers) if guide_markers else iter(source.runs)
    groups = groupby(runs, key=lambda run: (
        _shape_key(styles[run.appearance.style]),
        run.start if run.text in guide_markers else None,
    ))
    items: list[PositionedText] = []
    x = 0.0
    for (shape_key, marker), grouped in groups:
        group = tuple(grouped)
        style = styles[group[0].appearance.style]
        # Only the host font em and baseline are needed for an authored vector.
        text = "M" if marker is not None else "".join(run.text for run in group)
        try:
            for run in group:
                _style_supported(styles[run.appearance.style])
            width, height, descent, measured = _measure_run(shape_key, text, x, palt)
        except LayoutCapabilityError as error:
            raise LayoutCapabilityError(
                f"record {record_index}, decoded text range {group[0].start}:{group[-1].end}, "
                f"style {style.name!r}: {error}"
            ) from error
        for character in measured:
            start, end = (
                group[0].start + character.source.start,
                group[0].start + character.source.end,
            )
            covered = [run for run in group if run.start < end and run.end > start]
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
            shadow_alpha = next(
                (_packed_color(value) >> 24 for key, value in source_style.fields.items()
                 if key.lower() == "backcolour"),
                0,
            )
            if source_style.shadow and shadow_alpha < 255 and appearance.shadow != Color(0, 0, 0):
                raise LayoutCapabilityError(
                    "colored shadows require separate shadow-color lowering"
                )
            origin = EventOrigin((SourceRef(identifier, len(items)),), "document text")
            obj = TextObject(
                id=f"{identifier}/text:{start}:{end}",
                text=character.text if marker is None else group[0].text,
                lifetime=lifetime,
                font=style.fontname,
                font_size=style.fontsize,
                bold=style.bold,
                italic=style.italic,
                spacing=style.spacing,
                encoding=style.encoding,
                state=VisualState(
                    position=Vec2(character.box.left, character.box.top) + character.pen_offset,
                    scale=Vec2(style.scale_x / 100, style.scale_y / 100),
                    fill=appearance.primary,
                    outline=appearance.outline,
                    border=source_style.outline,
                    shadow=Vec2(source_style.shadow, source_style.shadow),
                    shadow_opacity=1 - shadow_alpha / 255,
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
                    source_style=appearance.style,
                )
            )
        x += width
    return TextLayout(
        identifier,
        record_index,
        source,
        lifetime,
        tuple(items),
        timing,
        _union(tuple(item.bounds for item in items)),
        _palt=palt,
    )


def layout_document_text(
    document: Document,
    record_index: int,
    *,
    id: str | None = None,
    display: Lifetime | None = None,
) -> TextLayout:
    """Bind a plain line; use layout_document_lyrics for ruby/continuations."""
    source = document.text_at(record_index)
    if any(character in source.text for character in "\n\r|｜#＃"):
        raise LayoutCapabilityError(
            "this text binder handles a single plain line; ruby/continuations require the lyric binder"
        )
    return _layout_document_view(document, source, record_index, id=id, display=display)
