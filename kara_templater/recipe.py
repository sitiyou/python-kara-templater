"""Public karaoke recipes and explicit, reusable execution contexts."""

from dataclasses import dataclass, field, replace

from .animation import Pulse, plan_pulses
from .appearance import (
    ColorSpan,
    PaintPair,
    RubyPaint,
    resolve_paints,
    resolve_ruby_paints,
)
from .ass import Line, Style
from .ass_output import Fade, OutputCapabilityError, TextLayer, quantize
from .characters import layout_characters
from .composition import Paint
from .masks import PaintedMask, compose_masks, track_spans
from .model import KaraokeLine, LaidOutLine
from .sampling import DynamicEffect
from .sources import EventOrigin, SourceRef, _source_context
from .timeline import (
    DisplayWindow,
    EdgeSweep,
    HighlightTrack,
    ProgressCurve,
    Region,
    tracks_from_layout,
)


@dataclass(frozen=True)
class KaraokeItem:
    id: str
    source: KaraokeLine
    style: str
    window: DisplayWindow
    ruby_style: str | None = None
    margins: tuple[int, int, int] | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("karaoke item needs a stable id")
        if self.margins is not None and (
            len(self.margins) != 3 or any(type(v) is not int for v in self.margins)
        ):
            raise ValueError("item margins must be three integers")


@dataclass(frozen=True)
class EffectContext:
    layout: LaidOutLine
    style: Style
    ruby_style: Style
    resolution: tuple[int, int]
    max_regions: int = 10000


@dataclass(frozen=True)
class EffectPlan:
    layers: tuple[TextLayer, ...] = ()
    diagnostics: tuple[str, ...] = ()
    raw_lines: tuple[Line, ...] = ()
    dynamic: DynamicEffect | None = None


@dataclass(frozen=True)
class Sweep:
    progress_curve: ProgressCurve = field(default_factory=ProgressCurve)
    edges: EdgeSweep = field(default_factory=EdgeSweep)
    completion: str = "release"

    def __post_init__(self):
        if self.completion not in {"release", "clip"}:
            raise ValueError("sweep completion must be release or clip")


@dataclass(frozen=True)
class TrackStyle:
    track_id: str
    after: Paint | None = None
    priority: int = 0

    def __post_init__(self):
        if not self.track_id or type(self.priority) is not int:
            raise ValueError("track appearance needs an id and integer priority")


@dataclass(frozen=True)
class RubyPolicy:
    enabled: bool = True
    offset_y: float = 0
    follow: str = "none"

    def __post_init__(self):
        from .timeline import _finite

        _finite(self.offset_y, "ruby offset")
        if self.follow not in {"none", "syllable"}:
            raise ValueError("ruby follow must be none or syllable")


def _margin(paint):
    # Conservative working estimate; callers can add explicit edge padding.
    glow = paint.glow
    return max(paint.border, glow.border + 4 * glow.blur if glow else 0)


@dataclass(frozen=True)
class KaraokeEffect:
    paints: PaintPair = field(default_factory=PaintPair)
    spans: tuple[ColorSpan, ...] = ()
    sweep: Sweep = Sweep()
    pulses: tuple[Pulse, ...] = ()
    fade: Fade = field(default_factory=Fade)
    tracks: tuple[HighlightTrack, ...] | None = None
    track_styles: tuple[TrackStyle, ...] = ()
    overlap: str = "union"
    ruby: RubyPolicy = RubyPolicy()
    ruby_paints: tuple[RubyPaint, ...] = ()
    overflow: str = "truncate"
    dynamic: DynamicEffect | None = None

    @classmethod
    def guide(cls, *, paints: PaintPair, fade: Fade | None = None):
        return cls(paints=paints, fade=fade or Fade(), ruby=RubyPolicy(enabled=False))

    def build(self, target: KaraokeItem, context: EffectContext) -> EffectPlan:
        with _source_context(EventOrigin((SourceRef(target.id),), type(self).__name__)):
            return self._build(target, context)

    def _build(self, target: KaraokeItem, context: EffectContext) -> EffectPlan:
        layout = context.layout
        characters = layout_characters(layout, style=context.style)
        appearances = resolve_paints(characters, default=self.paints, spans=self.spans)
        if self.tracks is None:
            tracks = tuple(
                replace(
                    t,
                    passes=tuple(
                        replace(p, curve=self.sweep.progress_curve) for p in t.passes
                    ),
                )
                for t in tracks_from_layout(layout)
            )
        else:
            if self.sweep.progress_curve != ProgressCurve():
                raise ValueError(
                    "explicit tracks own their curves; do not also set Sweep.progress_curve"
                )
            tracks = tuple(self.tracks)
        styles = {s.track_id: s for s in self.track_styles}
        if len(styles) != len(self.track_styles) or set(styles) - {
            t.id for t in tracks
        }:
            raise ValueError("duplicate or unknown track appearance id")
        animation = plan_pulses(
            self.pulses,
            layout=layout,
            characters=tuple(c.target for c in characters),
            tracks=tracks,
            window=target.window,
            overflow=self.overflow,
        )
        window = animation.window
        layers = []
        diagnostics = list(animation.diagnostics)

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
        ):
            origin = EventOrigin(
                sources, type(self).__name__, tuple(t.id for t in selected_tracks)
            )
            selected_paints = [
                styles[t.id].after
                if t.id in styles and styles[t.id].after is not None
                else before_after.after
                for t in selected_tracks
            ]
            margin = max(
                (_margin(p) for p in (before_after.before, *selected_paints)), default=0
            )
            if self.dynamic is not None and self.dynamic.max_glow_blur is not None:
                margin = max(
                    margin,
                    max(
                        (
                            p.glow.border + 4 * self.dynamic.max_glow_blur
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
                - self.sweep.edges.padding_px,
                max(
                    body.right,
                    box.right,
                    ink_right,
                    *(p.region.right for t in selected_tracks for p in t.passes),
                )
                + margin
                + self.sweep.edges.padding_px,
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
                    p.end_ms
                    + (self.sweep.edges.tail_ms if p.region.right >= body.right else 0)
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
                            (p.start_ms - self.sweep.edges.lead_ms for p in passes),
                            default=window.start_ms,
                        ),
                    ),
                ),
                max(
                    window.end_ms,
                    max(
                        (p.end_ms + self.sweep.edges.tail_ms for p in passes),
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
                        edges=self.sweep.edges,
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
                    overlap=self.overlap,
                    max_regions=context.max_regions,
                )
            except OutputCapabilityError as error:
                raise OutputCapabilityError(
                    f"{target.id}/{source_id}: {error}",
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
                        f"{target.id}/{source_id}: incompatible clip-edge clocks use a shared "
                        "local interpolation interval to keep adjacent boundaries identical; "
                        "integer endpoints and centisecond times approximate the original fronts"
                    )
                    warned_local_clock = True
                if region.hard_decoration_boundary and not warned_decoration_boundary:
                    diagnostics.append(
                        f"{target.id}/{source_id}: ASS hard-clips differing outline/glow stacks "
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
                            f"{target.id}/{source_id}: mask exposure vanished during centisecond quantization"
                        )
                        continue
                    exposure = DisplayWindow(start, end)
                for order, paint in enumerate(region.paints):
                    layer = TextLayer(
                        f"{target.id}/{source_id}/region:{index}/stack:{order}",
                        text,
                        style,
                        box,
                        window,
                        paint,
                        self.fade,
                        (region.interpolation_span or region.span,),
                        animations,
                        order,
                        animation_id=f"{target.id}/{source_id}",
                        origin=origin,
                        active_window=exposure,
                    )
                    if (
                        self.sweep.completion == "release"
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
                            f"{target.id}: effect plan exceeds {context.max_regions} layers",
                            origin=origin,
                        )
            if any(p.glow is not None for p in (before_after.before, *selected_paints)):
                diagnostics.append(
                    f"{target.id}/{source_id}: glow bounds estimated as border + 4*blur; increase EdgeSweep.padding_px if needed"
                )

        for appearance in appearances:
            char = appearance.character
            if not char.target.drawable:
                continue
            box = layout.units[char.source.unit_index].box
            emit(
                char.id,
                char.text,
                char.box,
                Region(box.left, box.right),
                appearance.paints,
                tuple(t for t in tracks if t.unit_index == char.source.unit_index),
                tuple(a for a in animation.animations if a.target_id == char.id),
                context.style,
                tuple(
                    SourceRef(target.id, char.source.unit_index, si)
                    for si in range(len(layout.units[char.source.unit_index].segments))
                )
                or (SourceRef(target.id, char.source.unit_index),),
                char.ink_bounds,
            )

        if self.ruby.enabled:
            ruby_paints = resolve_ruby_paints(
                layout, appearances, overrides=self.ruby_paints
            )
            if self.ruby.follow == "syllable" and any(
                p.target != "syllable" for p in self.pulses
            ):
                raise OutputCapabilityError(
                    f"{target.id}: ruby syllable following requires syllable-target pulses",
                    origin=EventOrigin((SourceRef(target.id),), type(self).__name__),
                )
            for appearance in ruby_paints:
                ui, si = appearance.unit_index, appearance.segment_index
                segment = layout.units[ui].segments[si]
                box = replace(segment.ruby, top=segment.ruby.top + self.ruby.offset_y)
                if segment.right <= segment.left:
                    raise OutputCapabilityError(
                        f"{target.id}/ruby:{ui}:{si}: zero-width body mapping requires explicit timing",
                        origin=EventOrigin(
                            (SourceRef(target.id, ui, si),), type(self).__name__
                        ),
                    )
                ratio = box.width / (segment.right - segment.left)
                mapped = []
                for track in tracks:
                    if track.unit_index != ui:
                        continue
                    passes = tuple(
                        replace(
                            p,
                            region=Region(
                                box.left + (p.region.left - segment.left) * ratio,
                                box.left + (p.region.right - segment.left) * ratio,
                            ),
                        )
                        for p in track.passes
                    )
                    if passes:
                        mapped.append(replace(track, passes=passes))
                followers = ()
                if self.ruby.follow == "syllable":
                    first = next(
                        (
                            c
                            for c in characters
                            if c.source.unit_index == ui and c.target.drawable
                        ),
                        None,
                    )
                    if first:
                        followers = tuple(
                            a for a in animation.animations if a.target_id == first.id
                        )
                emit(
                    f"ruby:{ui}:{si}",
                    segment.source.ruby,
                    box,
                    Region(box.left, box.right),
                    appearance.paints,
                    tuple(mapped),
                    followers,
                    context.ruby_style,
                    (SourceRef(target.id, ui, si),),
                )
        return EffectPlan(tuple(layers), tuple(diagnostics), dynamic=self.dynamic)
