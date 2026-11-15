"""Internal source-target preparation and mask compilation for author effects."""

from dataclasses import replace

from . import _metrics
from ._track_types import TrackPlan
from .animation import plan_pulses
from .appearance import (
    resolve_paints,
)
from .ass_output import OutputCapabilityError, TextLayer, quantize
from .characters import layout_characters
from .masks import PaintedMask, compose_masks, track_spans
from .sources import EventOrigin
from .targets import PreparedLyrics, layout_targets
from .timeline import (
    DisplayWindow,
    ProgressCurve,
    Region,
    tracks_from_layout,
)


def _blur_padding(radius: float) -> int:
    # Native ASS clamps blur to 100; use its quantized finite kernel, including
    # downsample alignment, rather than a user-supplied spatial compensation.
    return _metrics.blur_padding(min(radius, 100))


def _margin(paint):
    glow = paint.glow
    return max(paint.border, glow.border + _blur_padding(glow.blur) if glow else 0)


def _prepare_targets(
    target,
    context,
    *,
    paints,
    spans=(),
    sweep,
    tracks=None,
    track_styles=(),
    ruby,
    ruby_paints=(),
    pulses=(),
    overflow="truncate",
    origin_effect,
) -> PreparedLyrics:
    layout = context.layout
    characters = layout_characters(layout, style=context.style)
    appearances = resolve_paints(characters, default=paints, spans=spans)
    if tracks is None:
        tracks = tuple(
            replace(
                t,
                passes=tuple(replace(p, curve=sweep.progress_curve) for p in t.passes),
            )
            for t in tracks_from_layout(layout)
        )
    else:
        if sweep.progress_curve != ProgressCurve():
            raise ValueError(
                "explicit tracks own their curves; do not also set Sweep.progress_curve"
            )
        tracks = tuple(tracks)
    styles = {s.track_id: s for s in track_styles}
    if len(styles) != len(track_styles) or set(styles) - {t.id for t in tracks}:
        raise ValueError("duplicate or unknown track appearance id")
    animation = plan_pulses(
        pulses,
        layout=layout,
        characters=tuple(c.target for c in characters),
        tracks=tracks,
        window=target.window,
        overflow=overflow,
    )
    return layout_targets(
        target,
        context,
        characters=characters,
        appearances=appearances,
        tracks=tracks,
        animation=animation,
        ruby=ruby,
        ruby_paints=ruby_paints,
        pulses=pulses,
        effect_name=origin_effect,
    )


def _compile_targets(
    target_id: str,
    context,
    prepared: PreparedLyrics,
    *,
    sweep,
    fade,
    track_styles=(),
    overlap="union",
    max_glow_blur=None,
    max_border=None,
    max_glow_width=None,
    component="both",
    order_offset=0,
    origin_effect,
    fade_window=None,
) -> TrackPlan:
    styles = {s.track_id: s for s in track_styles}
    window = prepared.window
    layers = []
    diagnostics = list(prepared.diagnostics)

    def emit(
        source_id,
        text,
        box,
        body,
        before_after,
        selected_tracks,
        animations,
        style,
        sources,
        ink=None,
        target_fade=None,
    ):
        origin = EventOrigin(
            sources,
            origin_effect,
            tuple(t.id for t in selected_tracks),
        )
        selected_paints = [
            (
                styles[t.id].after
                if t.id in styles and styles[t.id].after is not None
                else before_after.after
            )
            for t in selected_tracks
        ]
        margin = max(
            (_margin(p) for p in (before_after.before, *selected_paints)), default=0
        )
        if max_border is not None:
            margin = max(margin, max_border)
        if max_glow_width is not None:
            margin = max(
                margin,
                max(
                    (
                        max_glow_width
                        + _blur_padding(
                            max_glow_blur if max_glow_blur is not None else p.glow.blur
                        )
                        for p in (before_after.before, *selected_paints)
                        if p.glow is not None
                    ),
                    default=0,
                ),
            )
        if max_glow_blur is not None:
            margin = max(
                margin,
                max(
                    (
                        p.glow.border + _blur_padding(max_glow_blur)
                        for p in (before_after.before, *selected_paints)
                        if p.glow is not None
                    ),
                    default=0,
                ),
            )
        ink_left, ink_right = (
            (ink.left, ink.right) if ink is not None else (box.left, box.right)
        )
        # Keep the entire sweep trajectory in every glyph's mask domain.
        # Cutting at glyph/blur bounds introduces different crossing times;
        # centisecond quantization then changes the shared body front.
        domain = Region(
            min(
                body.left,
                box.left,
                ink_left,
                *(p.region.left for t in selected_tracks for p in t.passes),
            )
            - margin
            - sweep.edges.padding_px,
            max(
                body.right,
                box.right,
                ink_right,
                *(p.region.right for t in selected_tracks for p in t.passes),
            )
            + margin
            + sweep.edges.padding_px,
        )
        paint_region = Region(
            min(body.left, box.left, ink_left) - margin,
            max(body.right, box.right, ink_right) + margin,
        )
        # Arrange complete sweep phases before cropping their visibility.
        # Reparameterizing a front at display-window boundaries changes
        # ASS integer clip rounding and can shift the visible front.
        passes = tuple(p for t in selected_tracks for p in t.passes)
        release_at = max(
            (
                p.end_ms + (sweep.edges.tail_ms if p.region.right >= body.right else 0)
                for p in passes
            ),
            default=window.end_ms,
        )
        mask_window = DisplayWindow(
            min(
                window.start_ms,
                max(
                    0,
                    min(
                        (p.start_ms - sweep.edges.lead_ms for p in passes),
                        default=window.start_ms,
                    ),
                ),
            ),
            max(
                window.end_ms,
                max(
                    (p.end_ms + sweep.edges.tail_ms for p in passes),
                    default=window.end_ms,
                ),
            ),
        )
        masks = tuple(
            PaintedMask(
                t.id,
                paint,
                styles[t.id].priority if t.id in styles else 0,
                track_spans(
                    t,
                    body=body,
                    paint=paint_region,
                    window=mask_window,
                    edges=sweep.edges,
                ),
            )
            for t, paint in zip(selected_tracks, selected_paints, strict=True)
        )
        try:
            regions = compose_masks(
                masks,
                domain=domain,
                window=mask_window,
                before=before_after.before,
                overlap=overlap,
                max_regions=context.max_regions,
            )
        except OutputCapabilityError as error:
            raise OutputCapabilityError(
                f"{target_id}/{source_id}: {error}",
                origin=origin,
            ) from error
        warned_decoration_boundary = False
        warned_local_clock = False
        for index, region in enumerate(regions):
            if (
                region.span.end_ms <= window.start_ms
                or region.span.start_ms >= window.end_ms
            ):
                continue
            if region.shared_local_clock and not warned_local_clock:
                diagnostics.append(
                    f"{target_id}/{source_id}: incompatible clip-edge clocks use a shared "
                    "local interpolation interval to keep adjacent boundaries identical; "
                    "integer endpoints and centisecond times approximate the original fronts"
                )
                warned_local_clock = True
            if region.hard_decoration_boundary and not warned_decoration_boundary:
                diagnostics.append(
                    f"{target_id}/{source_id}: ASS hard-clips differing outline/glow stacks "
                    f"at a spatial boundary during "
                    f"{max(window.start_ms, region.span.start_ms):g}.."
                    f"{min(window.end_ms, region.span.end_ms):g} ms; "
                    f"tracks={','.join(t.id for t in selected_tracks)}; "
                    "smooth recoloring or blurring the combined regions is not supported "
                    "by this output path; temporal sampling cannot remove this spatial boundary"
                )
                warned_decoration_boundary = True
            exposure = None
            if region.interpolation_span is not None:
                start = quantize(max(window.start_ms, region.span.start_ms))
                end = quantize(min(window.end_ms, region.span.end_ms))
                if end <= start:
                    diagnostics.append(
                        f"{target_id}/{source_id}: mask exposure vanished during centisecond quantization"
                    )
                    continue
                exposure = DisplayWindow(start, end)
            for order, paint in enumerate(region.paints):
                layer = TextLayer(
                    f"{target_id}/{source_id}/region:{index}/stack:{order}",
                    text,
                    style,
                    box,
                    window,
                    paint,
                    target_fade or fade,
                    (region.interpolation_span or region.span,),
                    animations,
                    order + order_offset,
                    animation_id=f"{target_id}/{source_id}",
                    origin=origin,
                    active_window=exposure,
                    component=component,
                    fade_window=fade_window,
                )
                if (
                    sweep.completion == "release"
                    and region.span.start == region.span.end == domain
                    and region.span.end_ms > release_at
                ):
                    start = max(window.start_ms, region.span.start_ms)
                    stop = min(window.end_ms, region.span.end_ms)
                    boundary = max(start, release_at)
                    # Keep global fade/pulse clocks; expose only this phase.
                    if quantize(start) < quantize(min(boundary, stop)):
                        layers.append(
                            replace(
                                layer,
                                active_window=DisplayWindow(
                                    quantize(start),
                                    quantize(min(boundary, stop)),
                                ),
                            )
                        )
                    if quantize(boundary) < quantize(stop):
                        layers.append(
                            replace(
                                layer,
                                source_id=layer.source_id + "/released",
                                clips=None,
                                active_window=DisplayWindow(
                                    quantize(boundary), quantize(stop)
                                ),
                            )
                        )
                else:
                    layers.append(layer)
                if len(layers) > context.max_regions:
                    raise OutputCapabilityError(
                        f"{target_id}: effect plan exceeds {context.max_regions} layers",
                        origin=origin,
                    )

    for visual in prepared.targets:
        emit(
            visual.id,
            visual.text,
            visual.box,
            visual.body,
            visual.paints,
            visual.tracks,
            visual.animations,
            visual.style,
            visual.sources,
            visual.ink,
            visual.fade,
        )
    return TrackPlan(tuple(layers), tuple(diagnostics))
