"""Partition each leaf at authored clock boundaries. Lower supported animations to seekable shader parameters."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from itertools import pairwise
from math import ceil
from typing import TypeGuard

from ._contour_stroke import ContourStroke
from ._gpu_scene import (
    DrawCommand,
    GpuClip,
    SceneFrames,
    _ExtrusionSide,
)
from ._karaoke_motion import RowSlide, ZoomScale
from ._native_types import RasterImage
from ._path_raster import cutout_border
from ._scene_tree import SceneLeaf
from .easing import ease_in, ease_in_out, ease_out
from .scene import RectangleClip, RectangleKeyframes, SceneCompileError, VisualNode
from .scene_animation import (
    AnimationClip,
    DriftOut,
    FadeIn,
    FadeOut,
    Jump,
    ScalePulse,
    ShaderMotion,
    Slide,
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
from .timeline import ProgressCurve

_IDENTITY = VisualState()


@dataclass(frozen=True)
class Motion:
    start: float
    duration: float
    peak: float
    curve: int | ProgressCurve | ZoomScale
    end: VisualState
    fast_reveal: bool


@dataclass(frozen=True)
class ShaderInstance:
    program: ShaderMotion
    start: float
    duration: float
    outer: VisualState
    base: VisualState
    inner: VisualState
    local: bool


@dataclass(frozen=True)
class Span:
    first: int
    stop: int
    draw: DrawCommand
    motion: Motion | None = None
    clip_keys: RectangleKeyframes | None = None
    alternate_masks: tuple[RasterImage, ...] | None = None
    shader: ShaderInstance | None = None


def _supported(
    a: StateAnimation,
) -> TypeGuard[ScalePulse | DriftOut | FadeIn | FadeOut | Tween | Slide]:
    return type(a) in (ScalePulse, DriftOut, FadeIn, FadeOut, Tween, Slide, RowSlide)


def _curve(
    clip: AnimationClip,
) -> int | ProgressCurve | ZoomScale | None:
    a = clip.animation
    if isinstance(a, Jump):
        return 6
    if (
        isinstance(a, Transform)
        and isinstance(a.scale, ZoomScale)
        and a.offset is None
        and a.opacity is None
        and a.rotation is None
    ):
        return a.scale
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
    for index, rate in enumerate(
        (linear_rate, smooth_rate, smoother_rate, ease_in, ease_out, ease_in_out)
    ):
        if a.rate is rate:
            return index
    owner = getattr(a.rate, "__self__", None)
    if type(owner) is ProgressCurve and a.rate == owner.at:
        return owner
    return None


def _poses(
    leaf: SceneLeaf,
    owner: VisualNode,
    clip: AnimationClip,
    time: float,
    parent: VisualState | None,
) -> tuple[VisualState, VisualState]:
    """Use Scene's own capture, easing endpoints and hierarchy composition."""
    a = clip.animation
    before = tuple(c for c in owner.animations if c.start < clip.start)

    base = evaluate_clips(owner.state, before, clip.start)
    # Use normalized weight endpoints; the shader applies the curve once.
    if isinstance(a, Jump):
        poses = (base, a.sample(base, 0.5))
    elif isinstance(a, Transform):
        poses = (base, replace(a, scale=1.1).sample(base, 1))
    else:
        assert _supported(a)
        linear = replace(a, rate=linear_rate)
        if isinstance(linear, DriftOut):
            linear = replace(linear, travel_rate=None)
        poses = (
            linear.sample(base, 0),
            linear.sample(base, a.peak_at if isinstance(a, ScalePulse) else 1),
        )
    if parent is not None and owner is leaf.node:
        return compose_states(parent, poses[0]), compose_states(parent, poses[1])
    result = []
    nodes = (*leaf.parents, leaf.node)
    context = [None if node is owner else node.at(time) for node in nodes]
    for pose in poses:
        states = iter(pose if state is None else state for state in context)
        world = next(states)
        for state in states:
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
    frames: SceneFrames, leaf: SceneLeaf, fps: int, first: int, stop: int
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
    opaque = leaf.evaluator.referenced(leaf.node.id) or (
        keys is not None and not isinstance(keys, RectangleKeyframes)
    )
    parent = None
    if not any(node.animations for node in leaf.parents):
        parent = _IDENTITY
        for node in leaf.parents:
            parent = compose_states(parent, node.state)
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
                other is not c
                and local_seconds(other.start, c.end) < 0
                and local_seconds(c.start, other.end) < 0
                for other in n.animations
            ):
                curve = None
        shader = None
        if len(active) == 1:
            owner, clip = active[0]
            program = clip.animation
            if isinstance(program, ShaderMotion) and "border" in program.channels and not (
                owner is leaf.node and isinstance(leaf.node.shader_paint, ContourStroke)
            ):
                raise SceneCompileError("animated border requires a local contour stroke",
                                        object_id=leaf.node.id, origin=leaf.node.origin)
            if isinstance(program, ShaderMotion) and not any(
                other is not clip
                and local_seconds(other.start, clip.end) < 0
                and local_seconds(clip.start, other.end) < 0
                for other in owner.animations
            ):
                index = nodes.index(owner)
                outer = inner = _IDENTITY
                if parent is not None and owner is leaf.node:
                    outer = parent
                else:
                    for node in nodes[:index]:
                        outer = compose_states(outer, node.at(t))
                for node in nodes[index + 1 :]:
                    inner = compose_states(inner, node.at(t))
                before = tuple(c for c in owner.animations if c.start < clip.start)
                base = evaluate_clips(owner.state, before, clip.start)
                shader = ShaderInstance(
                    program,
                    owner.time_origin + clip.start,
                    clip.duration,
                    outer,
                    base,
                    inner,
                    owner is leaf.node,
                )
        if opaque or (active and curve is None and shader is None):
            if leaf.evaluator.referenced(leaf.node.id):
                reason = "reference-dependent transform"
            elif opaque:
                reason = f"clip deformation {type(keys).__name__}"
            elif len(active) > 1:
                reason = "overlapping " + ", ".join(
                    type(c.animation).__name__ for _, c in active
                )
            else:
                owner, unsupported = active[0]
                reason = f"{type(unsupported.animation).__name__} on {owner.id!r} (channels, easing or overlap)"
            raise SceneCompileError(
                f"hook cannot compile at {t:g}s: {reason}",
                object_id=leaf.node.id,
                origin=leaf.node.origin,
            )
        clip = None
        if rect is not None:
            clip = GpuClip(
                (rect.left, rect.top, rect.right, rect.bottom),
                local=rect.space == "local",
            )
        motion = None
        if shader is not None:
            state = compose_states(shader.outer, shader.base)
            if active[0][0] is not leaf.node:
                state = compose_states(state, shader.inner)
        elif curve is not None:
            n, c = active[0]
            state, end = _poses(leaf, n, c, t, parent)
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
            state = (
                leaf.at(t)
                if parent is None
                else compose_states(parent, leaf.node.at(t))
            )
            if state.opacity == 0 or state.singular:
                continue
        varying_basis = (
            motion is not None and replace(state.transform, tx=0, ty=0)
            != replace(motion.end.transform, tx=0, ty=0)
            or shader is not None and bool(shader.program.channels & {"scale", "skew", "rotation"})
        )
        draw = frames.draw_state(leaf, state, clip, varying_basis=varying_basis)
        alternate = None
        filled = leaf.node.filled
        cutout = cutout_border(state, filled)
        if (not isinstance(leaf, _ExtrusionSide) and motion
                and cutout != cutout_border(motion.end, filled)):
            other = replace(state, opacity=motion.end.opacity)
            alternate = frames.draw_state(leaf, other, clip, varying_basis=varying_basis).images
        if (not isinstance(leaf, _ExtrusionSide) and shader is not None and filled
                and state.border > 0 and round((1 - state.face_opacity) * 255) == 0):
            other = replace(state, opacity=1 if cutout else 0.5)
            alternate = frames.draw_state(leaf, other, clip, varying_basis=varying_basis).images
        yield Span(
            lo,
            hi,
            draw,
            motion,
            keys if isinstance(keys, RectangleKeyframes) else None,
            alternate,
            shader,
        )
