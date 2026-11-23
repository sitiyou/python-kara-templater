"""Bounded standard-ASS lowering for the shared document scene."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import lru_cache
from hashlib import sha256
from math import hypot
from typing import Literal
from urllib.parse import quote

from ._scene_clipping import (
    ClipResolver,
    ResolvedMasks,
    SceneClipError,
)
from .ass import EVENT_FORMAT, STYLE_FORMAT, Document, Line, Style
from .composition import Color
from .easing import ease_out
from .geometry import LineSegment, Vec2, VectorPath, finite
from .layout import text_extents
from .path_geometry import intersect_convex, path_bounds
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
    _CellWipeClip,
    _ColorStripClip,
)
from .scene_animation import (
    AnimationClip,
    AnimationSequence,
    DriftOut,
    FadeIn,
    FadeOut,
    ScalePulse,
    StatePatch,
    Tween,
    VisualState,
    linear_rate,
    local_seconds,
    merge_channels,
    smooth_rate,
    smoother_rate,
)
from .scene_evaluation import SceneEvaluator, SceneReferenceError, compose_states
from .sources import EventOrigin
from .text_geometry import _VectorGuideText, outline_text, text_to_path


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

    ASS compilation enforces limits on events, bytes, active drawings, geometry
    and boolean work. It does not sample at fps or generate paint bands.
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
class SceneEstimate:
    """Estimated ASS event count before emission."""

    estimated_events: int


@dataclass(frozen=True)
class ObjectReport:
    """ASS lowering strategy, source origin, event count and observed geometry costs."""

    id: str
    strategy: str
    events: int
    origin: EventOrigin | None
    peak_path_points: int | None = None
    peak_clip_points: int | None = None


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
class _ScalePolynomial:
    knots: tuple[tuple[float, Vec2], ...]
    controls: tuple[int, ...]


@dataclass(frozen=True)
class _Leaf:
    node: TextObject | PathObject
    parents: tuple[ObjectGroup, ...]
    start: float
    end: float
    evaluator: SceneEvaluator
    affine_pen_scale: Vec2 | None = None
    rectangle_anchor: Vec2 | None = None
    scale_polynomials: tuple[_ScalePolynomial, ...] = ()
    rectangle_states: dict[float, VisualState] = field(
        default_factory=dict, compare=False
    )

    @property
    def animated_pen(self) -> bool:
        """Local border radii can vary with scale even without an explicit border tween."""
        return self.node.scale_border and any(
            clip.animation.channels & {"border", "scale"}
            for owner in (*self.parents, self.node)
            for clip in owner.animations
        )

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
            any(
                n.state.skew != Vec2() or min(n.state.scale.x, n.state.scale.y) <= 0
                for n in (*self.parents, self.node)
            )
            or any(p.state.scale.x != p.state.scale.y for p in self.parents)
        )

    def at(self, time: float) -> VisualState:
        return self.evaluator.at(self.node.id, time)


def _leaves(
    scene: Scene,
    evaluator: SceneEvaluator,
    *,
    collect_coverage: bool = True,
) -> tuple[
    tuple[_Leaf, ...],
    tuple[NativeEvent, ...],
    tuple[ObjectGroup, ...],
    tuple[str, ...],
]:
    leaves: list[_Leaf] = []
    native: list[NativeEvent] = []
    coverage: list[ObjectGroup] = []
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
                    coverage.append(node)
                    order.append(node.id)
                return
            for child in node.children:
                visit(child, (*parents, node))
            return
        start = max(n.lifetime.start for n in (*parents, node))
        end = min(n.lifetime.end for n in (*parents, node))
        if end > start:
            if isinstance(node, _VectorGuideText):
                node = text_to_path(node, path=node.outline.path)
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


def _native_fade_curve(animation: object) -> bool:
    return (type(animation) is FadeIn or type(animation) is FadeOut) and animation.rate is ease_out


def _native_tween(leaf: _Leaf) -> bool:
    """Check whether a native ASS transform can express these animation clips."""
    node = leaf.node
    if (
        leaf.evaluator.referenced(node.id)
        or leaf.animated_pen
        or leaf.affine_paths
        or node.material is not None
        or node.clip is not None
        or (isinstance(node, PathObject) and node.deform is not None)
        or abs(round(leaf.start * 100) / 100 - leaf.start) > 1e-9
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
    if sum("position" in clip.animation.channels for clip in clips) > 1:
        return False  # ASS permits one move command per event.
    for index, clip in enumerate(clips):
        animation = clip.animation
        if (
            not isinstance(animation, (Tween, FadeIn, FadeOut))
            or (animation.rate is not linear_rate and not _native_fade_curve(animation))
            or (isinstance(animation, FadeIn) and clip.start != 0)
            or not animation.channels
            or not animation.channels
            <= frozenset(
                (
                    "position",
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


def _number(value: float) -> str:
    """Retain six-decimal ASS precision without redundant zero suffixes."""
    result = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if result == "-0" else result


def _opacity_tags(opacity: float, filled: bool) -> str:
    alpha = f"&H{round((1 - opacity) * 255):02X}&"
    return rf"\alpha{alpha}" if filled else rf"\1a&HFF&\3a{alpha}\4a{alpha}"


def _tween_tag(
    clip: AnimationClip, target: VisualState, *, start_offset: float = 0,
    omit_scale: bool = False, filled: bool = True,
) -> str:
    tags = {
        "scale": rf"\fscx{_number(target.scale.x * 100)}\fscy{_number(target.scale.y * 100)}",
        "rotation": rf"\frz{_number(-target.rotation)}",
        "opacity": _opacity_tags(target.opacity, filled),
        "fill": rf"\1c{_color(target.fill)}\2c{_color(target.fill)}",
        "outline": rf"\3c{_color(target.outline)}",
        "border": rf"\bord{_number(target.border)}",
        "blur": rf"\blur{_number(target.blur)}",
        "shadow": rf"\xshad{_number(target.shadow.x)}\yshad{_number(target.shadow.y)}",
    }
    target_tags = "".join(
        tag for channel, tag in tags.items()
        if channel in clip.animation.channels and not (omit_scale and channel == "scale")
    )
    if not target_tags:
        return ""
    tag = rf"\t({round((clip.start + start_offset) * 1000)},{round((clip.end + start_offset) * 1000)},{target_tags})"
    # libass applies transforms in order. Interpolating twice toward the
    # same alpha leaves (1-p)^2 of the initial difference.
    return tag * 2 if _native_fade_curve(clip.animation) else tag


def _tween_tags(leaf: _Leaf) -> str:
    return "".join(
        _tween_tag(
            replace(
                clip, start=local_seconds(owner.time_origin + clip.start, leaf.start)
            ),
            leaf.at(owner.time_origin + clip.end), filled=leaf.node.filled,
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
    if time not in leaf.rectangle_states:
        state = leaf.node.at(time)
        for parent in reversed(leaf.parents):
            state = compose_states(parent.at(time), state)
        leaf.rectangle_states[time] = state
    return leaf.rectangle_states[time]


def _rectangle_animation_known(clips: tuple[AnimationClip, ...]) -> bool:
    for clip in clips:
        animation = clip.animation
        if type(animation) is AnimationSequence:
            assert isinstance(animation, AnimationSequence)
            if not clip.hold or not _rectangle_animation_known(animation.clips):
                return False
        elif type(animation) is ScalePulse:
            if animation.rate is not linear_rate:
                return False
        elif type(animation) in (Tween, FadeIn, FadeOut):
            assert isinstance(animation, (Tween, FadeIn, FadeOut))
            if type(animation) is Tween and type(animation.target) is not StatePatch:
                return False
            if not clip.hold or (animation.rate is not linear_rate and not _native_fade_curve(animation)):
                return False
            if animation.channels & frozenset(("rotation", "skew")):
                return False
        else:
            return False
    return True


def _scale_polynomials(node: TextObject | PathObject) -> tuple[_ScalePolynomial, ...]:
    """Known scale polynomials as ordered ASS transforms, without clipped controls."""
    result = []
    for clip in _expanded_clips(node.animations):
        if "scale" not in clip.animation.channels:
            continue
        motion = clip.animation
        if type(motion) not in (ScalePulse, DriftOut):
            return ()
        assert isinstance(motion, (ScalePulse, DriftOut))
        if motion.rate not in (smooth_rate, smoother_rate) or not clip.hold:
            return ()
        first, last = node.time_origin + clip.start, node.time_origin + clip.end
        times = (
            (first, first + clip.duration * motion.peak_at, last)
            if isinstance(motion, ScalePulse) else (first, last)
        )
        knots = tuple((time, node.at(time).scale) for time in times)
        controls = (-2, 1, 1) if motion.rate is smooth_rate else (6, -9, 1, 1, 1)
        for (a, initial), (b, final) in zip(knots, knots[1:], strict=False):
            start, end = round(a * 1000) / 1000, round(b * 1000) / 1000
            delta = final - initial
            if end <= start:
                return ()
            # Both rates have speed <= 2. Bound phase-time rounding independently
            # of the existing geometry approximation, plus scale serialization.
            error = 2 * max(abs(delta.x), abs(delta.y)) * max(abs(start - a), abs(end - b)) / min(b - a, end - start)
            if error + 1e-8 > 0.001 or any(
                min(value.x, value.y) <= 1e-8
                for coefficient in controls
                for value in (initial + delta * coefficient,)
            ):
                return ()
        result.append(_ScalePolynomial(knots, controls))
    return tuple(result)


def _eased_rectangle_leaf(leaf: _Leaf, *, max_sections: int = 25_000) -> _Leaf:
    """Approximate known smooth motion internally, retaining source endpoints.

    The continuous linear-interpolation error is bounded by M*h*h/8, where M
    bounds the second derivative of each channel. Both supported rate polynomials have |f''| <= 6.
    Bounds are 0.1 parent pixels, 0.001 scale units and 1/255 opacity; rectangle
    edge rounding/interpolation is checked separately by the existing planner.
    Arbitrary callbacks, non-grid clocks and unrepresentable short curves are
    ineligible for this lowering. Author-owned declarations and the evaluator survive.
    """
    node = leaf.node
    clips = _expanded_clips(node.animations)
    if (
        not isinstance(node.clip, RectangleClip)
        or leaf.animated_pen
        or type(node.clip.deform) is not RectangleKeyframes
        or any(not (
            _rectangle_animation_known((clip,))
            or (type(clip.animation) in (ScalePulse, DriftOut)
                and isinstance(clip.animation, (ScalePulse, DriftOut))
                and clip.animation.rate in (smooth_rate, smoother_rate) and clip.hold
                and (not isinstance(clip.animation, DriftOut)
                     or clip.animation.travel_rate in (None, linear_rate, clip.animation.rate)))
        ) for clip in clips)
        or leaf.evaluator.referenced(node.id)
    ) or any(
        parent.state.scale != Vec2(1, 1)
        or parent.state.rotation != 0 or parent.state.skew != Vec2()
        or not _rectangle_animation_known(parent.animations)
        or any(clip.animation.channels - {"opacity"} for clip in parent.animations)
        for parent in leaf.parents
    ):
        return leaf
    result: list[AnimationClip] = []
    changed = False
    for clip in clips:
        motion = clip.animation
        if type(motion) not in (ScalePulse, DriftOut):
            result.append(clip)
            continue
        assert isinstance(motion, (ScalePulse, DriftOut))
        if motion.rate not in (smooth_rate, smoother_rate):
            result.append(clip)
            continue
        begin, finish = node.time_origin + clip.start, node.time_origin + clip.end
        if any(abs(t - _centiseconds(t) / 100) > 1e-9 for t in (begin, finish)):
            return leaf
        knots = (begin, finish)
        if isinstance(motion, ScalePulse):
            knots = (begin, begin + clip.duration * motion.peak_at, finish)
        # Each phase interpolates between two channel endpoints.
        # Even across the pulse peak the first derivative is continuous, so the
        # maximum of the two phase bounds remains valid for a crossing section.
        phases: list[tuple[float, float, float]] = []
        for a, b in zip(knots, knots[1:], strict=False):
            first, last = node.at(a), node.at(b)
            # A separately linear travel contributes no curvature. Remove it
            # before bounding the eased pivot compensation; endpoint cancellation
            # must never hide that compensation's second derivative.
            displacement = last.position - first.position
            if isinstance(motion, DriftOut) and motion.travel_rate is linear_rate:
                displacement -= motion.offset
            delta = (
                abs(displacement.x) / 0.1,
                abs(displacement.y) / 0.1,
                abs(last.scale.x - first.scale.x) / 0.001,
                abs(last.scale.y - first.scale.y) / 0.001,
                abs(last.opacity - first.opacity) * 255,
            )
            phases.append((a, b, max(delta) / (b - a) ** 2))
        pending = [(begin, finish)]
        sections: list[tuple[float, float]] = []
        while pending:
            if len(result) + len(sections) + len(pending) > max_sections:
                return leaf
            a, b = pending.pop()
            # Quintic smootherstep: f'' = 60*p*(2*p*p - 3*p + 1).
            # Its global absolute maximum is 10/sqrt(3) < 6; cubic
            # smoothstep admits the tighter endpoint bound on each subinterval.
            curvature = max(
                (
                    factor * (6 if motion.rate is smoother_rate else max(
                        abs(6 - 12 * (max(a, left) - left) / (right - left)),
                        abs(6 - 12 * (min(b, right) - left) / (right - left)),
                    ))
                    for left, right, factor in phases
                    if max(a, left) < min(b, right)
                ), default=0,
            )
            if curvature * (b - a) ** 2 / 8 > 1:
                middle = _centiseconds((a + b) / 2) / 100
                if not a < middle < b:
                    return leaf
                pending.extend(((middle, b), (a, middle)))
                continue
            sections.append((a, b))
        for a, b in sections:
            target = node.at(b)
            result.append(AnimationClip(
                start=local_seconds(a, node.time_origin), duration=local_seconds(b, a),
                animation=Tween(StatePatch(
                    position=target.position, scale=target.scale,
                    opacity=target.opacity if "opacity" in motion.channels else None,
                )),
            ))
        changed = True
    if not changed:
        return leaf
    candidate = replace(
        leaf, node=replace(node, animations=tuple(result)), rectangle_states={},
        scale_polynomials=_scale_polynomials(node),
    )
    return candidate if _native_rectangle(candidate) else leaf


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
            points.add(origin + clip.start + clip.duration * clip.animation.peak_at)
    if not points:
        return leaf.start, leaf.end
    return tuple(
        sorted({min(leaf.start, min(points)), *points, max(leaf.end, max(points))})
    )


def _bounded_screen_mask(
    source: RectangleClip | VectorClip | Literal[False] | None, width: int, height: int, max_points: int,
) -> RectangleClip | VectorClip | Literal[False] | None:
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
            max_points=max_points,
        )
        if bounded is None:
            if not source.inverse:
                return False
            source = None
        else:
            source = replace(source, path=bounded)
    return source


def _native_rectangle(leaf: _Leaf) -> bool:
    node = leaf.node
    if (
        not isinstance(node.clip, RectangleClip)
        or type(node.clip.deform) is not RectangleKeyframes
        or leaf.animated_pen
        or leaf.affine_paths
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
        type(clip.animation) is FadeIn
        and local_seconds(origin + clip.start, leaf.start) > 0
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
        and (node.clip.space == "screen" or state.rotation % 360 == 0
             or (node.material is None and state.rotation % 90 == 0
                 and all(c.animation.channels == {"opacity"} for _, c in owned)))
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
    leaf: _Leaf,
    time: float,
    *,
    before: bool = False,
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
        # A quarter turn keeps rectangles axis-aligned but can swap their extrema.
        return min(first.x, last.x), min(first.y, last.y), max(first.x, last.x), max(first.y, last.y)
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


def _rectangle_linear_anchor(leaf: _Leaf, first: float, last: float) -> bool:
    """Prove one linear move over the known piecewise-linear output anchor."""
    anchor = leaf.rectangle_anchor
    if anchor is None:
        return False
    points = (first, last, *(time for time in _rectangle_geometry_knots(leaf)
                            if first < time < last))
    origin = _rectangle_state(leaf, first).transform.apply(anchor)
    end = _rectangle_state(leaf, last).transform.apply(anchor)
    return all(
        abs(position.x - expected.x) <= 1e-8 and abs(position.y - expected.y) <= 1e-8
        for time in points
        for position in (_rectangle_state(leaf, time).transform.apply(anchor),)
        for expected in (origin.lerp(end, (time - first) / (last - first)),)
    )


def _rectangle_groups(
    leaf: _Leaf, sections: tuple[tuple[float, float], ...]
) -> tuple[tuple[tuple[float, float], ...], ...]:
    groups: list[list[tuple[float, float]]] = []
    for first, last in sections:
        if (
            groups
            and _rectangle_linear_anchor(leaf, groups[-1][0][0], last)
            and abs(groups[-1][-1][1] - first) <= 1e-9
            and all(abs(a - b) <= 1e-8 for a, b in zip(
                _rectangle_bounds(leaf, first, before=True),
                _rectangle_bounds(leaf, first), strict=True,
            ))
        ):
            # Compatible clip/scale/alpha transforms can share one ASS event.
            # A single move retains its original clock below. Keep resets
            # separate: an instantaneous discontinuity is not a linear tween.
            groups[-1].append((first, last))
        else:
            groups.append([(first, last)])
    return tuple(tuple(group) for group in groups)


def _rectangle_events(
    leaf: _Leaf,
    style: str,
    sections: tuple[tuple[float, float], ...],
) -> tuple[Line, ...]:
    node = leaf.node
    clip = node.clip
    assert isinstance(clip, RectangleClip)
    assert isinstance(clip.deform, RectangleKeyframes)
    kind = "iclip" if clip.inverse else "clip"

    def tag(time: float, *, before: bool = False) -> str:
        bounds = _rectangle_bounds(leaf, time, before=before)
        return rf"\{kind}({','.join(str(round(x)) for x in bounds)})"

    animations: list[tuple[float, AnimationClip]] = []
    for origin, animation in _rectangle_owned_clips(leaf):
        if type(animation.animation) is ScalePulse:
            animations.extend(
                (
                    origin,
                    replace(
                        animation,
                        start=animation.start + start * animation.duration,
                        duration=(end - start) * animation.duration,
                        breakpoints=(),
                    ),
                )
                for start, end in (
                    (0, animation.animation.peak_at),
                    (animation.animation.peak_at, 1),
                )
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
    # Studio rounds a descending cell front to the nearest pixel. libass
    # truncates the positive screen coordinate during a native clip tween.
    # Advance this uniform traverse by half a screen pixel's travel time.
    phase_ms = 0
    sweep_start = sweep_end = 0.0
    if (isinstance(clip, _CellWipeClip)
            and all(c.animation.channels == {"opacity"} for _, c in animations)):
        sweep_start, sweep_end = node.time_origin + clip.start, node.time_origin + clip.end
        initial = _rectangle_bounds(leaf, sweep_start)
        final = _rectangle_bounds(leaf, sweep_end)
        for index in (1, 3):
            distance = final[index] - initial[index]
            if initial[index] >= 0 and distance >= 1:
                phase_ms = round(500 * (clip.end - clip.start) / distance)
                break
    events: list[Line] = []
    for group in _rectangle_groups(leaf, sections):
        first, last = group[0][0], group[-1][1]
        start = _centiseconds(max(first, leaf.start))
        end = _centiseconds(min(last, leaf.end))
        spans = group
        if start >= end:
            continue
        tags = tag(spans[0][0])
        for t0, t1 in spans:
            final = tag(t1, before=True)
            if tag(t0) != final:
                a = round(t0 * 1000) - start * 10
                b = round(t1 * 1000) - start * 10
                if phase_ms and sweep_start <= t0 and t1 <= sweep_end and b > phase_ms:
                    a, b = a - phase_ms, b - phase_ms
                tags += rf"\t({a},{b},1,{final})"
        state = replace(
            _rectangle_state(leaf, node.time_origin),
            opacity=_rectangle_state(leaf, alpha_start).opacity,
        )
        for origin, animation in sorted(
            animations, key=lambda pair: pair[0] + pair[1].start
        ):
            if origin + animation.start >= end / 100:
                continue
            target = _rectangle_state(leaf, origin + animation.end)
            if round((origin + animation.end) * 1000) <= start * 10:
                # ASS treats a transform ending at 0 as ending at event end.
                # Fold completed channels into the header instead, retaining
                # original clocks only for active/future transforms.
                state = merge_channels(
                    state, target,
                    animation.animation.channels
                    - ({"position", "scale"} if leaf.scale_polynomials else {"position"}),
                )
            else:
                tags += _tween_tag(
                    animation, target, start_offset=origin - start / 100,
                    omit_scale=bool(leaf.scale_polynomials), filled=leaf.node.filled,
                )
        for polynomial in leaf.scale_polynomials:
            for (a, initial), (b, final) in zip(
                polynomial.knots, polynomial.knots[1:], strict=False,
            ):
                if initial == final:
                    continue
                begin_ms, end_ms = round(a * 1000), round(b * 1000)
                if begin_ms >= end * 10:
                    continue
                if end_ms <= start * 10:
                    state = replace(state, scale=final)
                    continue
                # Each transform blends the value left by its predecessor.
                # These controls expand to 3p²-2p³ or 6p⁵-15p⁴+10p³.
                # Unlike rectangular clips, libass keeps scale values in float.
                for coefficient in polynomial.controls:
                    value = initial + (final - initial) * coefficient
                    tags += (
                        rf"\t({begin_ms - start * 10},{end_ms - start * 10},"
                        rf"\fscx{_number(value.x * 100)}\fscy{_number(value.y * 100)})"
                    )
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
        if leaf.rectangle_anchor is not None:
            geometry_start, geometry_end = max(first, leaf.start), min(last, leaf.end)
        start_state = _rectangle_state(leaf, geometry_start)
        target = _rectangle_state(leaf, geometry_end)
        event_leaf = leaf
        if leaf.rectangle_anchor is not None:
            assert isinstance(node, TextObject)
            anchor = leaf.rectangle_anchor
            state = replace(state, position=start_state.transform.apply(anchor))
            target = replace(target, position=target.transform.apply(anchor))
            event_leaf = replace(leaf, node=replace(node, alignment=5))
        else:
            state = replace(state, position=start_state.position)
        a = round(geometry_start * 1000) - start * 10
        b = round(geometry_end * 1000) - start * 10
        event = _event(
            event_leaf,
            state,
            start,
            end,
            style,
            path=node.path if isinstance(node, PathObject) else None,
        )
        if state.position != target.position:
            event.text = event.text.replace(
                rf"\pos({_number(state.position.x)},{_number(state.position.y)})",
                rf"\move({_number(state.position.x)},{_number(state.position.y)},{_number(target.position.x)},{_number(target.position.y)},{a},{b})",
                1,
            )
        event.text = event.text.replace("}", tags + "}", 1)
        events.append(event)
    return tuple(events)


def _color(value: Color) -> str:
    return f"&H{value.blue:02X}{value.green:02X}{value.red:02X}&"


def _tags(state: VisualState, pen_scale: Vec2 | None = None, *, filled: bool = True) -> str:
    if pen_scale is None or not state.border:
        border = rf"\bord{_number(state.border)}"
    else:
        border = (
            rf"\xbord{_number(state.border * abs(pen_scale.x))}"
            rf"\ybord{_number(state.border * abs(pen_scale.y))}"
        )
    # Rotation is clockwise in the scene; ASS frz is counterclockwise.
    return (
        rf"\fscx{_number(state.scale.x * 100)}\fscy{_number(state.scale.y * 100)}"
        rf"\frz{_number(-state.rotation)}\frx0\fry0\fax{_number(state.skew.x)}\fay{_number(state.skew.y)}"
        rf"\1c{_color(state.fill)}\2c{_color(state.fill)}\3c{_color(state.outline)}\4c&H000000&"
        rf"{_opacity_tags(state.opacity, filled)}{border}\blur{_number(state.blur)}\be0"
        rf"\xshad{_number(state.shadow.x)}\yshad{_number(state.shadow.y)}"
    )


@lru_cache(maxsize=64)
def _object_drawing(path: VectorPath) -> tuple[int, str]:
    # libass rounds input coordinates to 1/64 before applying the object
    # transform. Keep thin features of unit-sized artwork at higher precision.
    bounds = path_bounds(path)
    if max(abs(bounds.left), abs(bounds.right), abs(bounds.top), abs(bounds.top + bounds.height)) <= 1:
        return 5, path.map(lambda point: point * 16).drawing()
    return 1, path.drawing()


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
    position = rf"\pos({_number(state.position.x)},{_number(state.position.y)})"
    if move:
        clip = node.animations[0]
        target = node.at(node.time_origin + clip.end).position
        position = (
            rf"\move({_number(state.position.x)},{_number(state.position.y)},{_number(target.x)},{_number(target.y)},"
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
            rf"\an{node.alignment}\fn{node.font}\fe{node.encoding}\fs{_number(node.font_size)}"
            rf"\b{int(node.bold)}\i{int(node.italic)}\u0\s0\fsp{_number(node.spacing)}\p0"
        )
    else:
        assert path is not None or isinstance(node, PathObject)
        drawing = node.path if isinstance(node, PathObject) and path is None else path
        assert drawing is not None
        if isinstance(node, PathObject) and node.deform is None and drawing is node.path:
            mode, content = _object_drawing(drawing)
        else:
            mode, content = 1, drawing.drawing()
        geometry = rf"\an7\p{mode}\pbo0"
    pen_scale = None
    if node.scale_border:
        pen_scale = leaf.affine_pen_scale or state.scale
    return Line(
        text="{"
        + rf"\r{style}\q2"
        + geometry
        + position
        + _tags(state, pen_scale, filled=leaf.node.filled)
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
    source = _bounded_screen_mask(resolved.clip, width, height, budget.max_path_points)
    if source is False:
        return _PaintedFrame((), resolved.peak_points)
    clip_points = max(
        resolved.peak_points,
        source.path.point_count if isinstance(source, VectorClip) else 0,
    )
    affine = (
        leaf.affine_paths
        or state.skew != Vec2()
        or min(state.scale.x, state.scale.y) <= 0
    )
    # With a top-left pen origin, ASS fay shears a glyph and its border
    # together. Baking only the fill outline would stroke it after the shear.
    if (
        affine and material is None and isinstance(leaf.node, TextObject)
        and leaf.node.scale_border and leaf.node.alignment == 7 and len(leaf.node.text) == 1
    ):
        matrix = state.transform
        if abs(matrix.c) < 1e-9 and matrix.a > 0 and matrix.d > 0:
            state = replace(state, scale=Vec2(matrix.a, matrix.d), rotation=0,
                            skew=Vec2(0, matrix.b / matrix.d))
            affine = False
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
        if leaf.node.scale_border:
            # The transformed path is already in screen axes. Preserve the
            # elliptical pen extents when resetting the ASS glyph transform.
            leaf = replace(leaf, affine_pen_scale=Vec2(
                hypot(linear.a, linear.c), hypot(linear.b, linear.d)
            ))
        state = replace(state, scale=Vec2(1, 1), rotation=0, skew=Vec2())
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
    native_tweens: bool = True,
    on_estimate: Callable[[SceneEstimate], None] | None = None,
) -> SceneResult:
    """Return a new Document. Source records and caller-owned nodes never mutate."""
    from .lyric_highlights import _FeatheredSingingClip

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
    if coverage:
        group = coverage[0]
        raise SceneCompileError(
            "ASS does not support raster coverage groups",
            object_id=group.id, origin=group.origin,
        )
    for leaf in leaves:
        node = leaf.node
        if node.extrusion is not None and node.extrusion.offset != Vec2():
            raise SceneCompileError("ASS does not support extrusion", object_id=node.id, origin=node.origin)
        if node.shader_paint is not None:
            raise SceneCompileError("ASS does not support shader paint", object_id=node.id, origin=node.origin)
        if node.material is not None:
            raise SceneCompileError(
                f"ASS does not support {type(node.material).__name__} paint fields",
                object_id=node.id, origin=node.origin,
            )
        if isinstance(node.clip, _ColorStripClip):
            raise SceneCompileError(
                "ASS does not support moving color strips for soft scanlines or blended glow",
                object_id=node.id, origin=node.origin,
            )
        if isinstance(node.clip, _FeatheredSingingClip):
            raise SceneCompileError(
                "ASS does not support feathered wipes (use a hard edge or export a hook)",
                object_id=node.id, origin=node.origin,
            )
    approximated: set[str] = set()
    if native_tweens:
        lowered = []
        for leaf in leaves:
            candidate = _eased_rectangle_leaf(leaf, max_sections=budget.max_events)
            if candidate is not leaf:
                approximated.add(leaf.node.id)
            lowered.append(candidate)
        leaves = tuple(lowered)
    meta = Document.parse(scene.document.dumps()).meta
    width, height = meta.res_x, meta.res_y
    outlines: dict[str, VectorPath | None] = {}
    estimate = 2 * len(native)
    max_quantization = 0.0
    rectangle_plans: dict[str, tuple[tuple[float, float], ...]] = {}
    rectangle_anchors: dict[str, Vec2] = {}
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
                    for time in mask.deform.breakpoints:
                        value = owner.time_origin + time
                        max_quantization = max(
                            max_quantization, abs(value - _centiseconds(value) / 100)
                        )
        rectangle = native_tweens and _native_rectangle(leaf)
        if rectangle:
            if isinstance(node, TextObject) and node.alignment == 7 and "\n" not in node.text:
                text_width, text_height, _, _ = text_extents(Style(
                    fontname=node.font, fontsize=node.font_size, bold=node.bold,
                    italic=node.italic, spacing=node.spacing, encoding=node.encoding, outline=0,
                ), node.text)
                leaf = replace(leaf, rectangle_anchor=Vec2(text_width / 2, text_height / 2))
            if leaf.rectangle_anchor is not None:
                rectangle_anchors[node.id] = leaf.rectangle_anchor
            rectangle_plans[node.id] = _rectangle_sections(leaf, budget)
        native_strategy = (
            not leaf.dynamic
            or _native_move(leaf)
            or (native_tweens and _native_tween(leaf))
            or rectangle
        )
        if not native_strategy:
            raise SceneCompileError(
                "ASS does not support this animation or clip because it requires frame sampling",
                object_id=node.id, origin=node.origin,
            )
        estimate += len(_rectangle_groups(leaf, rectangle_plans[node.id])) if rectangle else 1
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
        leaves
        and style.name in output.styles
        and output.styles[style.name].serialize() != style.serialize()
    ):
        raise SceneCompileError(
            "generated style name collides with a different source style"
        )
    generated: list[Line] = []
    if on_estimate is not None:
        on_estimate(SceneEstimate(estimate))
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
        tween = not move and native_tweens and _native_tween(leaf)
        rectangle = node.id in rectangle_plans
        peak_path_points = node.path.point_count if isinstance(node, PathObject) else 0
        peak_clip_points = 0
        if rectangle:
            if node.id in rectangle_anchors:
                leaf = replace(leaf, rectangle_anchor=rectangle_anchors[node.id])
            for event in _rectangle_events(leaf, style.name, rectangle_plans[node.id]):
                append(event, node.id, node.origin)
            strategy = "native-clip"
            if node.id in approximated:
                strategy += "-eased"
        else:
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
            for event in events:
                if tween:
                    event.text = event.text.replace("}", _tween_tags(leaf) + "}", 1)
                    movement = next((
                        clip for clip in _expanded_clips(node.animations)
                        if "position" in clip.animation.channels
                    ), None)
                    if movement is not None:
                        a = leaf.at(node.time_origin + movement.start).position
                        b = leaf.at(node.time_origin + movement.end).position
                        start_ms = round((node.time_origin + movement.start - leaf.start) * 1000)
                        end_ms = round((node.time_origin + movement.end - leaf.start) * 1000)
                        initial = leaf.at(leaf.start).position
                        event.text = event.text.replace(
                            rf"\pos({_number(initial.x)},{_number(initial.y)})",
                            rf"\move({_number(a.x)},{_number(a.y)},{_number(b.x)},{_number(b.y)},{start_ms},{end_ms})",
                            1,
                        )
                append(event, node.id, node.origin)
            strategy = (
                "native-move" if move else "native-tween" if tween else "native-static"
            )
        if affine:
            strategy += "-affine-path"
        reports.append(
            ObjectReport(
                node.id,
                strategy,
                len(generated) - before,
                node.origin,
                peak_path_points=peak_path_points,
                peak_clip_points=peak_clip_points
                if peak_clip_points or any(n.clip is not None for n in (*leaf.parents, node))
                else None,
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
        _insert_events(output, generated, style if leaves else None)
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
        event_origins=tuple(
            (event, event_origins[id(event)])
            for event in generated
            if not event.comment
        ),
    )
