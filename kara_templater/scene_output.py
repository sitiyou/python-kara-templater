"""Bounded standard-ASS lowering for the shared document scene."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
from math import ceil
from urllib.parse import quote

from ._scene_clipping import (
    ClipResolver,
    ResolvedMasks,
    SceneClipError,
    rectangle_difference,
)
from ._scene_clipping import _path as _mask_path
from .ass import EVENT_FORMAT, STYLE_FORMAT, Document, Line, Style
from .composition import Color
from .geometry import LineSegment, Vec2, VectorPath, finite
from .paint_fields import PaintActivity
from .path_boolean import path_boolean
from .path_geometry import intersect_convex
from .path_motion import MoveAlong
from .scene import (
    NativeEvent,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneObject,
    TextObject,
    VectorClip,
)
from .scene_animation import (
    AnimationClip,
    AnimationSequence,
    FadeIn,
    FadeOut,
    ScalePulse,
    StatePatch,
    Tween,
    VisualState,
    linear_rate,
    local_seconds,
    merge_channels,
)
from .scene_evaluation import SceneEvaluator, SceneReferenceError, compose_states
from .sources import EventOrigin
from .text_geometry import outline_text


class SceneCompileError(ValueError):
    """An invalid scene or exceeded compilation limit with object_id and optional source origin.

    Callback causes remain available for diagnosis.
    """

    def __init__(
        self, message: str, *, object_id: str = "", origin: EventOrigin | None = None
    ) -> None:
        super().__init__(f"{object_id}: {message}" if object_id else message)
        self.object_id = object_id
        self.origin = origin
        if origin is not None:
            self.add_note(f"effect={origin.effect}; sources={origin.sources!r}")


@dataclass(frozen=True, kw_only=True)
class SceneBudget:
    """Positive whole-scene sampling and resource limits.

    Defaults bound events, bytes, active drawings, geometry, color bands, and
    boolean work; exceeding a limit raises instead of reducing quality.
    clip_error_px bounds known native rectangle-edge interpolation in screen
    pixels, including endpoint rounding, before renderer pixel quantization.
    """

    fps: int = 50
    max_events: int = 25_000
    max_bytes: int = 10 * 1024 * 1024
    max_active: int = 1_000
    max_path_points: int = 4_096
    max_bands: int = 1_024
    max_boolean_work: int = 1_000_000
    clip_error_px: float = 0.75

    def __post_init__(self) -> None:
        finite(self.clip_error_px)
        if self.clip_error_px <= 0:
            raise ValueError("clip error must be positive")
        for value in (
            self.fps,
            self.max_events,
            self.max_bytes,
            self.max_active,
            self.max_path_points,
            self.max_bands,
            self.max_boolean_work,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("scene budgets must be positive integers")
        if self.fps > 100:
            raise ValueError(
                "ASS centisecond event grid supports at most 100 samples/s"
            )


@dataclass(frozen=True)
class CoverageEstimate:
    """Callback-free coverage work counts, before pixels or ASS rectangles exist.

    frames includes declared breakpoints; target_samples is frames times drawable
    leaves. Neither predicts encoded event count, memory use, or elapsed time.
    """

    id: str
    frames: int
    target_samples: int
    max_channel_error: int


@dataclass(frozen=True)
class SceneEstimate:
    """Immutable compilation preflight delivered before frame callbacks.

    estimated_events counts ordinary/native output estimates, excluding coverage
    rectangles whose count is unknown until rendering. coverage reports their
    planned work separately. Final budgets still apply to all output.
    """

    estimated_events: int
    coverage: tuple[CoverageEstimate, ...]


@dataclass(frozen=True)
class ObjectReport:
    """Per-object output strategy, event count, source origin, sample interval, and observed geometry/band costs.

    Optional metrics apply only to relevant strategies.
    """

    id: str
    strategy: str
    events: int
    origin: EventOrigin | None
    sample_interval: float | None = None
    peak_path_points: int | None = None
    peak_bands: int | None = None
    peak_clip_points: int | None = None
    sample_times: tuple[float, ...] = ()
    max_channel_error: int = 0


@dataclass(frozen=True)
class SceneResult:
    """A newly compiled ASS Document with object reports, final cost metrics, diagnostics, and actual generated-event origins.

    Caller-owned input objects remain unchanged.
    """

    document: Document
    objects: tuple[ObjectReport, ...]
    event_count: int
    peak_active: int
    byte_count: int
    estimated_events: int
    max_time_quantization: float
    diagnostics: tuple[str, ...] = ()
    event_origins: tuple[tuple[Line, EventOrigin | None], ...] = ()


@dataclass(frozen=True)
class _Leaf:
    node: TextObject | PathObject
    parents: tuple[ObjectGroup, ...]
    start: float
    end: float
    evaluator: SceneEvaluator
    force_affine: bool = False

    @property
    def dynamic(self) -> bool:
        return bool(
            self.node.animations
            or self.evaluator.referenced(self.node.id)
            or (
                isinstance(self.node.clip, (RectangleClip, VectorClip))
                and self.node.clip.deform is not None
            )
            or (self.node.material is not None and self.node.material.breakpoints)
            or (isinstance(self.node, PathObject) and self.node.deform is not None)
            or any(parent.animations for parent in self.parents)
            or any(
                isinstance(parent.clip, (RectangleClip, VectorClip))
                and parent.clip.deform is not None
                for parent in self.parents
            )
        )

    @property
    def affine_paths(self) -> bool:
        return (
            self.force_affine
            or any(
                n.state.skew != Vec2() or min(n.state.scale.x, n.state.scale.y) <= 0
                for n in (*self.parents, self.node)
            )
            or any(p.state.scale.x != p.state.scale.y for p in self.parents)
        )

    def at(self, time: float) -> VisualState:
        return self.evaluator.at(self.node.id, time)


@dataclass(frozen=True)
class _CoverageLeaf:
    node: ObjectGroup
    parents: tuple[ObjectGroup, ...]
    start: float
    end: float


def _leaves(
    scene: Scene,
    evaluator: SceneEvaluator,
    *,
    collect_coverage: bool = True,
) -> tuple[
    tuple[_Leaf, ...],
    tuple[NativeEvent, ...],
    tuple[_CoverageLeaf, ...],
    tuple[str, ...],
]:
    leaves: list[_Leaf] = []
    native: list[NativeEvent] = []
    coverage: list[_CoverageLeaf] = []
    order: list[str] = []
    ids: set[str] = set()

    def visit(
        node: SceneObject | NativeEvent, parents: tuple[ObjectGroup, ...]
    ) -> None:
        if node.id in ids:
            raise SceneCompileError(
                "duplicate object identity or group cycle", object_id=node.id
            )
        ids.add(node.id)
        if isinstance(node, NativeEvent):
            native.append(node)
            order.append(node.id)
            return
        if isinstance(node, ObjectGroup):
            if collect_coverage and node.coverage is not None:
                start = max(n.lifetime.start for n in (*parents, node))
                end = min(n.lifetime.end for n in (*parents, node))
                if end > start:
                    coverage.append(_CoverageLeaf(node, parents, start, end))
                    order.append(node.id)
                return
            for child in node.children:
                visit(child, (*parents, node))
            return
        start = max(n.lifetime.start for n in (*parents, node))
        end = min(n.lifetime.end for n in (*parents, node))
        if end > start:
            leaves.append(_Leaf(node, parents, start, end, evaluator))
            order.append(node.id)

    for node in scene.objects:
        visit(node, ())
    return tuple(leaves), tuple(native), tuple(coverage), tuple(order)


def _native_move(leaf: _Leaf) -> bool:
    node = leaf.node
    if (
        leaf.evaluator.referenced(node.id)
        or (isinstance(node, PathObject) and node.deform is not None)
        or (node.material is not None and node.material.breakpoints)
        or (
            node.clip is not None
            and (
                node.clip.space == "local"
                or (
                    isinstance(node.clip, (RectangleClip, VectorClip))
                    and node.clip.deform is not None
                )
            )
        )
        or any(
            parent.state != VisualState()
            or parent.animations
            or parent.clip is not None
            or leaf.evaluator.referenced(parent.id)
            for parent in leaf.parents
        )
        or leaf.start != node.time_origin
        or len(node.animations) != 1
    ):
        return False
    clip = node.animations[0]
    animation = clip.animation
    return clip.hold and (
        (
            isinstance(animation, Tween)
            and animation.rate is linear_rate
            and animation.channels == frozenset(("position",))
        )
        or (isinstance(animation, MoveAlong) and animation.native_linear)
    )


def _expanded_clips(clips: tuple[AnimationClip, ...]) -> tuple[AnimationClip, ...]:
    """Expose held sequence timing for analytical lowering, never evaluate state.

    Released outer sequences retain their scope and fail native eligibility.
    Their restoration semantics must not be approximated by flattened children.
    """
    result: list[AnimationClip] = []
    for clip in clips:
        if isinstance(clip.animation, AnimationSequence) and clip.hold:
            factor = clip.duration / clip.animation.duration
            result.extend(
                replace(
                    child,
                    start=clip.start + child.start * factor,
                    duration=child.duration * factor,
                    breakpoints=tuple(point * factor for point in child.breakpoints),
                )
                for child in _expanded_clips(clip.animation.clips)
            )
        else:
            result.append(clip)
    return tuple(result)


def _native_tween(leaf: _Leaf) -> bool:
    """Continuous ASS interpolation is an explicit alternative to midpoint hold."""
    node = leaf.node
    if (
        leaf.evaluator.referenced(node.id)
        or leaf.affine_paths
        or node.material is not None
        or node.clip is not None
        or (isinstance(node, PathObject) and node.deform is not None)
        or leaf.start != node.time_origin
        or round(leaf.start * 100) / 100 != leaf.start
        or not any(n.animations for n in (*leaf.parents, node))
        or any(
            parent.clip is not None
            or any(
                clip.animation.channels != frozenset(("opacity",))
                for clip in parent.animations
            )
            for parent in leaf.parents
        )
    ):
        return False
    owned = tuple(
        (owner, clip)
        for owner in (*leaf.parents, node)
        for clip in _expanded_clips(owner.animations)
    )
    clips = tuple(
        replace(clip, start=local_seconds(owner.time_origin + clip.start, leaf.start))
        for owner, clip in owned
        if owner.time_origin + clip.start >= leaf.start
    )
    if len(clips) != len(owned):
        return False
    for index, clip in enumerate(clips):
        animation = clip.animation
        if (
            not isinstance(animation, (Tween, FadeIn, FadeOut))
            or animation.rate is not linear_rate
            or (isinstance(animation, FadeIn) and clip.start != 0)
            or not animation.channels
            or not animation.channels
            <= frozenset(
                (
                    "scale",
                    "rotation",
                    "opacity",
                    "fill",
                    "outline",
                    "border",
                    "blur",
                    "shadow",
                )
            )
            or not clip.hold
            or round(clip.end * 1000) <= round(clip.start * 1000)
        ):
            return False
        if any(
            max(clip.start, other.start) < min(clip.end, other.end)
            and clip.animation.channels & other.animation.channels
            for other in clips[index + 1 :]
        ):
            # Simultaneous inherited opacity curves multiply, rather than add;
            # their product is not generally a linear ASS alpha interpolation.
            return False
        target = animation.sample(node.state, 1)
        if min(target.scale.x, target.scale.y) <= 0:
            return False
    return True


def _tween_tag(
    clip: AnimationClip, target: VisualState, *, start_offset: float = 0
) -> str:
    tags = {
        "scale": rf"\fscx{target.scale.x * 100:.6f}\fscy{target.scale.y * 100:.6f}",
        "rotation": rf"\frz{-target.rotation:.6f}",
        "opacity": rf"\alpha&H{round((1 - target.opacity) * 255):02X}&",
        "fill": rf"\1c{_color(target.fill)}\2c{_color(target.fill)}",
        "outline": rf"\3c{_color(target.outline)}",
        "border": rf"\bord{target.border:.6f}",
        "blur": rf"\blur{target.blur:.6f}",
        "shadow": rf"\xshad{target.shadow.x:.6f}\yshad{target.shadow.y:.6f}",
    }
    target_tags = "".join(
        tag for channel, tag in tags.items() if channel in clip.animation.channels
    )
    return (
        rf"\t({round((clip.start + start_offset) * 1000)},{round((clip.end + start_offset) * 1000)},{target_tags})"
        if target_tags
        else ""
    )


def _tween_tags(leaf: _Leaf) -> str:
    return "".join(
        _tween_tag(
            replace(
                clip, start=local_seconds(owner.time_origin + clip.start, leaf.start)
            ),
            leaf.at(owner.time_origin + clip.end),
        )
        for owner, clip in sorted(
            (
                (owner, clip)
                for owner in (*leaf.parents, leaf.node)
                for clip in _expanded_clips(owner.animations)
            ),
            key=lambda pair: pair[0].time_origin + pair[1].start,
        )
    )


def _centiseconds(time: float) -> int:
    return round(round(time * 100, 8))


def _rectangle_state(leaf: _Leaf, time: float) -> VisualState:
    """Evaluate proven curves at original knots, outside cropped visibility too."""
    state = leaf.node.at(time)
    for parent in reversed(leaf.parents):
        state = compose_states(parent.at(time), state)
    return state


def _rectangle_animation_known(clips: tuple[AnimationClip, ...]) -> bool:
    for clip in clips:
        animation = clip.animation
        if type(animation) is AnimationSequence:
            assert isinstance(animation, AnimationSequence)
            if not clip.hold or not _rectangle_animation_known(animation.clips):
                return False
        elif type(animation) is ScalePulse:
            pass  # The released value equals the pulse endpoint.
        elif type(animation) in (Tween, FadeIn, FadeOut):
            assert isinstance(animation, (Tween, FadeIn, FadeOut))
            if type(animation) is Tween and type(animation.target) is not StatePatch:
                return False
            if not clip.hold or animation.rate is not linear_rate:
                return False
            if animation.channels & frozenset(("rotation", "skew")):
                return False
        else:
            return False
    return True


def _rectangle_owned_clips(leaf: _Leaf) -> tuple[tuple[float, AnimationClip], ...]:
    return tuple(
        (owner.time_origin, clip)
        for owner in (*leaf.parents, leaf.node)
        for clip in _expanded_clips(owner.animations)
    )


def _rectangle_geometry_knots(leaf: _Leaf) -> tuple[float, ...]:
    points: set[float] = set()
    for origin, clip in _rectangle_owned_clips(leaf):
        points.update((origin + clip.start, origin + clip.end))
        if type(clip.animation) is ScalePulse:
            points.add(origin + clip.start + clip.duration / 2)
    if not points:
        return leaf.start, leaf.end
    return tuple(
        sorted({min(leaf.start, min(points)), *points, max(leaf.end, max(points))})
    )


def _native_rectangle(leaf: _Leaf) -> bool:
    node = leaf.node
    if (
        not isinstance(node.clip, RectangleClip)
        or type(node.clip.deform) is not RectangleKeyframes
        or leaf.affine_paths
        or node.material is not None
        or leaf.evaluator.referenced(node.id)
        or any(parent.clip is not None for parent in leaf.parents)
        or (isinstance(node, PathObject) and node.deform is not None)
    ):
        return False
    if not _rectangle_animation_known(node.animations):
        return False
    if any(
        not _rectangle_animation_known(parent.animations)
        or any(clip.animation.channels - {"opacity"} for clip in parent.animations)
        for parent in leaf.parents
    ):
        return False
    owned = _rectangle_owned_clips(leaf)
    opacity_intervals = tuple(
        (local_seconds(origin + clip.start, 0), local_seconds(origin + clip.end, 0))
        for origin, clip in owned
        if "opacity" in clip.animation.channels
    )
    if any(
        max(start, other_start) < min(end, other_end)
        for index, (start, end) in enumerate(opacity_intervals)
        for other_start, other_end in opacity_intervals[index + 1 :]
    ):
        # Simultaneous inherited alpha curves multiply. Their product cannot
        # in general be emitted as a linear ASS alpha transform.
        return False
    if any(
        type(clip.animation) is FadeIn and (clip.start != 0 or origin > leaf.start)
        for origin, clip in owned
    ):
        return False
    if owned and any(
        abs(time - _centiseconds(time) / 100) > 1e-9
        for time in (*_rectangle_geometry_knots(leaf), *_rectangle_knots(leaf))
    ):
        # The error proof covers whole emitted sections; an event cut cannot
        # represent a sub-centisecond change in the polynomial or a reset.
        return False
    return all(
        state.skew == Vec2()
        and min(state.scale.x, state.scale.y) > 0
        and (node.clip.space == "screen" or state.rotation % 360 == 0)
        for state in (
            _rectangle_state(leaf, time) for time in _rectangle_geometry_knots(leaf)
        )
    )


def _rectangle_knots(leaf: _Leaf) -> tuple[float, ...]:
    clip = leaf.node.clip
    assert isinstance(clip, RectangleClip)
    assert isinstance(clip.deform, RectangleKeyframes)
    keys = (
        *(leaf.node.time_origin + t for t in clip.deform.breakpoints),
        *(_rectangle_geometry_knots(leaf) if _rectangle_owned_clips(leaf) else ()),
    )
    # Keep original knots around a cropped exposure. Re-anchoring transforms
    # at the exposure boundary would round intermediate rectangle coordinates.
    return tuple(sorted({min(leaf.start, min(keys)), *keys, max(leaf.end, max(keys))}))


def _rectangle_bounds(
    leaf: _Leaf, time: float, *, before: bool = False
) -> tuple[float, float, float, float]:
    clip = leaf.node.clip
    assert isinstance(clip, RectangleClip)
    assert isinstance(clip.deform, RectangleKeyframes)
    left, top, right, bottom = clip.deform.bounds_at(
        local_seconds(time, leaf.node.time_origin), before=before
    )
    if clip.space == "local":
        state = _rectangle_state(leaf, time)
        first = state.transform.apply(Vec2(left, top))
        last = state.transform.apply(Vec2(right, bottom))
        return first.x, first.y, last.x, last.y
    return left, top, right, bottom


def _rectangle_sections(
    leaf: _Leaf, budget: SceneBudget
) -> tuple[tuple[float, float], ...]:
    knots = _rectangle_knots(leaf)
    pending = list(
        reversed(
            tuple(
                (first, last)
                for first, last in zip(knots, knots[1:], strict=False)
                if _centiseconds(max(first, leaf.start))
                < _centiseconds(min(last, leaf.end))
            )
        )
    )
    sections: list[tuple[float, float]] = []
    while pending:
        first, last = pending.pop()
        if _centiseconds(max(first, leaf.start)) >= _centiseconds(min(last, leaf.end)):
            continue
        a = _rectangle_bounds(leaf, first)
        b = _rectangle_bounds(leaf, last, before=True)
        middle = _rectangle_bounds(leaf, (first + last) / 2)
        error = 0.0
        for start, mid, end in zip(a, middle, b, strict=True):
            # Each world-space edge is quadratic: linear bounds times linear
            # scale plus linear translation. Include endpoint integer rounding
            # in the polynomial error, and check its interior extremum too.
            quadratic = 2 * (start + end - 2 * mid)
            linear = end - start - quadratic - (round(end) - round(start))
            constant = start - round(start)
            error = max(error, abs(constant), abs(end - round(end)))
            if abs(quadratic) > 1e-12:
                vertex = -linear / (2 * quadratic)
                if 0 < vertex < 1:
                    error = max(
                        error, abs((quadratic * vertex + linear) * vertex + constant)
                    )
        if error > budget.clip_error_px + 1e-9:
            split = _centiseconds((first + last) / 2) / 100
            if not first < split < last:
                raise SceneCompileError(
                    f"transformed clip exceeds {budget.clip_error_px:g}px at ASS time resolution",
                    object_id=leaf.node.id,
                    origin=leaf.node.origin,
                )
            pending.extend(((split, last), (first, split)))
        else:
            sections.append((first, last))
        if len(sections) + len(pending) > budget.max_events:
            raise SceneCompileError(
                "native clip event budget exceeded",
                object_id=leaf.node.id,
                origin=leaf.node.origin,
            )
    return tuple(sections)


def _rectangle_events(
    leaf: _Leaf, style: str, sections: tuple[tuple[float, float], ...]
) -> tuple[Line, ...]:
    node = leaf.node
    clip = node.clip
    assert isinstance(clip, RectangleClip)
    assert isinstance(clip.deform, RectangleKeyframes)
    kind = "iclip" if clip.inverse else "clip"

    def tag(time: float, *, before: bool = False) -> str:
        left, top, right, bottom = _rectangle_bounds(leaf, time, before=before)
        return f"\\{kind}({round(left)},{round(top)},{round(right)},{round(bottom)})"

    animations: list[tuple[float, AnimationClip]] = []
    for origin, animation in _rectangle_owned_clips(leaf):
        if type(animation.animation) is ScalePulse:
            animations.extend(
                (
                    origin,
                    replace(
                        animation,
                        start=animation.start + index * animation.duration / 2,
                        duration=animation.duration / 2,
                        breakpoints=(),
                    ),
                )
                for index in (0, 1)
            )
        else:
            animations.append((origin, animation))
    alpha_start = min(
        (
            origin + animation.start
            for origin, animation in animations
            if "opacity" in animation.animation.channels
        ),
        default=node.time_origin,
    )
    events: list[Line] = []
    for first, last in sections:
        start = _centiseconds(max(first, leaf.start))
        end = _centiseconds(min(last, leaf.end))
        if start >= end:
            continue
        initial, final = tag(first), tag(last, before=True)
        tags = initial
        if initial != final:
            a, b = round(first * 1000) - start * 10, round(last * 1000) - start * 10
            tags += rf"\t({a},{b},1,{final})"
        state = replace(
            _rectangle_state(leaf, node.time_origin),
            opacity=_rectangle_state(leaf, alpha_start).opacity,
        )
        for origin, animation in sorted(
            animations, key=lambda pair: pair[0] + pair[1].start
        ):
            target = _rectangle_state(leaf, origin + animation.end)
            if round((origin + animation.end) * 1000) <= start * 10:
                # ASS treats a transform ending at 0 as ending at event end.
                # Fold completed channels into the header instead, retaining
                # original clocks only for active/future transforms.
                state = merge_channels(
                    state, target, animation.animation.channels - {"position"}
                )
            else:
                tags += _tween_tag(animation, target, start_offset=origin - start / 100)
        geometry_start, geometry_end = next(
            (
                (origin + animation.start, origin + animation.end)
                for origin, animation in animations
                if "position" in animation.animation.channels
                and origin + animation.start
                <= max(first, leaf.start)
                < min(last, leaf.end)
                <= origin + animation.end
            ),
            (max(first, leaf.start), max(first, leaf.start)),
        )
        state = replace(state, position=_rectangle_state(leaf, geometry_start).position)
        target = _rectangle_state(leaf, geometry_end)
        a = round(geometry_start * 1000) - start * 10
        b = round(geometry_end * 1000) - start * 10
        event = _event(
            leaf,
            state,
            start,
            end,
            style,
            path=node.path if isinstance(node, PathObject) else None,
        )
        if state.position != target.position:
            event.text = event.text.replace(
                rf"\pos({state.position.x:.6f},{state.position.y:.6f})",
                rf"\move({state.position.x:.6f},{state.position.y:.6f},{target.position.x:.6f},{target.position.y:.6f},{a},{b})",
                1,
            )
        event.text = event.text.replace("}", tags + "}", 1)
        events.append(event)
    return tuple(events)


def _active_intervals(leaf: _Leaf) -> tuple[tuple[float, float], ...]:
    """Only omit sampling where the declared object semantics are constant."""
    node = leaf.node
    if leaf.evaluator.referenced(node.id):
        return ((leaf.start, leaf.end),)
    if (isinstance(node, PathObject) and node.deform is not None) or (
        any(
            isinstance(n.clip, (RectangleClip, VectorClip))
            and n.clip.deform is not None
            for n in (*leaf.parents, node)
        )
    ):
        return ((leaf.start, leaf.end),)
    intervals = [
        (n.time_origin + c.start, n.time_origin + c.end)
        for n in (*leaf.parents, node)
        for c in n.animations
    ]
    if isinstance(node.material, PaintActivity):
        intervals.extend(
            (
                node.time_origin + interval.start,
                node.time_origin + interval.end,
            )
            for interval in node.material.active_intervals
        )
    elif node.material is not None and node.material.breakpoints:
        return ((leaf.start, leaf.end),)
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        start, end = max(leaf.start, start), min(leaf.end, end)
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            previous = merged.pop()
            start, end = previous[0], max(previous[1], end)
        merged.append((start, end))
    return tuple(merged)


def _sampling_diagnostics(leaf: _Leaf) -> tuple[str, ...]:
    """Report declared animation intervals lost on the output time grid."""
    messages: list[str] = []
    for owner in (*leaf.parents, leaf.node):
        for clip in owner.animations:
            points = sorted({0.0, *clip.breakpoints, clip.duration})
            for first, last in zip(points, points[1:], strict=False):
                start = max(leaf.start, owner.time_origin + clip.start + first)
                end = min(leaf.end, owner.time_origin + clip.start + last)
                if start < end and _centiseconds(start) == _centiseconds(end):
                    messages.append(
                        f"{owner.id}: sampled animation interval "
                        f"{start:.9g}..{end:.9g}s collapses on ASS centisecond grid"
                    )
    return tuple(messages)


def _sample_interval(points: tuple[int, ...], leaf: _Leaf) -> float | None:
    intervals = _active_intervals(leaf)
    widths = [
        (b - a) / 100
        for a, b in zip(points, points[1:], strict=False)
        if any(
            a < _centiseconds(end) and b > _centiseconds(start)
            for start, end in intervals
        )
    ]
    return max(widths) if widths else None


def _boundaries(leaf: _Leaf, budget: SceneBudget) -> tuple[int, ...]:
    start, end = _centiseconds(leaf.start), _centiseconds(leaf.end)
    points = {start, end}
    if leaf.evaluator.referenced(leaf.node.id):
        points.update(
            max(start, min(end, _centiseconds(t)))
            for t in leaf.evaluator.breakpoints(leaf.node.id)
        )
    for first, last in _active_intervals(leaf):
        first_step = max(1, int(local_seconds(first, leaf.start) * budget.fps))
        last_step = ceil(local_seconds(last, leaf.start) * budget.fps)
        points.update(
            _centiseconds(leaf.start + i / budget.fps)
            for i in range(first_step, last_step)
            if first < leaf.start + i / budget.fps < last
        )
        points.update((_centiseconds(first), _centiseconds(last)))
    for node in (*leaf.parents, leaf.node):
        for clip in node.animations:
            for value in (
                node.time_origin + clip.start,
                node.time_origin + clip.end,
                *(node.time_origin + clip.start + t for t in clip.breakpoints),
            ):
                points.add(max(start, min(end, _centiseconds(value))))
    if isinstance(leaf.node, PathObject) and leaf.node.deform is not None:
        for value in leaf.node.deform.breakpoints:
            points.add(
                max(start, min(end, _centiseconds(leaf.node.time_origin + value)))
            )
    for node in (*leaf.parents, leaf.node):
        if (
            isinstance(node.clip, (RectangleClip, VectorClip))
            and node.clip.deform is not None
        ):
            for value in node.clip.deform.breakpoints:
                points.add(
                    max(start, min(end, _centiseconds(node.time_origin + value)))
                )
    if leaf.node.material is not None:
        for value in leaf.node.material.breakpoints:
            points.add(
                max(start, min(end, _centiseconds(leaf.node.time_origin + value)))
            )
    return tuple(sorted(points))


def _color(value: Color) -> str:
    return f"&H{value.blue:02X}{value.green:02X}{value.red:02X}&"


def _tags(state: VisualState) -> str:
    alpha = round((1 - state.opacity) * 255)
    # Rotation is clockwise in the scene; ASS frz is counterclockwise.
    return (
        rf"\fscx{state.scale.x * 100:.6f}\fscy{state.scale.y * 100:.6f}"
        rf"\frz{-state.rotation:.6f}\frx0\fry0\fax{state.skew.x:.6f}\fay{state.skew.y:.6f}"
        rf"\1c{_color(state.fill)}\2c{_color(state.fill)}\3c{_color(state.outline)}\4c&H000000&"
        rf"\alpha&H{alpha:02X}&\bord{state.border:.6f}\blur{state.blur:.6f}\be0"
        rf"\xshad{state.shadow.x:.6f}\yshad{state.shadow.y:.6f}"
    )


def _event(
    leaf: _Leaf,
    state: VisualState,
    start: int,
    end: int,
    style: str,
    *,
    move: bool = False,
    path: VectorPath | None = None,
    paint_clip: RectangleClip | VectorClip | None = None,
) -> Line:
    node = leaf.node
    position = rf"\pos({state.position.x:.6f},{state.position.y:.6f})"
    if move:
        clip = node.animations[0]
        target = node.at(node.time_origin + clip.end).position
        position = (
            rf"\move({state.position.x:.6f},{state.position.y:.6f},{target.x:.6f},{target.y:.6f},"
            f"{round(clip.start * 1000)},{round(clip.end * 1000)})"
        )
    clipping = ""
    clipping_shape = paint_clip
    if clipping_shape is not None:
        kind = "iclip" if clipping_shape.inverse else "clip"
        if isinstance(clipping_shape, RectangleClip):
            coordinates = ",".join(
                str(round(v))
                for v in (
                    clipping_shape.left,
                    clipping_shape.top,
                    clipping_shape.right,
                    clipping_shape.bottom,
                )
            )
            clipping = f"\\{kind}({coordinates})"
        else:
            clipping = f"\\{kind}(1,{clipping_shape.path.drawing()})"
    if isinstance(node, TextObject) and path is None:
        # Protect literal backslashes before adding ASS escapes. The invisible
        # word joiner prevents a following N/n/h from becoming an ASS command.
        content = (
            node.text.replace("\\", "\\\u2060")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\n", r"\N")
        )
        geometry = (
            rf"\an{node.alignment}\fn{node.font}\fe{node.encoding}\fs{node.font_size:.6f}"
            rf"\b{int(node.bold)}\i{int(node.italic)}\u0\s0\fsp{node.spacing:.6f}\p0"
        )
    else:
        assert path is not None or isinstance(node, PathObject)
        drawing = node.path if isinstance(node, PathObject) and path is None else path
        assert drawing is not None
        content = drawing.drawing()
        geometry = r"\an7\p1\pbo0"
    return Line(
        text="{"
        + rf"\r{style}\q2"
        + geometry
        + position
        + _tags(state)
        + clipping
        + "}"
        + content,
        start_time=start * 10,
        end_time=end * 10,
        style=style,
        layer=node.layer + sum(parent.layer for parent in leaf.parents),
    )


@dataclass(frozen=True)
class _PaintedFrame:
    events: tuple[Line, ...]
    clip_points: int = 0
    path_points: int = 0
    affine: bool = False


def _painted_events(
    leaf: _Leaf,
    state: VisualState,
    start: int,
    end: int,
    style: str,
    width: int,
    height: int,
    time: float,
    *,
    move: bool = False,
    path: VectorPath | None = None,
    budget: SceneBudget,
    outlines: dict[str, VectorPath | None],
    clips: ClipResolver,
    resolved_mask: ResolvedMasks | None = None,
) -> _PaintedFrame:
    if state.singular:
        return _PaintedFrame((), affine=True)
    material = leaf.node.material
    resolved = (
        clips.combine((*leaf.parents, leaf.node), time, state)
        if resolved_mask is None
        else resolved_mask
    )
    source = resolved.clip
    if source is False:
        return _PaintedFrame((), resolved.peak_points)
    # ASS clips act after blur. Restrict oversized polygon masks before output:
    # huge half-planes can exceed libass's mask bitmap limits. Leave ordinary
    # masks intact to retain rasterizer edge rounding, including overscan paths.
    if (
        isinstance(source, VectorClip)
        and all(
            isinstance(segment, LineSegment)
            for contour in source.path.contours
            for segment in contour.segments
        )
        and any(
            abs(point.x) > 32768 or abs(point.y) > 32768
            for contour in source.path.contours
            for point in (contour.start, *(segment.end for segment in contour.segments))
        )
    ):
        bounded = intersect_convex(
            source.path,
            (Vec2(0, 0), Vec2(width, 0), Vec2(width, height), Vec2(0, height)),
            max_points=budget.max_path_points,
        )
        if bounded is None:
            if not source.inverse:
                return _PaintedFrame((), resolved.peak_points)
            source = None
        else:
            source = replace(source, path=bounded)
    clip_points = max(
        resolved.peak_points,
        source.path.point_count if isinstance(source, VectorClip) else 0,
    )
    paint_state = state
    affine = (
        leaf.affine_paths
        or state.skew != Vec2()
        or min(state.scale.x, state.scale.y) <= 0
    )
    path_points = 0
    if affine:
        if isinstance(leaf.node, TextObject):
            if "\n" in leaf.node.text:
                raise ValueError("affine text lowering requires single-line text")
            if leaf.node.id not in outlines:
                outlines[leaf.node.id] = outline_text(
                    leaf.node, max_points=budget.max_path_points
                ).path
            path = outlines[leaf.node.id]
            if path is None:
                return _PaintedFrame((), clip_points, affine=True)
        elif path is None:
            path = leaf.node.path
        path_points = path.point_count
        if path_points > budget.max_path_points:
            raise ValueError("affine geometry point budget exceeded")
        linear = replace(state.transform, tx=0, ty=0)
        path = path.map(linear.apply)
        state = replace(state, scale=Vec2(1, 1), rotation=0, skew=Vec2())
    if material is None:
        return _PaintedFrame(
            (
                _event(
                    leaf,
                    state,
                    start,
                    end,
                    style,
                    move=move,
                    path=path,
                    paint_clip=source,
                ),
            ),
            clip_points,
            path_points,
            affine,
        )
    limit = width if material.axis == "x" else height
    bands = material.bands(
        0, limit, local_seconds(time, leaf.node.time_origin), paint_state
    )
    if len(bands) > material.max_bands:
        raise ValueError("paint field exceeded its declared band bound")
    previous = 0
    result: list[Line] = []
    for band in bands:
        if (
            type(band.start) is not int
            or type(band.end) is not int
            or band.start != previous
            or not previous < band.end <= limit
        ):
            raise ValueError(
                "paint bands must partition the screen with integer boundaries"
            )
        previous = band.end
        left, top, right, bottom = (
            (band.start, 0, band.end, height)
            if material.axis == "x"
            else (0, band.start, width, band.end)
        )
        if isinstance(source, RectangleClip) and not source.inverse:
            left, top = max(left, round(source.left)), max(top, round(source.top))
            right, bottom = (
                min(right, round(source.right)),
                min(bottom, round(source.bottom)),
            )
        if right <= left or bottom <= top:
            continue
        combined: RectangleClip | VectorClip = RectangleClip(left, top, right, bottom)
        if isinstance(source, RectangleClip) and source.inverse:
            for rectangle in rectangle_difference(combined, source):
                result.append(
                    _event(
                        leaf,
                        replace(state, fill=band.fill, outline=band.outline),
                        start,
                        end,
                        style,
                        move=move,
                        path=path,
                        paint_clip=rectangle,
                    )
                )
            continue
        if source is not None and source.inverse:
            intersection = path_boolean(
                _mask_path(combined),
                _mask_path(source),
                "difference",
                max_points=budget.max_path_points,
                max_work=budget.max_boolean_work,
            )
            if intersection is None:
                continue
            combined = VectorClip(intersection)
            clip_points = max(clip_points, intersection.point_count)
        elif isinstance(source, VectorClip):
            intersection = intersect_convex(
                source.path,
                (
                    Vec2(left, top),
                    Vec2(right, top),
                    Vec2(right, bottom),
                    Vec2(left, bottom),
                ),
                max_points=budget.max_path_points,
            )
            if intersection is None:
                continue
            combined = VectorClip(intersection)
            clip_points = max(clip_points, intersection.point_count)
        result.append(
            _event(
                leaf,
                replace(state, fill=band.fill, outline=band.outline),
                start,
                end,
                style,
                move=move,
                path=path,
                paint_clip=combined,
            )
        )
    if previous != limit:
        raise ValueError("paint bands must cover the screen")
    return _PaintedFrame(tuple(result), clip_points, path_points, affine)


def _insert_events(
    document: Document, generated: list[Line], style: Style | None
) -> None:
    records = document.records
    events_index = next(
        (
            i
            for i, record in enumerate(records)
            if isinstance(record, str) and record.strip().lower() == "[events]"
        ),
        None,
    )
    if events_index is None:
        records.extend(("[Events]", "Format: " + EVENT_FORMAT))
        events_index = len(records) - 2
    if style is not None and style.name not in document.styles:
        # A dedicated style section is safe even when a source uses reordered columns.
        records[events_index:events_index] = [
            "[V4+ Styles]",
            "Format: " + STYLE_FORMAT,
            style,
        ]
        events_index += 3
    end = events_index + 1
    columns: list[str] = []
    while end < len(records):
        record = records[end]
        if isinstance(record, str):
            text = record.strip()
            if text.startswith("[") and text.endswith("]"):
                break
            if text.lower().startswith("format:"):
                columns = [
                    column.strip() for column in text.partition(":")[2].split(",")
                ]
        end += 1
    if not columns:
        records.insert(events_index + 1, "Format: " + EVENT_FORMAT)
        columns = list(EVENT_FORMAT.split(", "))
        end += 1
    if "effect" not in {column.lower() for column in columns}:
        # Preserve the source's earlier Format and introduce canonical output columns.
        records.insert(end, "Format: " + EVENT_FORMAT)
        end += 1
        columns = list(EVENT_FORMAT.split(", "))
    if columns[-1].lower() != "text":
        raise SceneCompileError("event Text must be the final field")
    for event in generated:
        # Native nodes retain custom metadata when columns are available.
        event.fields = {column: event.fields.get(column, "") for column in columns}
    records[end:end] = generated


def _scene_source_records(
    records: list[str | Style | Line],
    prefix: str,
    replace_records: set[int],
) -> list[str | Style | Line]:
    """Strip owned output pairs before any importer removes their Dialogue."""
    retained: list[str | Style | Line] = []
    skip_native = False
    for index, record in enumerate(records):
        if skip_native:
            if not isinstance(record, Line) or record.comment:
                raise SceneCompileError("damaged native-event provenance marker")
            skip_native = False
            continue
        if isinstance(record, Line) and record.effect.startswith(prefix):
            skip_native = record.comment and record.text == "kara native event follows"
            continue
        retained.append(
            replace(record, comment=True)
            if index in replace_records and isinstance(record, Line)
            else record
        )
    if skip_native:
        raise SceneCompileError("native-event provenance marker has no following event")
    return retained


def compile_scene(
    scene: Scene,
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
    on_estimate: Callable[[SceneEstimate], None] | None = None,
) -> SceneResult:
    """Return a new Document. Source records and caller-owned nodes never mutate."""
    budget = SceneBudget() if budget is None else budget
    if on_estimate is not None and not callable(on_estimate):
        raise TypeError("on_estimate must be callable")
    if not scene.owner:
        raise SceneCompileError("scene owner must be nonempty")
    try:
        evaluator = SceneEvaluator(scene)
    except SceneReferenceError as error:
        raise SceneCompileError(
            str(error), object_id=error.object_id, origin=error.origin
        ) from error
    leaves, native, coverage, object_order = _leaves(scene, evaluator)
    meta = Document.parse(scene.document.dumps()).meta
    width, height = meta.res_x, meta.res_y
    outlines: dict[str, VectorPath | None] = {}
    estimate = 2 * len(native)
    max_quantization = 0.0
    diagnostics: dict[str, None] = {}
    rectangle_plans: dict[str, tuple[tuple[float, float], ...]] = {}
    for leaf in leaves:
        node = leaf.node
        if isinstance(node, TextObject) and leaf.affine_paths:
            try:
                if "\n" in node.text:
                    raise ValueError("affine text lowering requires single-line text")
                outlines[node.id] = outline_text(
                    node, max_points=budget.max_path_points
                ).path
            except (ValueError, TypeError) as error:
                raise SceneCompileError(
                    str(error), object_id=node.id, origin=node.origin
                ) from error
        for path in [node.path] if isinstance(node, PathObject) else []:
            if path.point_count > budget.max_path_points:
                raise SceneCompileError(
                    "path complexity budget exceeded",
                    object_id=node.id,
                    origin=node.origin,
                )
        band_bound = 1
        if node.material is not None:
            band_bound = node.material.max_bands
            if type(band_bound) is not int or not 1 <= band_bound <= budget.max_bands:
                raise SceneCompileError(
                    "declared paint band budget exceeded",
                    object_id=node.id,
                    origin=node.origin,
                )
            if node.material.axis not in ("x", "y"):
                raise SceneCompileError("paint axis must be x or y", object_id=node.id)
        if node.material is not None and any(
            isinstance(n.clip, RectangleClip) and n.clip.inverse
            for n in (*leaf.parents, node)
        ):
            # One inverse rectangle can split a paint band into four disjoint
            # native rectangles. This counts events, not additional colors.
            band_bound *= 4
        geometry_breaks = (
            len(evaluator.breakpoints(node.id)) if evaluator.referenced(node.id) else 0
        )
        for owner in (*leaf.parents, node):
            mask = owner.clip
            if (
                isinstance(mask, RectangleClip)
                and mask.space == "local"
                and budget.max_path_points < 4
            ):
                raise SceneCompileError(
                    "local rectangle clip point budget exceeded",
                    object_id=owner.id,
                    origin=owner.origin,
                )
            if isinstance(mask, RectangleClip) and mask.deform is not None:
                geometry_breaks += len(mask.deform.breakpoints)
                for time in mask.deform.breakpoints:
                    value = owner.time_origin + time
                    max_quantization = max(
                        max_quantization, abs(value - _centiseconds(value) / 100)
                    )
            if isinstance(mask, VectorClip):
                if mask.path.point_count > budget.max_path_points:
                    raise SceneCompileError(
                        "path complexity budget exceeded",
                        object_id=owner.id,
                        origin=owner.origin,
                    )
                if mask.deform is not None:
                    if mask.deform.max_points > budget.max_path_points:
                        raise SceneCompileError(
                            "declared clip point budget exceeded",
                            object_id=owner.id,
                            origin=owner.origin,
                        )
                    geometry_breaks += len(mask.deform.breakpoints)
                    for time in mask.deform.breakpoints:
                        value = owner.time_origin + time
                        max_quantization = max(
                            max_quantization, abs(value - _centiseconds(value) / 100)
                        )
        if isinstance(node, PathObject) and node.deform is not None:
            if node.deform.max_points > budget.max_path_points:
                raise SceneCompileError(
                    "declared geometry point budget exceeded",
                    object_id=node.id,
                    origin=node.origin,
                )
            geometry_breaks += len(node.deform.breakpoints)
        rectangle = native_tweens and _native_rectangle(leaf)
        if rectangle:
            rectangle_plans[node.id] = _rectangle_sections(leaf, budget)
        native_strategy = (
            not leaf.dynamic
            or _native_move(leaf)
            or (native_tweens and _native_tween(leaf))
            or rectangle
        )
        if not native_strategy:
            diagnostics.update(dict.fromkeys(_sampling_diagnostics(leaf)))
        estimate += band_bound * (
            len(rectangle_plans[node.id])
            if rectangle
            else 1
            if native_strategy
            else sum(ceil((b - a) * budget.fps) + 2 for a, b in _active_intervals(leaf))
            + sum(
                2 + len(c.breakpoints)
                for n in (*leaf.parents, node)
                for c in n.animations
            )
            + 1
            + geometry_breaks
            + (len(node.material.breakpoints) if node.material is not None else 0)
        )
        for value in (
            leaf.start,
            leaf.end,
            *(evaluator.breakpoints(node.id) if evaluator.referenced(node.id) else ()),
            *(
                n.time_origin + t
                for n in (*leaf.parents, node)
                for c in n.animations
                for t in (c.start, c.end, *(c.start + value for value in c.breakpoints))
            ),
        ):
            max_quantization = max(
                max_quantization, abs(value - _centiseconds(value) / 100)
            )
        if isinstance(node, PathObject) and node.deform is not None:
            for t in node.deform.breakpoints:
                value = node.time_origin + t
                max_quantization = max(
                    max_quantization, abs(value - _centiseconds(value) / 100)
                )
        if node.material is not None:
            for t in node.material.breakpoints:
                value = node.time_origin + t
                max_quantization = max(
                    max_quantization, abs(value - _centiseconds(value) / 100)
                )
        if _centiseconds(leaf.end) <= _centiseconds(leaf.start):
            raise SceneCompileError(
                "lifetime vanishes on ASS centisecond grid",
                object_id=node.id,
                origin=node.origin,
            )
        if estimate > budget.max_events:
            raise SceneCompileError(
                f"estimated event budget exceeded ({estimate} > {budget.max_events})",
                object_id=node.id,
                origin=node.origin,
            )
    if estimate > budget.max_events:
        raise SceneCompileError("native event budget exceeded")
    prefix = "kara:scene:v1:" + quote(scene.owner, safe="") + ":"
    output = deepcopy(scene.document)
    output.records = _scene_source_records(
        output.records, prefix, scene.replace_records
    )
    for index in scene.replace_records:
        if not 0 <= index < len(scene.document.records) or not isinstance(
            scene.document.records[index], Line
        ):
            raise SceneCompileError("invalid source replacement record")
    style = Style(
        name="KaraScene_" + sha256(scene.owner.encode()).hexdigest()[:12],
        fontname="DejaVu Sans",
        fontsize=48,
        outline=0,
        shadow=0,
        align=7,
    )
    if (
        (leaves or coverage)
        and style.name in output.styles
        and output.styles[style.name].serialize() != style.serialize()
    ):
        raise SceneCompileError(
            "generated style name collides with a different source style"
        )
    generated: list[Line] = []
    from .coverage_output import _lower_coverage, _prepare_coverage

    prepared_coverage = deque()
    for branch in coverage:
        try:
            prepared_coverage.append(
                _prepare_coverage(
                    branch.node,
                    resolution=(width, height),
                    budget=budget,
                    parents=branch.parents,
                    interval=(branch.start, branch.end),
                    evaluator=evaluator,
                )
            )
        except ValueError as error:
            raise SceneCompileError(str(error), object_id=branch.node.id) from error
        for leaf in prepared_coverage[-1].sampler.leaves.values():
            diagnostics.update(dict.fromkeys(_sampling_diagnostics(leaf)))
    if on_estimate is not None:
        on_estimate(
            SceneEstimate(
                estimate,
                tuple(
                    CoverageEstimate(
                        prepared.group.id,
                        len(prepared.points) - 1,
                        (len(prepared.points) - 1) * len(prepared.sampler.leaves),
                        prepared.group.coverage.settings.max_channel_error,
                    )
                    for prepared in prepared_coverage
                    if prepared.group.coverage is not None
                ),
            )
        )
    by_object: dict[str, list[Line]] = {}
    event_origins: dict[int, EventOrigin | None] = {}
    reports: list[ObjectReport] = []
    size = len(output.dumps().encode("utf-8")) + 3

    def append(
        event: Line,
        object_id: str,
        origin: EventOrigin | None,
        *,
        preserve_effect: bool = False,
    ) -> None:
        nonlocal size
        if not preserve_effect:
            event.effect = prefix + quote(object_id, safe="")
        size += len(event.serialize().encode("utf-8")) + 1
        if len(generated) >= budget.max_events or size > budget.max_bytes:
            raise SceneCompileError(
                "actual event/byte budget exceeded", object_id=object_id, origin=origin
            )
        generated.append(event)
        event_origins[id(event)] = origin
        by_object.setdefault(object_id, []).append(event)

    clips = ClipResolver(evaluator, budget.max_path_points, budget.max_boolean_work)
    for leaf in leaves:
        node = leaf.node
        affine = False
        before = len(generated)
        move = _native_move(leaf)
        tween = native_tweens and _native_tween(leaf)
        rectangle = node.id in rectangle_plans
        sample_interval: float | None = None
        peak_path_points = 0
        peak_bands = 0
        peak_clip_points = 0
        if rectangle:
            events = _rectangle_events(leaf, style.name, rectangle_plans[node.id])
            for event in events:
                append(event, node.id, node.origin)
            strategy = "native-clip"
            peak_path_points = (
                node.path.point_count if isinstance(node, PathObject) else 0
            )
            peak_bands = 1
        elif not leaf.dynamic or move or tween:
            peak_path_points = (
                node.path.point_count if isinstance(node, PathObject) else 0
            )
            try:
                frame = _painted_events(
                    leaf,
                    leaf.at(leaf.start),
                    _centiseconds(leaf.start),
                    _centiseconds(leaf.end),
                    style.name,
                    width,
                    height,
                    leaf.start,
                    move=move,
                    budget=budget,
                    outlines=outlines,
                    clips=clips,
                )
            except (ValueError, TypeError) as error:
                raise SceneCompileError(
                    str(error),
                    object_id=error.object_id
                    if isinstance(error, (SceneReferenceError, SceneClipError))
                    else node.id,
                    origin=error.origin
                    if isinstance(error, (SceneReferenceError, SceneClipError))
                    else node.origin,
                ) from error
            events = frame.events
            affine = frame.affine
            peak_path_points = max(peak_path_points, frame.path_points)
            peak_clip_points = frame.clip_points
            peak_bands = len(events)
            for event in events:
                if tween:
                    event.text = event.text.replace("}", _tween_tags(leaf) + "}", 1)
                append(event, node.id, node.origin)
            strategy = (
                "native-tween" if tween else "native-move" if move else "native-static"
            )
        else:
            points = _boundaries(leaf, budget)
            sample_interval = _sample_interval(points, leaf)
            samples: list[tuple[int, int, float, VisualState]] = []
            for start, end in zip(points, points[1:], strict=False):
                time = (start + end) / 200
                try:
                    samples.append((start, end, time, leaf.at(time)))
                except (ValueError, TypeError) as error:
                    raise SceneCompileError(
                        f"sample at {time:.6f}s: {error}",
                        object_id=error.object_id
                        if isinstance(error, (SceneReferenceError, SceneClipError))
                        else node.id,
                        origin=error.origin
                        if isinstance(error, (SceneReferenceError, SceneClipError))
                        else node.origin,
                    ) from error
            # Choose a consistent backend for these emitted samples; this is not
            # a claim about an arbitrary callback between sampling instants.
            if any(
                state.skew != Vec2() or min(state.scale.x, state.scale.y) <= 0
                for _, _, _, state in samples
            ):
                leaf = replace(leaf, force_affine=True)
            pending: dict[str, Line] = {}
            for start, end, time, state in samples:
                try:
                    path = node.path_at(time) if isinstance(node, PathObject) else None
                    if path is not None:
                        peak_path_points = max(peak_path_points, path.point_count)
                        if path.point_count > budget.max_path_points:
                            raise ValueError("actual geometry point budget exceeded")
                    frame = (
                        _PaintedFrame(())
                        if isinstance(node, PathObject) and path is None
                        else _painted_events(
                            leaf,
                            state,
                            start,
                            end,
                            style.name,
                            width,
                            height,
                            time,
                            path=path,
                            budget=budget,
                            outlines=outlines,
                            clips=clips,
                        )
                    )
                except (ValueError, TypeError) as error:
                    raise SceneCompileError(
                        f"sample at {time:.6f}s: {error}",
                        object_id=error.object_id
                        if isinstance(error, (SceneReferenceError, SceneClipError))
                        else node.id,
                        origin=error.origin
                        if isinstance(error, (SceneReferenceError, SceneClipError))
                        else node.origin,
                    ) from error
                events = frame.events
                affine |= frame.affine
                peak_path_points = max(peak_path_points, frame.path_points)
                peak_clip_points = max(peak_clip_points, frame.clip_points)
                peak_bands = max(peak_bands, len(events))
                current: dict[str, Line] = {}
                for event in events:
                    previous = pending.pop(event.text, None)
                    if previous is not None and previous.end_time == event.start_time:
                        previous.end_time = event.end_time
                        event = previous
                    elif previous is not None:
                        append(previous, node.id, node.origin)
                    current[event.text] = event
                for event in pending.values():
                    append(event, node.id, node.origin)
                pending = current
            for event in pending.values():
                append(event, node.id, node.origin)
            strategy = "sampled"
        if affine:
            strategy += "-affine-path"
        if node.material is not None:
            strategy += "-bands"
        reports.append(
            ObjectReport(
                node.id,
                strategy,
                len(generated) - before,
                node.origin,
                sample_interval,
                peak_path_points,
                peak_bands if node.material is not None else None,
                peak_clip_points
                if any(n.clip is not None for n in (*leaf.parents, node))
                else None,
            )
        )
    while prepared_coverage:
        prepared = prepared_coverage.popleft()
        group = prepared.group

        try:
            lowered = _lower_coverage(
                prepared,
                style=style.name,
                native_tweens=native_tweens,
            )
        except ValueError as error:
            raise SceneCompileError(str(error), object_id=group.id) from error
        estimate += len(lowered.events)
        if estimate > budget.max_events:
            raise SceneCompileError(
                "estimated event budget exceeded with coverage", object_id=group.id
            )
        for event in lowered.events:
            append(event, group.id, lowered.origin)
        max_quantization = max(max_quantization, lowered.time_error)
        reports.append(
            ObjectReport(
                group.id,
                "coverage-native-opacity" if lowered.native_opacity else "coverage",
                len(lowered.events),
                lowered.origin,
                1 / budget.fps,
                sample_times=lowered.sample_times,
                max_channel_error=lowered.max_channel_error,
            )
        )
    for node in native:
        append(
            Line(
                text="kara native event follows",
                comment=True,
                start_time=node.event.start_time,
                end_time=node.event.end_time,
            ),
            node.id,
            node.origin,
        )
        append(deepcopy(node.event), node.id, node.origin, preserve_effect=True)
        reports.append(ObjectReport(node.id, "native-event", 1, node.origin))
    generated = [
        event for identity in object_order for event in by_object.get(identity, ())
    ]
    ranks = {identity: rank for rank, identity in enumerate(object_order)}
    reports.sort(key=lambda report: ranks[report.id])
    if generated:
        _insert_events(output, generated, style if leaves or coverage else None)
    byte_count = len(output.dumps().encode("utf-8")) + 3
    if byte_count > budget.max_bytes:
        raise SceneCompileError("serialized document byte budget exceeded")
    edges: list[tuple[float, int]] = []
    for event in output.lines:
        if not event.comment and event.end_time > event.start_time:
            finite(event.start_time, event.end_time)
            edges.extend(((event.start_time, 1), (event.end_time, -1)))
    active = peak = 0
    for _, delta in sorted(edges):
        active += delta
        peak = max(peak, active)
    if peak > budget.max_active:
        raise SceneCompileError(
            f"peak active event budget exceeded ({peak} > {budget.max_active})"
        )
    return SceneResult(
        output,
        tuple(reports),
        sum(not event.comment for event in generated),
        peak,
        byte_count,
        estimate,
        max_quantization,
        diagnostics=tuple(diagnostics),
        event_origins=tuple(
            (event, event_origins[id(event)])
            for event in generated
            if not event.comment
        ),
    )
