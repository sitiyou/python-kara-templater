"""Lyric semantics bound to ordinary visual nodes and AnimationClips."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Literal, Self

from .characters import LayoutCapabilityError
from .document_text import SingingSpan
from .geometry import Vec2, finite
from .model import Box
from .parameters import LengthExpr, TimeExpr
from .scene import Lifetime, ObjectGroup, RectangleClip, RectangleKeyframes, SceneObject
from .scene_animation import (
    AnimationClip,
    AnimationSequence,
    StateAnimation,
    TimeSpan,
    _resolve_pivot,
    local_seconds,
)
from .scene_lyrics import LyricLayout, _reading_intervals
from .scene_text import DocumentLayout, PositionedText

type LyricRole = Literal["line", "syllable", "segment", "character", "ruby", "cue"]
_LYRIC_ROLES = frozenset(("line", "syllable", "segment", "character", "ruby", "cue"))
type LyricAnchor = Literal["enter", "exit", "singing", "after_singing"]


def _line_x(character: PositionedText, left: float, right: float) -> tuple[float, float]:
    assert character.layout_scale is not None
    origin, scale = character.object.state.position.x, character.layout_scale.x
    return (left - origin) / scale, (right - origin) / scale


def _cell_left(character: PositionedText, layout: LyricLayout) -> float:
    if layout._vertical:
        return 0
    assert character.layout_scale is not None
    return (character.bounds.left - character.object.state.position.x) / character.layout_scale.x


def _character_center(character: PositionedText) -> Vec2:
    assert character.layout_scale is not None
    return Vec2(
        (character.bounds.center - character.object.state.position.x) / character.layout_scale.x,
        character.bounds.height / character.layout_scale.y / 2,
    )


@dataclass(frozen=True)
class LyricTarget:
    """Stable semantic identity referring to an existing visual node.

    Several repeated singing segments may refer to the same body node. Selecting
    them never creates copies or changes visual parentage. singing retains the
    original absolute seconds and decoded text offsets.
    center is the undecorated measured center in the node's local coordinates.
    Line/syllable centers use body text, so ruby/glow do not shift the pivot.
    source_style is the body cluster's active ASS style, inherited by its readings.
    A factory changing a target's local coordinate origin must update center too.
    """

    id: str
    node_id: str
    role: LyricRole
    singing: tuple[SingingSpan, ...] = ()
    tags: frozenset[str] = frozenset()

    delay: float = 0
    aliases: tuple[str, ...] = ()
    center: Vec2 = Vec2()
    baseline: float | None = None
    em_size: float | None = None
    source_style: str | None = None
    font_size: float | None = None
    _line_x: tuple[float, float] | None = field(default=None, repr=False)
    _reading_span: SingingSpan | None = field(default=None, repr=False)
    _cell_left: float = field(default=0, repr=False)

    @property
    def _baseline_pivot(self) -> Vec2:
        """Scale about the horizontal cell edge, including any offset from the font pen."""
        return self.center if self.baseline is None else Vec2(self._cell_left, self.baseline)

    def _visual_singing(self) -> tuple[SingingSpan, ...]:
        return (self._reading_span,) if self._reading_span else self.singing


@dataclass(frozen=True)
class LyricAnimationContext:
    """Measured target and current timing request for an animation factory.

    interval contains absolute seconds, including a visual copy's delay, before
    rule offset/stagger. It is None for display-relative enter/exit, whose final
    times depend on allocation. target retains all original singing spans.
    requested_duration is the rule's optional explicit override. Factories run
    once per resolved interval (once per target for display anchors), never per
    rendered frame. Return an ordinary StateAnimation or AnimationSequence.
    """

    line: LyricLine
    target: LyricTarget
    interval: TimeSpan | None
    requested_duration: float | None = None
    note_duration: float | None = None

    def resolve(self, expression: LengthExpr | TimeExpr) -> float:
        """Read a relative parameter from the same facts used for declarative binding."""
        if isinstance(expression, LengthExpr):
            return expression._pixels(self.target.font_size, self.line.layout.script_height, self.target.id)
        seconds = self.requested_duration if self.requested_duration is not None else (
            self.interval.duration if self.interval is not None else None
        )
        return expression._seconds(self.note_duration, seconds, self.target.id)

    @property
    def duration(self) -> float:
        """Requested seconds, or the current interval's length including zero.

        Raises ValueError for a display anchor without an explicit duration.
        Such a factory can return an authored sequence without reading duration.
        This value excludes gaps between repeated singing intervals.
        """
        if self.requested_duration is not None:
            return self.requested_duration
        if self.interval is not None:
            return self.interval.duration
        raise ValueError("display animation factory has no requested duration")


@dataclass(frozen=True)
class LyricRule:
    """Bind a common animation to selected lyric nodes at a semantic anchor.

    enter/exit use the node's display start/end; exit ends at the anchor.
    singing binds each selected singing interval. An omitted duration uses a
    sequence's authored length, or otherwise the singing interval's length.
    after_singing starts at the selected target's last singing end and requires
    a duration or sequence length. Select segment to trigger after each repeat,
    character to trigger only after that character's final singing interval.
    A factory receives a LyricAnimationContext once per resolved interval,
    before layout, and returns the same animation protocol as direct authoring.
    Repeated singing intervals can therefore choose different amplitudes/curves.
    duration and offset accept relative time expressions. Note.duration uses the
    selected note (the final note for after_singing); Animation.duration can
    supply an offset once the animation length is bound.
    offset is relative seconds; display-anchor factories must return a sequence
    when duration is omitted.
    stagger adds nonnegative seconds between targets in selection order. For
    exit, the last target ends at the display end (plus offset); earlier targets
    finish earlier. Other anchors shift later targets forward from their own
    anchor, so singing with stagger deliberately offsets original singing clocks.
    A callable anchor receives the measured line and target and returns absolute
    second intervals, before layout occupancy is allocated. This permits custom
    arrival clocks without adding another animation evaluator. Returned intervals
    already include any visual copy delay.
    No state interpolation or ASS encoding occurs in this declaration.
    target accepts a role, a queried semantic target, or a tuple of targets.
    Explicit targets must belong to the receiving line; current aliases are
    resolved at binding. Duplicate selections and selected descendants are
    suppressed. Role/tag queries and empty tuples may select nothing.
    """

    target: LyricRole | LyricTarget | tuple[LyricTarget, ...]
    anchor: (
        LyricAnchor
        | LyricTarget
        | Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]]
    )
    animation: StateAnimation | Callable[[LyricAnimationContext], StateAnimation]
    duration: float | TimeExpr | None = None
    offset: float | TimeExpr = 0
    hold: bool = True
    tags: frozenset[str] = frozenset()
    stagger: float = 0

    def __post_init__(self) -> None:
        finite(self.stagger)
        if not isinstance(self.offset, TimeExpr):
            finite(self.offset)
        if self.stagger < 0:
            raise ValueError("lyric stagger must be nonnegative seconds")
        if isinstance(self.target, str):
            if self.target not in _LYRIC_ROLES:
                raise ValueError("unknown lyric target")
        elif not isinstance(self.target, LyricTarget) and not (
            isinstance(self.target, tuple)
            and all(isinstance(target, LyricTarget) for target in self.target)
        ):
            raise TypeError(
                "lyric target must be a role, semantic target, or target tuple"
            )
        if isinstance(self.anchor, str) and self.anchor not in (
            "enter",
            "exit",
            "singing",
            "after_singing",
        ):
            raise ValueError("unknown lyric anchor")
        if isinstance(self.anchor, LyricTarget) and not self.anchor.singing:
            raise ValueError("referenced lyric anchor has no singing intervals")
        if self.duration is None:
            if (
                isinstance(self.anchor, str)
                and self.anchor != "singing"
                and isinstance(self.animation, StateAnimation)
                and not isinstance(self.animation, AnimationSequence)
            ):
                raise ValueError("display/after_singing anchors require an explicit duration")
        elif not isinstance(self.duration, TimeExpr):
            finite(self.duration)
            if self.duration <= 0:
                raise ValueError("lyric animation duration must be positive")

    def singing_intervals(self, target: LyricTarget) -> tuple[TimeSpan, ...]:
        """Resolve source clocks, optionally from an explicit other-track target.

        A referenced target is an immutable snapshot of its source singing and
        visual delay, independent of input ordering or runtime evaluation order.
        Display anchors are resolved separately from the actual target lifetime.
        """
        source = self.anchor if isinstance(self.anchor, LyricTarget) else target
        intervals = tuple(
            TimeSpan(span.start + source.delay, span.end + source.delay)
            for span in source.singing
        )
        if self.anchor == "after_singing" and intervals:
            end = max(span.end for span in intervals)
            return (TimeSpan(end, end),)
        return intervals


@dataclass(frozen=True)
class _LyricBinding:
    target: LyricTarget
    animation: StateAnimation
    at: float | Literal["enter", "exit"]
    duration: float
    offset: float
    hold: bool

    flexible: bool = False
    fit_end: Literal["display", "before_exit"] | None = None

    def retarget(self, names: Mapping[str, str], delay: float) -> _LyricBinding:
        target = self.target
        if target.node_id in names:
            target = replace(
                target,
                id=names[target.node_id] + target.id[len(target.node_id) :],
                node_id=names[target.node_id],
                aliases=tuple(names.get(name, name) for name in target.aliases),
                delay=target.delay + delay,
            )
        return replace(
            self,
            target=target,
            at=self.at + delay if isinstance(self.at, (int, float)) else self.at,
        )

    def clip(self, node: SceneObject) -> AnimationClip:
        start = (
            node.lifetime.start
            if self.at == "enter"
            else node.lifetime.end - self.duration
            if self.at == "exit"
            else self.at
        )
        assert isinstance(start, (int, float))
        start += self.offset
        local_start = local_seconds(start, node.time_origin)
        local_end = local_seconds(start + self.duration, node.time_origin)
        duration = self.duration
        if local_end > local_start and local_seconds(local_start + duration, 0) != local_end:
            duration = local_seconds(local_end, local_start)
        return AnimationClip(
            local_start,
            duration,
            self.animation,
            self.hold,
        )


@dataclass(frozen=True, kw_only=True)
class LyricLine(ObjectGroup):
    """An editable lyric line, with the same animate method as any visual node.

    Body and ruby belong to syllable groups, so whole-line and syllable animation
    compose through the ordinary Scene hierarchy. track_index counts lines in
    singing order within the selected track, starting at zero. query is a logical selection;
    it never reparents objects. The original measured layout remains available.
    required_display declares absolute-seconds visual intervals for allocation;
    it does not move the original singing clocks or create animation events.
    """

    layout: LyricLayout
    targets: tuple[LyricTarget, ...]
    independent: tuple[ObjectGroup, ...] = ()
    track_index: int = 0
    required_display: tuple[TimeSpan, ...] = ()
    _fit_display: bool = field(default=False, repr=False, compare=False)
    _flexible_end: float = field(default=0, repr=False, compare=False)
    _optional_display: tuple[TimeSpan, ...] = field(default=(), repr=False, compare=False)
    _optional_objects: frozenset[str] = field(default=frozenset(), repr=False, compare=False)
    _scheduled: tuple[_LyricBinding, ...] = field(default=(), repr=False)
    _at_placement: tuple[Callable[[LyricLine, float, float], LyricLine], ...] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if any(span.start < 0 or span.duration <= 0 for span in self.required_display):
            raise ValueError(
                "required display intervals must be positive absolute intervals"
            )

    @classmethod
    def from_layout(
        cls,
        layout: LyricLayout,
        *,
        tags: frozenset[str] = frozenset(),
        inline: tuple[ObjectGroup, ...] = (),
        independent: tuple[ObjectGroup, ...] = (),
        track_index: int = 0,
    ) -> LyricLine:
        """Build a line from shaped text, retaining repeat and ruby associations.

        Independent syllable animation requires boundaries that do not split a
        shaping cluster. Such boundaries fail explicitly, never split codepoints.
        """
        body = layout.body
        # Studio shares one ink span across all appearances of the same role.
        style_spans: dict[str | None, tuple[float, float]] = {}
        fallback = body.bounds.left, body.bounds.right
        for glyph in body.characters:
            ink = glyph.ink_bounds
            if ink is not None and ink.width:
                left, right = style_spans.get(glyph.source_style, (ink.left, ink.right))
                style_spans[glyph.source_style] = min(left, ink.left), max(right, ink.right)
        if body._cue_gradient_edge is not None:
            first = next((g for g in body.characters if g.object.text.strip()), None)
            if first is not None:
                left, right = style_spans.get(first.source_style, fallback)
                style_spans[first.source_style] = (
                    min(left, body._cue_gradient_edge), max(right, body._cue_gradient_edge),
                )
        line_interval = (
            ()
            if not body.singing
            else (
                replace(
                    body.singing[0],
                    start=min(span.start for span in body.singing),
                    end=max(span.end for span in body.singing),
                ),
            )
        )
        targets = [LyricTarget(
            body.id, body.id, "line", line_interval, tags,
            center=Vec2(body.bounds.center, body.bounds.middle),
            em_size=body.characters[0].em_size if body.characters else None,
        )]
        children: list[SceneObject] = []
        assigned: set[str] = set()
        for index, unit in enumerate(layout.lyrics.units):
            if unit.start == unit.end:
                continue
            for character in body.characters:
                if (
                    character.start < unit.end
                    and character.end > unit.start
                    and not (
                        unit.start <= character.start and character.end <= unit.end
                    )
                ):
                    raise LayoutCapabilityError(
                        "syllable boundary splits a shaped cluster"
                    )
            group = layout.unit_group(index)
            children.append(group)
            assigned.update(node.id for node in group.children)
            spans = tuple(segment.singing for segment in unit.segments)
            interval = (
                ()
                if not spans
                else (
                    replace(
                        spans[0],
                        start=min(span.start for span in spans),
                        end=max(span.end for span in spans),
                    ),
                )
            )
            targets.append(LyricTarget(group.id, group.id, "syllable", interval, tags))
            for si, segment in enumerate(unit.segments):
                targets.append(
                    LyricTarget(
                        f"{group.id}/segment:{si}",
                        group.id,
                        "segment",
                        (segment.singing,),
                        tags,
                    )
                )
            for character in body.characters:
                if (
                    character.object.id in assigned
                    and unit.start <= character.start < unit.end
                ):
                    targets.append(
                        LyricTarget(
                            character.object.id,
                            character.object.id,
                            "character",
                            spans,
                            tags,
                            center=_character_center(character),
                            source_style=character.source_style, font_size=character.object.font_size,
                            _line_x=_line_x(character, *style_spans.get(character.source_style, fallback)),
                            baseline=character.baseline, em_size=character.em_size,
                            _cell_left=_cell_left(character, layout),
                        )
                    )
            for ruby in layout.ruby:
                if ruby.unit_index == index:
                    style = next((c.source_style for c in body.characters
                                  if c.start <= ruby.body_start < c.end), None)
                    for character, span in zip(ruby.layout.characters, _reading_intervals(ruby, unit), strict=True):
                        targets.append(
                            LyricTarget(
                                character.object.id,
                                character.object.id,
                                "ruby",
                                (unit.segments[ruby.segment_index].singing,),
                                tags,
                                _reading_span=span,
                                center=_character_center(character),
                                source_style=style, font_size=character.object.font_size,
                                _line_x=_line_x(character, *style_spans.get(style, fallback)),
                                baseline=character.baseline, em_size=character.em_size,
                                _cell_left=_cell_left(character, layout),
                            )
                        )
        # Untimed/unassigned drawable text is retained as ordinary children.
        children.extend(
            item.object for item in body.characters if item.object.id not in assigned
        )
        children.extend(inline)
        targets.extend(
            LyricTarget(cue.id, cue.id, "cue", (), tags)
            for cue in (*inline, *independent)
        )
        return cls(
            id=body.id,
            lifetime=body.lifetime,
            children=tuple(children),
            layout=layout,
            targets=tuple(targets),
            independent=independent,
            track_index=track_index,
        )

    def with_display(self, display: Lifetime) -> LyricLine:
        """Change shared lyric visibility while preserving all existing local clocks.

        Nodes with this line's original window follow the change. Independently
        timed decorations and independent cues retain their own windows.
        """
        previous = self.lifetime

        def adjust(node: SceneObject) -> SceneObject:
            # Rebuild children first, then validate the parent's updated window.
            children = (
                tuple(adjust(child) for child in node.children)
                if isinstance(node, ObjectGroup)
                else ()
            )
            if node.lifetime == previous:
                mask = node.clip
                limit = display.end - node.time_origin
                if isinstance(mask, RectangleClip) and isinstance(mask.deform, RectangleKeyframes):
                    keys = mask.deform
                    if keys.keyframes[-1][0] > limit:
                        prefix = tuple(k for k in keys.keyframes if k[0] <= limit)
                        if not prefix or prefix[-1][0] < limit:
                            prefix = (*prefix, (limit, keys.bounds_at(limit)))
                        mask = replace(mask, deform=RectangleKeyframes(prefix))
                result = replace(node, lifetime=display, clock_start=node.time_origin, clip=mask)
            else:
                result = node
            return (
                replace(result, children=children)
                if isinstance(result, ObjectGroup)
                else result
            )

        def measured(layout: DocumentLayout) -> DocumentLayout:
            return replace(
                layout,
                lifetime=display,
                characters=tuple(
                    replace(
                        item,
                        object=replace(
                            item.object,
                            lifetime=display,
                            clock_start=item.object.time_origin,
                        ),
                    )
                    if item.object.lifetime == previous
                    else item
                    for item in layout.characters
                ),
            )

        result = adjust(self)
        assert isinstance(result, LyricLine)
        return replace(
            result,
            layout=replace(
                self.layout,
                body=measured(self.layout.body),
                ruby=tuple(
                    replace(ruby, layout=measured(ruby.layout))
                    for ruby in self.layout.ruby
                ),
            ),
        )

    @property
    def objects(self) -> tuple[ObjectGroup, ...]:
        """The line and its independently positioned cues for Scene.add."""
        return (self, *self.independent)

    def copy(self, *, id: str, offset: Vec2 | None = None, delay: float = 0) -> Self:
        """Copy visuals and retarget semantic identities, retaining original source.

        delay shifts visual anchors and lifetimes, never edits the source singing
        spans. offset moves the lyric group; independently positioned cues retain
        their own positions. Already-bound animations retain their local clocks.
        """
        copied = super().copy(id=id, offset=offset, delay=delay)
        independent = tuple(
            cue.copy(id=cue.id if id == self.id else f"{id}/{cue.id}", delay=delay)
            for cue in self.independent
        )
        names: dict[str, str] = {}

        def pair(original: SceneObject, clone: SceneObject) -> None:
            names[original.id] = clone.id
            if isinstance(original, ObjectGroup) and isinstance(clone, ObjectGroup):
                for before, after in zip(
                    original.children, clone.children, strict=True
                ):
                    pair(before, after)

        pair(self, copied)
        for before, after in zip(self.independent, independent, strict=True):
            pair(before, after)
        return replace(
            copied,
            independent=independent,
            _scheduled=tuple(
                binding.retarget(names, delay) for binding in self._scheduled
            ),
            targets=tuple(
                replace(
                    target,
                    id=names[target.node_id] + target.id[len(target.node_id) :],
                    node_id=names[target.node_id],
                    aliases=tuple(names[name] for name in target.aliases),
                    delay=target.delay + delay,
                )
                for target in self.targets
            ),
        )

    def _retarget_copy(self, names: Mapping[str, str], delay: float) -> Self:
        copied = super()._retarget_copy(names, delay)
        return replace(
            copied,
            required_display=tuple(
                TimeSpan(span.start + delay, span.end + delay)
                for span in self.required_display
            ),
            _scheduled=tuple(
                binding.retarget(names, delay) for binding in self._scheduled
            ),
            targets=tuple(
                replace(
                    target,
                    id=names[target.node_id] + target.id[len(target.node_id) :],
                    node_id=names[target.node_id],
                    aliases=tuple(names.get(name, name) for name in target.aliases),
                    delay=target.delay + delay,
                )
                if target.node_id in names
                else target
                for target in self.targets
            ),
        )

    def _glyph_regions(
        self, *, automatic: bool,
    ) -> Iterator[tuple[LyricTarget, PositionedText, int, Box]]:
        """Pair semantic targets with their timed body's or reading's sweep bounds."""
        body = self.layout.body
        for target, glyph in zip(self.query("character"), body.characters, strict=True):
            index, unit = next(
                (i, u) for i, u in enumerate(self.layout.lyrics.units)
                if u.start <= glyph.start and glyph.end <= u.end
            )
            bounds = (body._sweep_bounds(unit.start, unit.end, glyph) if automatic and not self.layout._vertical
                      else body.range_bounds(unit.start, unit.end))
            yield target, glyph, index, bounds
        readings = ((glyph, ruby) for ruby in self.layout.ruby for glyph in ruby.layout.characters)
        for target, (glyph, ruby) in zip(self.query("ruby"), readings, strict=True):
            layout = ruby.layout
            if automatic and self.layout._vertical:
                bounds = glyph.ink_bounds or glyph.bounds
            elif automatic:
                bounds = layout._sweep_bounds(glyph.start, glyph.end, glyph)
            else:
                bounds = layout.bounds
            yield target, glyph, ruby.unit_index, bounds

    def query(
        self, *roles: LyricRole, tags: frozenset[str] = frozenset()
    ) -> tuple[LyricTarget, ...]:
        """Select roles/tags without changing hierarchy; ancestors win over children.

        Multiple segment identities sharing one node are retained for their
        separate clocks. An explicitly selected ancestor suppresses descendants
        so a bulk transform cannot be applied twice through parent inheritance.
        """
        if any(role not in _LYRIC_ROLES for role in roles):
            raise ValueError("unknown lyric target role")
        selected = tuple(
            target
            for target in self.targets
            if (not roles or target.role in roles) and tags <= target.tags
        )
        return self._without_selected_ancestors(selected)

    @cached_property
    def _parent_ids(self) -> dict[str, str]:
        parents: dict[str, str] = {}

        def visit(group: ObjectGroup) -> None:
            for child in group.children:
                parents[child.id] = group.id
                if isinstance(child, ObjectGroup):
                    visit(child)

        visit(self)
        for cue in self.independent:
            visit(cue)

        return parents

    def _without_selected_ancestors(
        self, selected: tuple[LyricTarget, ...]
    ) -> tuple[LyricTarget, ...]:
        selected_nodes = {
            name for target in selected for name in (target.node_id, *target.aliases)
        }
        parents = self._parent_ids

        def has_selected_parent(node_id: str) -> bool:
            while node_id in parents:
                node_id = parents[node_id]
                if node_id in selected_nodes:
                    return True
            return False

        return tuple(
            target for target in selected if not has_selected_parent(target.node_id)
        )

    def _rule_targets(self, rule: LyricRule) -> tuple[LyricTarget, ...]:
        if isinstance(rule.target, LyricTarget):
            requested = (rule.target,)
        elif isinstance(rule.target, tuple):
            requested = rule.target
        else:
            return self.query(rule.target, tags=rule.tags)
        available = {target.id: target for target in self.targets}
        selected: dict[str, LyricTarget] = {}
        for target in requested:
            current = available.get(target.id)
            if current is None or (current.node_id, current.role) != (
                target.node_id,
                target.role,
            ):
                raise ValueError(
                    f"lyric target {target.id!r} does not belong to line {self.id!r}"
                )
            if rule.tags <= current.tags:
                # Resolve current aliases after material construction. A target
                # selected before painting still addresses all its contributions.
                selected[current.id] = current
        return self._without_selected_ancestors(tuple(selected.values()))

    def _resolve(self, rules: tuple[LyricRule, ...]) -> tuple[_LyricBinding, ...]:
        bindings: list[_LyricBinding] = []
        selections = tuple((rule, self._rule_targets(rule)) for rule in rules)
        for rule, targets in selections:
            for index, target in enumerate(targets):
                stagger = rule.stagger * (
                    index - len(targets) + 1 if rule.anchor == "exit" else index
                )
                display_anchor = rule.anchor in ("enter", "exit")
                intervals: tuple[TimeSpan | None, ...] = (
                    (None,)
                    if display_anchor
                    else rule.singing_intervals(target)
                    if isinstance(rule.anchor, (str, LyricTarget))
                    else rule.anchor(self, target)
                )
                for span in intervals:
                    note = None
                    if span is not None and (rule.anchor == "singing" or isinstance(rule.anchor, LyricTarget)):
                        note = span.duration
                    elif rule.anchor == "after_singing" and target.singing:
                        last = max(target.singing, key=lambda s: s.end)
                        note = last.end - last.start
                    duration = rule.duration
                    if isinstance(duration, TimeExpr):
                        duration = duration._seconds(note, None, f"{target.id}: LyricRule.duration")
                        if duration < 0:
                            raise ValueError(f"{target.id}: negative lyric duration")
                    animation = (
                        rule.animation
                        if isinstance(rule.animation, StateAnimation)
                        else rule.animation(LyricAnimationContext(self, target, span, duration, note))
                    )
                    animation = _resolve_pivot(animation, target.center)
                    if duration is None and isinstance(animation, AnimationSequence):
                        duration = animation.duration
                    if duration is None:
                        if span is None or rule.anchor == "after_singing":
                            raise ValueError(
                                "display/after_singing anchors require an explicit "
                                "duration or animation sequence"
                            )
                        duration = span.duration
                    offset = rule.offset
                    if isinstance(offset, TimeExpr):
                        offset = offset._seconds(note, duration, f"{target.id}: LyricRule.offset")
                    if duration > 0:
                        bindings.append(_LyricBinding(
                            target, animation,
                            span.start if span is not None
                            else "enter" if rule.anchor == "enter" else "exit",
                            duration, offset + stagger, rule.hold,
                        ))
        return tuple(bindings)

    def schedule(self, *rules: LyricRule) -> LyricLine:
        """Declare animations inside a Track effect, returning a new line.

        Factories resolve once per interval against this measured line. Track preparation
        reserves their time before layout and attaches clips after decoration
        and allocation, including any subsequently added material aliases.
        Display-relative enter/exit anchors use the final allocated lifetime.
        This method does not attach clips immediately; use bind for an already
        allocated line used directly in a Scene.
        """
        return replace(self, _scheduled=(*self._scheduled, *self._resolve(rules)))

    def bind(self, *rules: LyricRule) -> LyricLine:
        """Resolve factories and semantic clocks into ordinary immutable clips.

        Sequences retain their authored seconds length unless duration overrides
        it. Unspecified pure animations use the singing interval length. Missing
        targets and zero-duration intervals do not invent animation time.
        """
        return self._bind(self._resolve(rules))

    def _bind(self, bindings: tuple[_LyricBinding, ...]) -> LyricLine:
        if not bindings:
            return self
        nodes: dict[str, SceneObject] = {}

        def collect(node: SceneObject) -> None:
            nodes[node.id] = node
            if isinstance(node, ObjectGroup):
                for child in node.children:
                    collect(child)

        collect(self)
        for cue in self.independent:
            collect(cue)
        additions: dict[str, list[AnimationClip]] = {}
        for binding in bindings:
            for name in (binding.target.node_id, *binding.target.aliases):
                node = nodes[name]
                additions.setdefault(node.id, []).append(binding.clip(node))

        def apply(node: SceneObject) -> SceneObject:
            extra = additions.get(node.id)
            if isinstance(node, ObjectGroup):
                children = tuple(apply(child) for child in node.children)
                if not extra and all(a is b for a, b in zip(children, node.children, strict=True)):
                    return node
                return replace(
                    node,
                    animations=(*node.animations, *extra) if extra else node.animations,
                    children=children,
                )
            return replace(node, animations=(*node.animations, *extra)) if extra else node

        result = apply(self)
        assert isinstance(result, LyricLine)
        independent = tuple(apply(cue) for cue in self.independent)
        assert all(isinstance(cue, ObjectGroup) for cue in independent)
        return replace(
            result,
            independent=tuple(
                cue for cue in independent if isinstance(cue, ObjectGroup)
            ),
        )
