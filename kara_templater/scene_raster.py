"""Explicit, bounded offscreen group composition into standard ASS pixel runs."""

from dataclasses import dataclass, replace
from math import ceil

from ._material_raster import blur_frame
from ._raster import (
    RasterBudget,
    RasterCanvas,
    RasterFrame,
    encode_frame,
    quantize_frame,
    rasterize,
)
from .ass import Document, Line, Style
from .geometry import finite
from .raster_settings import RasterSettings
from .scene import NativeEvent, ObjectGroup, Scene
from .scene_animation import AnimationClip, StateFunction, VisualState
from .scene_output import SceneBudget, _centiseconds
from .sources import EventOrigin
from .timeline import DisplayWindow

_DEFAULT_SETTINGS = RasterSettings()
_DEFAULT_BUDGET = SceneBudget()


@dataclass(frozen=True)
class RasterizedGroup:
    """Baked standard-ASS scene and its explicit sampling/quantization costs."""

    scene: Scene
    sampled_frames: int
    source_events: int
    max_channel_error: int


def rasterize_group(
    group: ObjectGroup,
    *,
    resolution: tuple[int, int],
    blur_radius: float = 0,
    settings: RasterSettings = _DEFAULT_SETTINGS,
    budget: SceneBudget = _DEFAULT_BUDGET,
) -> RasterizedGroup:
    """Bake a group's already-lowered picture, then apply its root opacity once.

    The viewport-clipped RGBA picture is blurred in premultiplied space before
    root opacity is applied. Child and root masks act before this group blur;
    offscreen content beyond the viewport cannot contribute to the blur.
    Descendant opacity retains ordinary Scene semantics. The root must be
    self-contained: external references are diagnosed by the Scene compiler.
    Geometry first uses the Scene sampling strategy, then pixel frames are
    sampled at the declared output grid. No tighter temporal error is claimed.
    """
    finite(blur_radius)
    if not 0 <= blur_radius <= 100:
        raise ValueError("group blur radius must be in 0..100 ASS pixels")
    start, end = _centiseconds(group.lifetime.start), _centiseconds(group.lifetime.end)
    frames = ceil((end - start) / 100 * budget.fps)
    if end <= start or frames > settings.max_frames:
        raise ValueError(f"{group.id}: raster frame budget exceeded or empty lifetime")
    raster_budget = RasterBudget(
        max_pixels=settings.max_pixels,
        max_images=settings.max_images,
        max_events=settings.max_frame_events,
        max_rectangles=settings.max_rectangles,
        max_path_chars=settings.max_frame_chars,
    )
    raster_budget.check_pixels(*resolution)
    if group.reference is not None:
        raise ValueError(
            f"{group.id}: offscreen root references require explicit prior evaluation"
        )
    channels = frozenset(
        channel
        for clip in group.animations
        for channel in clip.animation.channels
        if channel != "opacity"
    )

    def geometry(base: VisualState, progress: float) -> VisualState:
        time = group.lifetime.start + progress * (
            group.lifetime.end - group.lifetime.start
        )
        return replace(group.at(time), opacity=1)

    source_group = replace(
        group,
        state=replace(group.state, opacity=1),
        animations=(
            AnimationClip(
                group.lifetime.start - group.time_origin,
                group.lifetime.end - group.lifetime.start,
                StateFunction(geometry, channels),
                breakpoints=tuple(
                    sorted(
                        {
                            value + group.time_origin - group.lifetime.start
                            for clip in group.animations
                            for value in (
                                clip.start,
                                clip.end,
                                *(clip.start + t for t in clip.breakpoints),
                            )
                            if group.lifetime.start
                            <= group.time_origin + value
                            <= group.lifetime.end
                        }
                    )
                ),
            ),
        )
        if channels
        else (),
    )
    width, height = resolution
    source = (
        Scene(Document.create(width=width, height=height))
        .add(source_group)
        .compile(budget=budget)
    )
    script = source.document.dumps()
    style = Style(name="KaraComposite", outline=0, shadow=0, align=7)
    scene = Scene(
        Document.create(width=width, height=height, styles=(style,)),
        owner=f"composite:{group.id}",
    )
    origins = tuple(item.origin for item in source.objects if item.origin is not None)
    sources = tuple(dict.fromkeys(ref for origin in origins for ref in origin.sources))
    track_ids = tuple(
        dict.fromkeys(track for origin in origins for track in origin.track_ids)
    )
    origin = group.origin or (
        EventOrigin(sources, "offscreen group", track_ids) if sources else None
    )
    boundaries = {
        _centiseconds(group.time_origin + value)
        for clip in group.animations
        for value in (clip.start, clip.end, *(clip.start + t for t in clip.breakpoints))
    }
    boundaries.update(
        _centiseconds(value / 1000)
        for event in source.document.lines
        for value in (event.start_time, event.end_time)
    )
    points = sorted(
        {
            start,
            end,
            *(value for value in boundaries if start < value < end),
            *(_centiseconds(start / 100 + i / budget.fps) for i in range(1, frames)),
        }
    )
    if len(points) - 1 > settings.max_frames:
        raise ValueError(
            f"{group.id}: raster frame budget exceeded after boundary splitting"
        )
    previous: RasterFrame | None = None
    pending: tuple[Line, ...] = ()
    events = 0
    characters = 0
    for left, right in zip(points, points[1:], strict=False):
        # libass samples integer milliseconds; choose the interval midpoint.
        time_ms = (left + right) * 5
        opacity = group.at(time_ms / 1000).opacity
        if blur_radius:
            original = rasterize(script, time_ms, resolution, budget=raster_budget)
            left_offset, top_offset, blurred = blur_frame(
                original, blur_radius, budget=raster_budget
            )
            canvas = RasterCanvas(width, height, budget=raster_budget)
            canvas.over_frame(blurred, left_offset, top_offset)
            frame = canvas.finish(opacity=opacity)
        else:
            frame = rasterize(
                script, time_ms, resolution, opacity=opacity, budget=raster_budget
            )
        frame = quantize_frame(frame, settings.max_channel_error)
        if frame == previous:
            for event in pending:
                event.end_time = right * 10
            continue
        previous = frame
        pending = encode_frame(
            frame,
            DisplayWindow(left * 10, right * 10),
            style=style.name,
            resolution=resolution,
            budget=raster_budget,
        )
        if len(pending) > budget.max_active:
            raise ValueError(f"{group.id}: composite peak active budget exceeded")
        for event in pending:
            events += 1
            characters += len(event.text)
            if events > budget.max_events or characters > settings.max_output_chars:
                raise ValueError(f"{group.id}: composite output budget exceeded")
            event.layer = group.layer
            scene.add(NativeEvent(f"{group.id}/pixel:{events}", event, origin))
    # Include style/provenance/UTF-8 overhead in the final shared output budget.
    scene.compile(budget=budget)
    return RasterizedGroup(
        scene, len(points) - 1, source.event_count, settings.max_channel_error
    )
