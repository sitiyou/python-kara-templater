"""Inline and independently positioned count-in components using ordinary objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Literal, Protocol

from .appearance import PaintPair
from .ass import Style
from .colors import CYAN, WHITE
from .composition import Color, Paint
from .document_text import CueMarker
from .geometry import Vec2, VectorPath, finite
from .layout import text_extents
from .lyric_highlights import LyricGradient
from .scene import (
    Lifetime,
    ObjectGroup,
    PathObject,
    SceneObject,
    TextObject,
    VisualNode,
)
from .scene_animation import AnimationClip, StateFunction, VisualState
from .scene_lyrics import LyricLayout, PositionedRuby, _move
from .scene_text import DocumentLayout, PositionedText, _union
from .sources import EventOrigin, SourceRef

_DEFAULT_COLORS = PaintPair(
    Paint(WHITE, Color(34, 34, 34)), Paint(Color(255, 90, 111), Color(34, 34, 34))
)


@dataclass(frozen=True)
class CueContext:
    """Factory input containing a stable cue ID, absolute seconds lifetime, absolute step boundaries, and source origin.

    Factories create local objects for that interval. host is the measured text
    cluster at the marker (the final cluster for an end marker), when available. colors supplies the before/after paint for the first nonblank role.
    role_em is that role’s measured em in script pixels. base_gradient and gradient supply its unsung and sung fill ramps.
    zoom_pulse_curve_level selects the lyric zoom curve for cue steps, or None for steady size.
    """

    id: str
    lifetime: Lifetime
    steps: tuple[float, ...]
    origin: EventOrigin
    host: TextObject | None = None
    host_em: float | None = None
    colors: PaintPair = _DEFAULT_COLORS
    zoom_pulse_curve_level: int | None = None
    role_em: float | None = None
    gradient: LyricGradient | None = None
    base_gradient: LyricGradient | None = None


@dataclass(frozen=True)
class CueContent:
    """Local objects plus the explicit layout space the author wants to reserve."""

    objects: tuple[SceneObject, ...]
    width: float
    height: float

    def __post_init__(self) -> None:
        finite(self.width, self.height)
        if self.width < 0 or self.height < 0:
            raise ValueError("cue dimensions cannot be negative")


@dataclass(frozen=True)
class _SharedGradientCue(CueContent):
    """A cue whose fill can use the lyric span once all inline slots are measured."""

    ink_left: float
    paint_span: Callable[[float, float], tuple[SceneObject, ...]]


class CueFactory(Protocol):
    """A typed callable that maps CueContext to local CueContent.

    Implement it with an ordinary function or callable object to customize cue text,
    geometry, and animation.
    """

    def __call__(self, context: CueContext, /) -> CueContent:
        """Return custom local objects and reserved dimensions for the supplied cue context."""
        ...


@dataclass(frozen=True, kw_only=True)
class CuePreset:
    """A cue factory with lead/duration in seconds, normalized step fractions, gap, position, and reservation policy.

    On a Track, line_edge places an independent cue above or below the measured
    lyric row (including ruby), reserves its dimensions and applies gap in pixels.
    With no line_edge, independent cues use absolute position.
    An explicit trigger overrides the relevant singing interval default. colors fixes
    the cue fill and outline pair across hosts. Omit it to follow the lyric palette.
    """

    factory: CueFactory
    lead: float = 1
    duration: float = 1
    steps: tuple[float, ...] = (0, 1 / 3, 2 / 3, 1)
    gap: float = 12
    position: Vec2 = Vec2()
    line_edge: Literal["above", "below"] | None = None
    keep_space: bool = True
    trigger: float | None = None
    colors: PaintPair | None = None

    def __post_init__(self) -> None:
        if self.line_edge not in (None, "above", "below"):
            raise ValueError("line_edge must be above or below")
        finite(self.lead, self.duration, self.gap, *self.steps)
        if self.trigger is not None:
            finite(self.trigger)
        if self.lead < 0 or self.duration <= 0 or self.gap < 0:
            raise ValueError("cue lead/gap must be nonnegative and duration positive")
        if (
            len(self.steps) < 2
            or self.steps[0] != 0
            or self.steps[-1] != 1
            or any(a >= b for a, b in zip(self.steps, self.steps[1:], strict=False))
        ):
            raise ValueError("cue steps must increase strictly from 0 to 1")


@dataclass(frozen=True)
class BarsCue:
    """A CueFactory producing a stepwise bar countdown from vector objects.

    Width, height, border, and colors are explicit and the returned content reserves
    its own layout dimensions.
    """

    width: float = 72
    height: float = 48
    color: Color = CYAN
    border: float = 2
    outline: Color = WHITE

    direction: Literal["left_to_right", "right_to_left"] = "left_to_right"

    def __call__(self, context: CueContext) -> CueContent:
        """Create local bar objects and explicit reserved dimensions for the supplied cue clock."""
        count = len(context.steps) - 1
        cell = self.width / count
        objects: list[SceneObject] = []
        ends = context.steps[1:] if self.direction == "left_to_right" else tuple(reversed(context.steps[1:]))
        for index, end in enumerate(ends):
            height = self.height * (1 - 0.5 * index / count)
            objects.append(
                PathObject(
                    id=f"{context.id}/bar:{index}",
                    lifetime=Lifetime(context.lifetime.start, end),
                    path=VectorPath.rectangle(cell * 0.45, height),
                    state=VisualState(
                        position=Vec2(index * cell, (self.height - height) / 2),
                        fill=self.color,
                        outline=self.outline,
                        border=self.border,
                    ),
                    origin=context.origin,
                )
            )
        return CueContent(tuple(objects), self.width, self.height)


@dataclass(frozen=True)
class TextCue:
    """A CueFactory displaying configurable countdown text for each step.

    It measures the requested font and returns objects plus explicit reserved width
    and height.
    """

    labels: tuple[str, ...] = ("3", "2", "1")
    font: str = "DejaVu Sans"
    font_size: float = 48
    color: Color = CYAN

    def __call__(self, context: CueContext) -> CueContent:
        """Create the configured step text objects and measured reserved dimensions for this cue."""
        if len(self.labels) != len(context.steps) - 1:
            raise ValueError("countdown labels must match the explicit step intervals")
        metrics = tuple(
            text_extents(Style(fontname=self.font, fontsize=self.font_size), label)
            for label in self.labels
        )
        width, height = (
            max(value[0] for value in metrics),
            max(value[1] for value in metrics),
        )
        objects = tuple(
            TextObject(
                id=f"{context.id}/text:{index}",
                text=label,
                font=self.font,
                font_size=self.font_size,
                lifetime=Lifetime(context.steps[index], context.steps[index + 1]),
                state=VisualState(
                    position=Vec2((width - metrics[index][0]) / 2, 0), fill=self.color
                ),
                origin=context.origin,
            )
            for index, label in enumerate(self.labels)
        )
        return CueContent(objects, width, height)


@dataclass(frozen=True)
class CuePlacement:
    """A bound marker, preset, content, and trigger placement in the lyric layout.

    It retains the data needed to reserve or release inline space.
    """

    marker: CueMarker
    content: CueContent
    preset: CuePreset
    lifetime: Lifetime
    position: Vec2


@dataclass(frozen=True)
class CuedLayout:
    """A plain-text layout after cue binding, with inline and independent cue groups.

    Its group combines the adjusted text and reserved-space behavior.
    """

    text: DocumentLayout
    cues: tuple[CuePlacement, ...]
    inline: tuple[ObjectGroup, ...]
    independent: tuple[ObjectGroup, ...]

    def group(self, *, position: Vec2 | None = None) -> ObjectGroup:
        """Only inline cues follow this lyric group; independent cues stay separate."""
        starts = [
            self.text.lifetime.start,
            *(node.lifetime.start for node in self.inline),
        ]
        ends = [self.text.lifetime.end, *(node.lifetime.end for node in self.inline)]
        return ObjectGroup(
            id=self.text.id,
            lifetime=Lifetime(min(starts), max(ends)),
            state=VisualState(position=Vec2() if position is None else position),
            children=(
                *tuple(item.object for item in self.text.characters),
                *self.inline,
            ),
        )


def _stamp(node: SceneObject, origin: EventOrigin) -> SceneObject:
    if isinstance(node, ObjectGroup):
        return replace(
            node,
            origin=origin if node.origin is None else node.origin,
            children=tuple(_stamp(child, origin) for child in node.children),
        )
    return replace(node, origin=origin if node.origin is None else node.origin)


def bind_cues(
    layout: DocumentLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
) -> CuedLayout:
    """Bind input markers or equivalent Python values to the same object model.

    Defaults trigger at the first singing interval; there is no inferred beat.
    A preset can supply an absolute trigger. Inline reservations are included in
    range/background measurements and optionally released after the cue ends.
    """
    markers = layout.source.cues if markers is None else markers
    if len({marker.id for marker in markers}) != len(markers):
        raise ValueError("duplicate cue identity")
    boundaries = {
        0,
        len(layout.source.text),
        *(item.start for item in layout.characters),
        *(item.end for item in layout.characters),
    }
    direction = -1 if layout._right_to_left else 1
    placements: list[CuePlacement] = []
    inline: list[ObjectGroup] = []
    independent: list[ObjectGroup] = []
    first = next((run.appearance for run in layout.source.runs if run.text.strip()), None)
    role = next((g for g in layout.characters if g.object.text.strip()), None)
    border = role.object.state.border if role else 0
    colors = (
        PaintPair(Paint(first.secondary, first.outline, border), Paint(first.primary, first.outline, border))
        if first else _DEFAULT_COLORS
    )
    for marker in sorted(markers, key=lambda marker: marker.offset):
        if marker.offset not in boundaries:
            raise ValueError(
                f"record {layout.record_index}, cue {marker.id}: anchor splits a cluster or is outside the text"
            )
        if marker.preset not in presets:
            raise ValueError(
                f"record {layout.record_index}, cue {marker.id}: unknown preset {marker.preset!r}"
            )
        preset = presets[marker.preset]
        if preset.trigger is None:
            trigger = min(
                (
                    span.start
                    for span in layout.singing
                    if span.end_offset > span.start_offset
                ),
                default=None,
            )
            if trigger is None:
                raise ValueError(
                    f"cue {marker.id}: supply an absolute trigger for untimed text"
                )
        else:
            trigger = preset.trigger
        start = trigger - preset.lead
        lifetime = Lifetime(start, start + preset.duration)
        identifier = f"{layout.id}/cue:{marker.id}"
        origin = EventOrigin((SourceRef(layout.id),), f"cue {marker.id}")
        host = next(
            (glyph for glyph in layout.characters if glyph.start == marker.offset),
            layout.characters[-1] if layout.characters else None,
        )
        context = CueContext(
            identifier,
            lifetime,
            tuple(start + step * preset.duration for step in preset.steps),
            origin,
            host.object if host is not None else None,
            host.em_size if host is not None else None,
            preset.colors or colors,
            role_em=role.em_size if role else None,
        )
        content = preset.factory(context)
        for node in content.objects:
            if node.lifetime.start < lifetime.start or node.lifetime.end > lifetime.end:
                raise ValueError(
                    f"cue {marker.id}: factory objects must fit the declared lifetime"
                )
        if marker.placement == "inline":
            base_x = next(
                (
                    item.bounds.right if layout._right_to_left else item.bounds.left
                    for item in layout.characters
                    if item.start == marker.offset
                ),
                layout.bounds.left if layout._right_to_left else layout.bounds.right,
            )
            preceding_width = sum(
                p.content.width + p.preset.gap
                for p in placements
                if p.marker.placement == "inline" and p.marker.offset <= marker.offset
            )
            position = Vec2(
                base_x + direction * preceding_width - (content.width if layout._right_to_left else 0), (layout.bounds.height - content.height) / 2
            )
        else:
            position = preset.position
        placement = CuePlacement(marker, content, preset, lifetime, position)
        placements.append(placement)
        group = ObjectGroup(
            id=identifier,
            lifetime=lifetime,
            state=VisualState(position=position),
            children=tuple(_stamp(node, origin) for node in content.objects),
            origin=origin,
        )
        (inline if marker.placement == "inline" else independent).append(group)
    characters: list[PositionedText] = []
    for item in layout.characters:
        reservations = [
            p
            for p in placements
            if p.marker.placement == "inline" and p.marker.offset <= item.start
        ]
        dx = direction * sum(p.content.width + p.preset.gap for p in reservations)
        obj = item.object.copy(id=item.object.id, offset=Vec2(dx, 0))
        obj = _released(obj, tuple(reservations), direction=direction)
        box = replace(item.bounds, left=item.bounds.left + dx)
        ink = (
            None
            if item.ink_bounds is None
            else replace(item.ink_bounds, left=item.ink_bounds.left + dx)
        )
        characters.append(replace(item, object=obj, bounds=box, ink_bounds=ink))
    body_bounds = _union(tuple(item.bounds for item in characters))
    inline_placements = tuple(p for p in placements if p.marker.placement == "inline")
    shared = {
        p.marker.id: p.position.x + (p.content.width - p.content.ink_left
                                     if layout._right_to_left else p.content.ink_left)
        for p in inline_placements
        if p.marker.offset == 0 and isinstance(p.content, _SharedGradientCue) and characters
    }
    role_boxes = [g.bounds for g in characters if role and g.source_style == role.source_style]
    gradient_left = min(shared.values(), default=body_bounds.left)
    gradient_right = max((b.right for b in role_boxes), default=body_bounds.right)
    if layout._right_to_left:
        gradient_right = max(shared.values(), default=body_bounds.right)
        gradient_left = min((b.left for b in role_boxes), default=body_bounds.left)
    painted: dict[str, CuePlacement] = {}
    for index, placement in enumerate(inline_placements):
        content = placement.content
        if placement.marker.id in shared and isinstance(content, _SharedGradientCue):
            x = placement.position.x
            objects = content.paint_span(gradient_left - x, gradient_right - x)
            painted[placement.marker.id] = replace(placement, content=replace(content, objects=objects))
            inline[index] = replace(inline[index], children=objects)
    placements = [painted.get(p.marker.id, p) for p in placements]
    inline = [
        _released(group, inline_placements[:index], direction=direction)
        for index, group in enumerate(inline)
    ]
    bound = replace(
        layout,
        characters=tuple(characters),
        bounds=body_bounds,
        _cue_gradient_edge=(gradient_right if layout._right_to_left else gradient_left) if shared else None,
    )
    return CuedLayout(bound, tuple(placements), tuple(inline), tuple(independent))


def _released[T: VisualNode](
    node: T,
    reservations: tuple[CuePlacement, ...],
    *,
    weights: tuple[float, ...] | None = None,
    direction: int = 1,
) -> T:
    releases: dict[float, float] = {}
    weights = (1.0,) * len(reservations) if weights is None else weights
    for placement, weight in zip(reservations, weights, strict=True):
        if (
            not placement.preset.keep_space
            and placement.lifetime.end < node.lifetime.end
        ):
            time = max(0, placement.lifetime.end - node.lifetime.start)
            releases[time] = (
                releases.get(time, 0)
                + direction * (placement.content.width + placement.preset.gap) * weight
            )
    animations = list(node.animations)
    times = sorted(releases)
    for index, time in enumerate(times):

        def release(
            state: VisualState, progress: float, shift: float = releases[time]
        ) -> VisualState:
            return replace(state, position=state.position - Vec2(shift, 0))

        next_time = (
            times[index + 1]
            if index + 1 < len(times)
            else node.lifetime.end - node.lifetime.start
        )
        animations.append(
            AnimationClip(
                time,
                min(0.01, next_time - time),
                StateFunction(release, frozenset(("position",))),
            )
        )
    return replace(node, animations=tuple(animations))


@dataclass(frozen=True)
class CuedLyrics:
    """Body/ruby with shared cue reservations; independent cues remain separate."""

    lyrics: LyricLayout
    cues: tuple[CuePlacement, ...]
    inline: tuple[ObjectGroup, ...]
    independent: tuple[ObjectGroup, ...]

    def group(self, *, position: Vec2 | None = None) -> ObjectGroup:
        """Build the adjusted body, readings, and cue content as one editable object hierarchy."""
        group = self.lyrics.group(position=position)
        return replace(
            group,
            lifetime=Lifetime(
                min(
                    group.lifetime.start, *(node.lifetime.start for node in self.inline)
                ),
                max(group.lifetime.end, *(node.lifetime.end for node in self.inline)),
            )
            if self.inline
            else group.lifetime,
            children=(*group.children, *self.inline),
        )


def bind_lyric_cues(
    layout: LyricLayout,
    presets: Mapping[str, CuePreset],
    *,
    markers: tuple[CueMarker, ...] | None = None,
) -> CuedLyrics:
    """Reserve/release body space and translate associated ruby by the same rule.

    Markers use projected body offsets. A reservation inside a body unit moves
    its ruby by half the reserved width, keeping its original center offset from
    the expanded body box; before a unit it moves ruby by the full width.
    """
    bound = bind_cues(layout.body, presets, markers=markers)
    ruby_items: list[PositionedRuby] = []
    for ruby in layout.ruby:
        reservations = tuple(
            p
            for p in bound.cues
            if p.marker.placement == "inline" and p.marker.offset < ruby.body_end
        )
        weights = tuple(
            1.0 if p.marker.offset <= ruby.body_start else 0.5 for p in reservations
        )
        direction = -1 if layout.body._right_to_left else 1
        dx = direction * sum(
            (p.content.width + p.preset.gap) * weight
            for p, weight in zip(reservations, weights, strict=True)
        )
        moved = _move(ruby.layout, dx, 0)
        moved = replace(
            moved,
            characters=tuple(
                replace(
                    item, object=_released(item.object, reservations, weights=weights, direction=direction)
                )
                for item in moved.characters
            ),
        )
        ruby_items.append(replace(ruby, layout=moved))
    lyrics = replace(
        layout,
        body=bound.text,
        ruby=tuple(ruby_items),
        bounds=_union(
            (bound.text.bounds, *(ruby.layout.bounds for ruby in ruby_items))
        ),
    )
    return CuedLyrics(lyrics, bound.cues, bound.inline, bound.independent)
