"""Partition each leaf at authored clock boundaries. Only opaque spans need sampling."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from itertools import pairwise
from math import ceil
from typing import TypeGuard

from ._gpu import GpuClip
from ._gpu_scene import DrawCommand, SceneFrames
from ._karaoke_motion import Slide
from .scene import RectangleClip, RectangleKeyframes, VisualNode
from .scene_animation import (
    AnimationClip,
    DriftOut,
    FadeIn,
    FadeOut,
    ScalePulse,
    StateAnimation,
    Transform,
    Tween,
    VisualState,
    evaluate_clips,
    linear_rate,
    local_seconds,
    smooth_rate,
    smoother_rate,
)
from .scene_evaluation import compose_states
from .scene_output import _Leaf
from .timeline import ProgressCurve


@dataclass(frozen=True)
class Motion:
    start: float
    duration: float
    peak: float
    curve: int | ProgressCurve | tuple[float, ...]
    end: VisualState
    fast_reveal: bool


@dataclass(frozen=True)
class Span:
    first: int
    stop: int
    draw: DrawCommand
    motion: Motion | None = None
    clip_end: tuple[float, float, float, float] | None = None


def _supported(
    a: StateAnimation,
) -> TypeGuard[ScalePulse | DriftOut | FadeIn | FadeOut | Tween | Slide]:
    return type(a) in (ScalePulse, DriftOut, FadeIn, FadeOut, Tween, Slide)


def _curve(
    clip: AnimationClip,
) -> int | ProgressCurve | Callable[[float], float] | None:
    a = clip.animation
    if not _supported(a):
        return None
    if (
        isinstance(a, DriftOut)
        and a.travel_rate is not None
        and a.travel_rate is not a.rate
    ):
        return None
    if isinstance(a, Tween) and not a.channels <= {"position", "scale", "opacity"}:
        return None
    for index, rate in enumerate((linear_rate, smooth_rate, smoother_rate)):
        if a.rate is rate:
            return index
    owner = getattr(a.rate, "__self__", None)
    if type(owner) is ProgressCurve and a.rate == owner.at:
        return owner
    return a.rate


def _poses(
    leaf: _Leaf, owner: VisualNode, clip: AnimationClip, time: float
) -> tuple[VisualState, VisualState]:
    """Use Scene's own capture, easing endpoints and hierarchy composition."""
    a = clip.animation
    assert _supported(a)
    before = tuple(c for c in owner.animations if c.start < clip.start)

    base = evaluate_clips(owner.state, before, clip.start)
    # Use normalized weight endpoints; the shader applies the curve once.
    linear = replace(a, rate=linear_rate)
    if isinstance(linear, DriftOut):
        linear = replace(linear, travel_rate=None)
    poses = (
        linear.sample(base, 0),
        linear.sample(base, a.peak_at if isinstance(a, ScalePulse) else 1),
    )
    result = []
    for pose in poses:
        world = VisualState()
        for node in (*leaf.parents, leaf.node):
            state = pose if node is owner else node.at(time)
            world = compose_states(world, state)
        result.append(world)
    return result[0], result[1]


def _varies(clip: AnimationClip) -> bool:
    animation = clip.animation
    if type(animation) is Transform:
        return any(
            callable(value)
            for value in (
                animation.offset,
                animation.scale,
                animation.rotation,
                animation.opacity,
            )
        )
    return True


def spans(
    frames: SceneFrames, leaf: _Leaf, fps: int, first: int, stop: int
) -> Iterator[Span]:
    def grid(seconds: float) -> int:
        return ceil(round(seconds * fps, 9))

    first, stop = max(first, grid(leaf.start)), min(stop, grid(leaf.end))
    if first >= stop:
        return
    nodes = (*leaf.parents, leaf.node)
    clips = [(n, c) for n in nodes for c in n.animations]
    bounds = {first, stop}
    for n, c in clips:
        bounds.update(grid(n.time_origin + t) for t in (c.start, c.end))
    varying = [(node, clip) for node, clip in clips if _varies(clip)]
    rect = leaf.node.clip
    assert rect is None or isinstance(rect, RectangleClip)
    keys = rect.deform if rect else None
    if isinstance(keys, RectangleKeyframes):
        bounds.update(grid(leaf.node.time_origin + t) for t in keys.breakpoints)
    opaque = leaf.evaluator.referenced(leaf.node.id) or (
        keys is not None and not isinstance(keys, RectangleKeyframes)
    )
    for lo, hi in pairwise(sorted(x for x in bounds if first <= x <= stop)):
        t = lo / fps
        active = [
            (n, c)
            for n, c in varying
            if local_seconds(c.start, 0)
            <= local_seconds(t, n.time_origin)
            < local_seconds(c.end, 0)
        ]
        curve = _curve(active[0][1]) if len(active) == 1 else None
        # A disjoint-channel clip can capture an active channel. Keep the evaluator
        # for those combinations instead of reconstructing their capture order.
        if curve is not None:
            n, c = active[0]
            if any(
                other is not c and other.start < c.end and c.start < other.end
                for other in n.animations
            ):
                curve = None
        # An opaque easing only needs one scalar per requested phase. Identical
        # scalar tracks share an interned record even for distinct callables.
        if (
            curve is not None
            and not isinstance(curve, (int, ProgressCurve))
            and not opaque
        ):
            n, c = active[0]
            values: list[float] = []
            for i in range(lo, hi):
                p = min(
                    1.0,
                    max(
                        0.0,
                        local_seconds(local_seconds(i / fps, n.time_origin), c.start)
                        / c.duration,
                    ),
                )
                if isinstance(c.animation, ScalePulse):
                    peak = c.animation.peak_at
                    value = (
                        0.0
                        if p in (0, 1)
                        else curve(p / peak if p <= peak else (1 - p) / (1 - peak))
                    )
                else:
                    value = curve(p)
                values.append(value)
            curve = tuple(values) if all(0 <= v <= 1 for v in values) else None
        if opaque or (active and curve is None):
            for i in range(lo, hi):
                draw = frames.draw_at(leaf, i / fps)
                if draw is not None:
                    yield Span(i, i + 1, draw)
            continue
        clip = None
        clip_end = None
        if rect is not None:
            if isinstance(keys, RectangleKeyframes):
                left = keys.bounds_at(local_seconds(t, leaf.node.time_origin))
                right = keys.bounds_at(
                    local_seconds((hi - 1) / fps, leaf.node.time_origin)
                )
                if left != right:
                    clip_end = right
            else:
                left = (rect.left, rect.top, rect.right, rect.bottom)
            if clip_end is None and (left[0] == left[2] or left[1] == left[3]):
                continue
            clip = GpuClip(left, local=rect.space == "local")
        motion = None
        if curve is not None:
            n, c = active[0]
            state, end = _poses(leaf, n, c, t)
            assert not callable(curve)
            motion = Motion(
                n.time_origin + c.start,
                c.duration,
                c.animation.peak_at if isinstance(c.animation, ScalePulse) else 0,
                curve,
                end,
                isinstance(c.animation, Slide)
                and c.animation.entering
                and c.animation.fast_reveal,
            )
        else:
            state = leaf.at(t)
            if state.opacity == 0 or state.singular:
                continue
        yield Span(lo, hi, frames.draw_state(leaf, state, clip), motion, clip_end)
