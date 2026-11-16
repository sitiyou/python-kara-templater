"""Document-backed, explicitly sampled coverage materials → standard ASS."""

from dataclasses import dataclass, replace
from math import ceil, isclose

from ._raster import PositionedFrame, encode_frame, quantize_frame
from ._raster_alpha import apply_opacity
from ._scene_coverage import SceneCoverageSampler
from .ass import Line
from .coverage_animation import GlowFunction
from .raster_settings import RasterSettings
from .scene import ObjectGroup, PathObject, SceneObject
from .scene_animation import (
    AnimationClip,
    AnimationSequence,
    FadeIn,
    FadeOut,
    Tween,
    evaluate_clips,
    linear_rate,
    local_seconds,
)
from .scene_evaluation import SceneEvaluator
from .scene_output import (
    SceneBudget,
    SceneCompileError,
    _centiseconds,
    _expanded_clips,
)
from .sources import EventOrigin
from .timeline import DisplayWindow

_DEFAULT_SETTINGS = RasterSettings()
_DEFAULT_BUDGET = SceneBudget()


def _opacity_curve(group: ObjectGroup) -> tuple[tuple[int, float], ...] | None:
    """Prove a continuous piecewise-linear curve without author callbacks."""

    def known(clip: AnimationClip) -> bool:
        animation = clip.animation
        if "opacity" not in animation.channels:
            return True
        if type(animation) is AnimationSequence:
            assert isinstance(animation, AnimationSequence)
            return clip.hold and all(known(child) for child in animation.clips)
        return type(animation) in (Tween, FadeIn, FadeOut)

    if not all(known(clip) for clip in group.animations):
        return None
    clips = tuple(
        clip
        for clip in _expanded_clips(group.animations)
        if "opacity" in clip.animation.channels
    )
    if not clips:
        return None
    for clip in clips:
        animation = clip.animation
        if type(animation) not in (Tween, FadeIn, FadeOut):
            return None
        assert isinstance(animation, (Tween, FadeIn, FadeOut))
        if animation.rate is not linear_rate:
            return None
    start = group.lifetime.start
    offset = local_seconds(start, group.time_origin)
    duration = local_seconds(group.lifetime.end, start)
    knots = sorted(
        {
            0.0,
            duration,
            *(
                value
                for clip in clips
                for value in (clip.start - offset, clip.end - offset)
                if 0 < value < duration
            ),
        }
    )
    if any(abs(start + t - _centiseconds(start + t) / 100) > 1e-8 for t in knots):
        return None

    def value(time: float) -> float:
        return evaluate_clips(group.state, clips, time + offset).opacity

    # Known curves are linear inside each interval. Derive their left endpoint
    # from the midpoint, rather than nextafter: the common clock intentionally
    # treats adjacent floating-point values as the same 1e-10s instant.
    left_values = tuple(
        2 * value((a + b) / 2) - value(a)
        for a, b in zip(knots, knots[1:], strict=False)
    )
    for local, left in zip(knots[1:-1], left_values, strict=False):
        if not isclose(
            left,
            value(local),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            return None
    return tuple(
        (
            _centiseconds(start + time) * 10,
            min(1, max(0, left_values[-1])) if time == duration else value(time),
        )
        for time in knots
    )


def _sample_grid(
    sampler: SceneCoverageSampler,
    settings: RasterSettings,
    budget: SceneBudget,
    interval: tuple[float, float] | None = None,
) -> tuple[tuple[int, ...], float]:
    group = sampler.group
    start, end = map(
        _centiseconds, interval or (group.lifetime.start, group.lifetime.end)
    )
    frames = ceil((end - start) / 100 * budget.fps)
    if end <= start or frames > settings.max_frames:
        raise SceneCompileError(
            "coverage frame budget exceeded or empty lifetime",
            object_id=group.id,
            origin=group.origin,
        )
    times: set[float] = set()

    def visit(node: SceneObject) -> None:
        times.update(sampler.evaluator.breakpoints(node.id))
        if node.clip is not None and node.clip.deform is not None:
            times.update(node.time_origin + t for t in node.clip.deform.breakpoints)
        if node.material is not None:
            times.update(node.time_origin + t for t in node.material.breakpoints)
        if isinstance(node, PathObject) and node.deform is not None:
            times.update(node.time_origin + t for t in node.deform.breakpoints)
        if isinstance(node, ObjectGroup):
            for child in node.children:
                visit(child)

    visit(group)
    for name, leaf in sampler.leaves.items():
        if _centiseconds(leaf.end) <= _centiseconds(leaf.start):
            raise SceneCompileError(
                "lifetime vanishes on ASS centisecond grid",
                object_id=name,
                origin=leaf.node.origin,
            )
        birth = leaf.node.time_origin
        glow = sampler.glows.get(name)
        if isinstance(glow, GlowFunction):
            times.update(birth + t for t in glow.breakpoints)
        field = sampler.glow_materials.get(name)
        if field is not None:
            times.update(birth + t for t in field.breakpoints)
        partition = sampler.partitions.get(name)
        if partition is not None:
            times.update(birth + t for t in partition.breakpoints)
        owners = {node.id: node for node in (*leaf.parents, leaf.node)}
        for rule in sampler.scope_opacities.get(name, ()):
            times.update(
                owners[rule.owner].time_origin + t for t in rule.breakpoints
            )
    points = {start, end}
    points.update(_centiseconds(start / 100 + i / budget.fps) for i in range(1, frames))
    points.update(max(start, min(end, _centiseconds(t))) for t in times)
    if len(points) - 1 > settings.max_frames:
        raise SceneCompileError(
            "coverage frame budget exceeded after boundary splitting",
            object_id=group.id,
            origin=group.origin,
        )
    error = max((abs(t - _centiseconds(t) / 100) for t in times), default=0)
    return tuple(sorted(points)), error


@dataclass(frozen=True)
class _CoverageOutput:
    events: tuple[Line, ...]
    origin: EventOrigin | None
    sample_times: tuple[float, ...]
    max_channel_error: int
    time_error: float
    native_opacity: bool


@dataclass(frozen=True)
class _PreparedCoverage:
    group: ObjectGroup
    sampler: SceneCoverageSampler
    points: tuple[int, ...]
    time_error: float
    has_parents: bool


def _prepare_coverage(
    group: ObjectGroup,
    *,
    resolution: tuple[int, int],
    budget: SceneBudget,
    parents: tuple[ObjectGroup, ...] = (),
    interval: tuple[float, float] | None = None,
    evaluator: SceneEvaluator | None = None,
) -> _PreparedCoverage:
    """Validate coverage and plan its sample grid without running callbacks."""
    config = group.coverage
    assert config is not None
    settings = config.settings
    branch = replace(group, coverage=None)
    for parent in reversed(parents):
        branch = replace(parent, children=(branch,))
    sampler = SceneCoverageSampler(
        branch,
        evaluator=evaluator,
        resolution=resolution,
        glows=config.glows,
        glow_materials=config.glow_materials,
        components=config.components,
        scope_opacities=config.scope_opacities,
        partitions=config.partitions,
        settings=settings,
        budget=budget,
    )
    points, time_error = _sample_grid(sampler, settings, budget, interval)
    return _PreparedCoverage(group, sampler, points, time_error, bool(parents))


def _lower_coverage(
    prepared: _PreparedCoverage, *, style: str, native_tweens: bool = False
) -> _CoverageOutput:
    """Sample the validated plan and encode its composed pixels as standard ASS."""
    group, sampler = prepared.group, prepared.sampler
    config = group.coverage
    assert config is not None
    settings, budget = config.settings, sampler.budget
    resolution = sampler.resolution
    points, time_error = prepared.points, prepared.time_error
    # Parent and per-material weighted alpha need a separate factorization proof.
    # Unsupported declarations retain the normal sampled composition semantics.
    curve = (
        _opacity_curve(group)
        if native_tweens
        and not prepared.has_parents
        and not any(config.scope_opacities.values())
        else None
    )
    sampler.exclude_root_opacity = curve is not None
    origins = tuple(
        leaf.node.origin
        for leaf in sampler.leaves.values()
        if leaf.node.origin is not None
    )
    sources = tuple(dict.fromkeys(ref for origin in origins for ref in origin.sources))
    tracks = tuple(
        dict.fromkeys(track for origin in origins for track in origin.track_ids)
    )
    origin = group.origin or (
        EventOrigin(sources, "coverage group", tracks) if sources else None
    )
    previous: PositionedFrame | None = None
    pending: dict[str, Line] = {}
    count = characters = 0
    events: list[Line] = []
    for left, right in zip(points, points[1:], strict=False):
        frame = sampler.frame((left + right) / 200)
        if frame is not None:
            frame = (
                frame[0],
                frame[1],
                quantize_frame(frame[2], settings.max_channel_error),
            )
        if frame == previous:
            for event in pending.values():
                event.end_time = right * 10
            continue
        previous = frame
        encoded = (
            ()
            if frame is None
            else encode_frame(
                frame[2],
                DisplayWindow(left * 10, right * 10),
                style=style,
                position=(frame[0], frame[1]),
                resolution=resolution,
                neutral_style=True,
                budget=sampler.raster_budget,
            )
        )
        if len(encoded) > budget.max_active:
            raise SceneCompileError(
                "coverage peak active budget exceeded", object_id=group.id
            )
        current: dict[str, Line] = {}
        for event in encoded:
            prior = pending.get(event.text)
            if prior is not None and prior.end_time == event.start_time:
                prior.end_time = event.end_time
                current[event.text] = prior
                continue
            current[event.text] = event
            count += 1
            characters += len(event.text)
            if count > budget.max_events or characters > settings.max_output_chars:
                raise SceneCompileError(
                    "coverage output budget exceeded", object_id=group.id
                )
            event.layer = group.layer
            events.append(event)
        pending = current
    if curve is not None:
        characters = 0
        changes: list[tuple[float, int]] = []
        for event in events:
            event.text = apply_opacity(event.text, round(event.start_time), curve)
            size = len(event.text)
            characters += size
            changes.extend(((event.start_time, size), (event.end_time, -size)))
        if characters > settings.max_output_chars:
            raise SceneCompileError(
                "coverage output budget exceeded after opacity lowering",
                object_id=group.id,
            )
        active = 0
        for _, delta in sorted(changes):
            active += delta
            if active > settings.max_frame_chars:
                raise SceneCompileError(
                    "coverage frame character budget exceeded after opacity lowering",
                    object_id=group.id,
                )
    return _CoverageOutput(
        tuple(events),
        origin,
        tuple((a + b) / 200 for a, b in zip(points, points[1:], strict=False)),
        settings.max_channel_error,
        time_error,
        curve is not None,
    )
