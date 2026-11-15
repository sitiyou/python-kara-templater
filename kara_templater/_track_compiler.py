"""Bind track declarations and lower them to shared visual targets and properties."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ._compiler import _compile_targets, _prepare_targets
from ._track_raster import TrackRasterPlan
from ._track_styles import base_paint, prepare_style, range_paints, sung_paint
from .appearance import ColorSpan, PaintPair, RubyPaint
from .ass import Style
from .ass_output import Fade, OutputCapabilityError
from .behaviors import BoundProperty, MotionRule, resolve_behaviors, sample_hierarchy
from .characters import TextRange, layout_characters, select_characters
from .components import Body, Lyrics, Ruby
from .lowering import lower_offsets, lower_opacity
from .material_animation import (
    BoundMaterial,
    MaterialRule,
    PaintBounds,
    bind_material,
    material_value,
    sample_materials,
)
from .model import LaidOutLine, LaidOutUnit, TextUnit
from .motion import AnimationContext
from .properties import PropertyTarget
from .recipe import EffectContext, EffectPlan, KaraokeItem, RubyPolicy, Sweep
from .sampling import DynamicEffect, DynamicProperties, SampleContext
from .targets import PreparedLyrics, VisualTarget
from .timeline import DisplayWindow, HighlightTrack, SingingPass

if TYPE_CHECKING:
    from .track import Track


def bind_track(track: Track, items: tuple[KaraokeItem, ...]) -> dict[str, BoundTrack]:
    bound: dict[str, BoundTrack] = {}
    for item in items:
        config = deepcopy(track)
        root = Lyrics(config.body, *((config.ruby,) if config.ruby is not None else ()))
        for node in root.walk():
            node.attributes["style"] = item.style
        context = AnimationContext(item)
        rules: list[MotionRule] = []
        materials: list[MaterialRule] = []
        start, end = item.window.start_ms, item.window.end_ms
        for animation in config.animations:
            motions = animation.bind(context)
            if any(motion.mode == "ruby" for motion in motions) and (
                config.ruby is None or not config.ruby.policy.enabled
            ):
                raise ValueError(
                    f"{item.id}: animation targets Ruby but this Track has no visible Ruby"
                )
            for motion in motions:
                if isinstance(motion, MaterialRule):
                    materials.append(motion)
                else:
                    rules.append(motion)
            if animation.extend_display:
                for motion in motions:
                    left, right = motion.during
                    assert isinstance(left, int) and isinstance(right, int)
                    start, end = min(start, left), max(end, right)
        window = DisplayWindow(max(0, start), end)
        bound[item.id] = BoundTrack(
            config, tuple(rules), window, materials=tuple(materials)
        )
    if track.layout is not None:
        rows = deepcopy(track.layout).allocate(
            tuple(replace(item, window=bound[item.id].window) for item in items)
        )
        bound = {key: replace(value, row=rows[key]) for key, value in bound.items()}
    return bound


@dataclass(frozen=True)
class PreparedTrack:
    """Bound geometry and animation, before backend-specific ASS expansion.

    Property keys are local visual IDs; material keys include the item ID.
    Preparing without native lowering retains all geometry animation in the
    property bindings, so another backend need not reverse-engineer ASS tags.
    """

    lyrics: PreparedLyrics
    properties: dict[str, tuple[BoundProperty, ...]]
    materials: dict[str, tuple[BoundMaterial, ...]]
    bounds: PaintBounds
    context: EffectContext
    sweep: Sweep


@dataclass(frozen=True)
class BoundTrack:
    config: Track
    rules: tuple[MotionRule, ...]
    window: DisplayWindow
    row: int = 0
    materials: tuple[MaterialRule, ...] = ()

    def prepare_styles(self, style: Style, ruby_style: Style) -> tuple[Style, Style]:
        style = prepare_style(self.config.body, style, self.config.styles)
        ruby = self.config.ruby
        if ruby is not None:
            ruby_style = prepare_style(ruby, ruby_style, self.config.styles)
        return style, ruby_style

    def _ruby_ranges(
        self,
        visual: VisualTarget,
        item: KaraokeItem,
        context: EffectContext,
    ) -> tuple[VisualTarget, ...]:
        ruby, overlay = self.config.ruby, self.config.overlay
        if ruby is None or visual.kind != "ruby":
            return (visual,)
        source = visual.sources[0]
        spans = tuple(
            span
            for span in ruby.spans
            if (span.unit_index, span.segment_index)
            == (source.unit_index, source.segment_index)
        )
        length = len(visual.text)
        split = any(span.start != 0 or span.end not in (None, length) for span in spans)
        parts: list[tuple[VisualTarget, int, int]] = []
        if split:
            layout = LaidOutLine(
                visual.box,
                (
                    LaidOutUnit(
                        TextUnit(visual.text, visual.singing),
                        visual.box,
                        (),
                    ),
                ),
            )
            characters = layout_characters(layout, style=context.ruby_style)
            for span in spans:
                select_characters(
                    characters,
                    TextRange(0, span.start, length if span.end is None else span.end),
                )
            parts.extend(
                (
                    replace(
                        visual,
                        id=f"{visual.id}/text:{char.source.start}:{char.source.end}",
                        text=char.text,
                        box=char.box,
                        ink=char.ink_bounds,
                        transform_box=visual.box,
                    ),
                    char.source.start,
                    char.source.end,
                )
                for char in characters
                if char.target.drawable
            )
        else:
            parts.append((visual, 0, length))
        result: list[VisualTarget] = []
        for part, start, end in parts:
            active = tuple(
                span
                for span in spans
                if span.start <= start
                and end <= (length if span.end is None else span.end)
            )
            base, local = range_paints(
                ruby,
                context.ruby_style,
                self.config.styles,
                visual.paints.before,
                active,
                {
                    "style": item.style,
                    "unit": source.unit_index or 0,
                    "segment": source.segment_index or 0,
                    "start": start,
                    "end": end,
                    "text": part.text,
                },
            )
            pair = PaintPair(base, base)
            if overlay is not None and overlay.enabled(Ruby):
                pair = sung_paint(
                    ruby,
                    local,
                    context.ruby_style,
                    self.config.styles,
                    base,
                    overlay.resolve(Ruby, base),
                    active,
                )
            result.append(replace(part, paints=pair))
        return tuple(result)

    def _bind_materials(
        self,
        targets: tuple[VisualTarget, ...],
        item: KaraokeItem,
    ) -> tuple[dict[str, tuple[BoundMaterial, ...]], PaintBounds]:
        result: dict[str, tuple[BoundMaterial, ...]] = {}
        limits: dict[str, float] = {}
        for visual in targets:
            ui = visual.sources[0].unit_index
            assert ui is not None
            selected = [
                rule
                for rule in self.materials
                if ui in rule.units
                and (rule.mode != "ruby" or visual.kind == "ruby")
                and (
                    rule.segments is None
                    or visual.kind != "ruby"
                    or any(
                        (source.unit_index, source.segment_index) in rule.segments
                        for source in visual.sources
                    )
                )
            ]
            selected.sort(
                key=lambda rule: (
                    0 if rule.mode == "group" else 2 if rule.mode == "ruby" else 1
                )
            )
            motions: list[BoundMaterial] = []
            for rule in selected:
                segments = tuple(
                    segment
                    for si, segment in enumerate(item.source.units[ui].segments)
                    if rule.segments is None or (ui, si) in rule.segments
                )
                motion = bind_material(
                    rule,
                    visual.paints.before,
                    segments,
                    target=PropertyTarget(
                        f"{item.id}/{visual.id}",
                        visual.text,
                        visual.kind,
                        visual.sources,
                    ),
                )
                before = material_value(visual.paints.before, rule.property)
                after = material_value(visual.paints.after, rule.property)
                start, end = motion.interval
                stop = self.window.end_ms if rule.keep else end
                first_sweep = min(
                    (p.start_ms for t in visual.tracks for p in t.passes),
                    default=self.window.end_ms,
                )
                if (
                    before != after
                    and rule.compose != "override"
                    and max(start, first_sweep, self.window.start_ms)
                    < min(stop, self.window.end_ms)
                ):
                    raise OutputCapabilityError(
                        f"{item.id}/{visual.id}: {rule.property} animation conflicts with Sweep; "
                        "use compose='override' to explicitly replace both materials"
                    )
                for previous in motions:
                    if previous.rule.property != rule.property:
                        continue
                    previous_end = (
                        self.window.end_ms
                        if previous.rule.keep
                        else previous.interval[1]
                    )
                    if (
                        max(start, previous.interval[0], self.window.start_ms)
                        < min(stop, previous_end, self.window.end_ms)
                        and rule.compose != "override"
                    ):
                        raise OutputCapabilityError(
                            f"{item.id}/{visual.id}: {rule.property} material animation conflict"
                        )
                motions.append(motion)
                if motion.upper is not None:
                    limits[rule.property] = max(
                        limits.get(rule.property, 0), motion.upper
                    )
            if motions:
                result[f"{item.id}/{visual.id}"] = tuple(motions)
        return result, PaintBounds(
            stroke_width=limits.get("stroke_width"),
            blur_radius=limits.get("blur_radius"),
            blur_width=limits.get("blur_width"),
        )

    def prepare(
        self,
        item: KaraokeItem,
        context: EffectContext,
        *,
        lower_native: bool = False,
    ) -> PreparedTrack:
        """Resolve layout/styles once, leaving sampled callbacks unevaluated."""
        config = self.config
        if config.layout is not None:
            context = replace(
                context, layout=config.layout.place(context.layout, self.row)
            )
        body, ruby, overlay = config.body, config.ruby, config.overlay
        before = base_paint(body, context.style, config.styles)
        after = before if overlay is None else overlay.resolve(Body, before)
        chars = layout_characters(context.layout, style=context.style)
        offsets: list[int] = []
        length = 0
        for unit in item.source.units:
            offsets.append(length)
            length += len(unit.text)
        for span in body.spans:
            if span.end > length:
                raise ValueError(f"{item.id}: text span exceeds body length {length}")
            for ui, unit in enumerate(item.source.units):
                left, right = (
                    max(span.start, offsets[ui]),
                    min(span.end, offsets[ui] + len(unit.text)),
                )
                if left < right:
                    select_characters(
                        chars, TextRange(ui, left - offsets[ui], right - offsets[ui])
                    )
        spans: list[ColorSpan] = []
        for char in chars:
            start = offsets[char.source.unit_index] + char.source.start
            end = offsets[char.source.unit_index] + char.source.end
            active = tuple(
                span for span in body.spans if span.start <= start and end <= span.end
            )
            base, local = range_paints(
                body,
                context.style,
                config.styles,
                before,
                active,
                {
                    "style": item.style,
                    "unit": char.source.unit_index,
                    "start": start,
                    "end": end,
                    "text": char.text,
                },
            )
            pair = PaintPair(base, base)
            if overlay is not None and overlay.enabled(Body):
                pair = sung_paint(
                    body,
                    local,
                    context.style,
                    config.styles,
                    base,
                    overlay.resolve(Body, base),
                    active,
                )
            spans.append(ColorSpan(char.source, pair.before, pair.after))
        ruby_paints: list[RubyPaint] = []
        if ruby is not None:
            for span in ruby.spans:
                if span.unit_index >= len(item.source.units):
                    raise ValueError(
                        f"{item.id}: ruby span references a missing syllable"
                    )
                segments = item.source.units[span.unit_index].segments
                if (
                    span.segment_index >= len(segments)
                    or not segments[span.segment_index].ruby
                ):
                    raise ValueError(
                        f"{item.id}: ruby span references a missing reading"
                    )
                length = len(segments[span.segment_index].ruby)
                end = length if span.end is None else span.end
                if not span.start < end <= length:
                    raise ValueError(
                        f"{item.id}: ruby span exceeds reading length {length}"
                    )
            for ui, unit in enumerate(context.layout.units):
                for si, segment in enumerate(unit.segments):
                    if segment.ruby is not None:
                        base = base_paint(ruby, context.ruby_style, config.styles)
                        sung = base if overlay is None else overlay.resolve(Ruby, base)
                        ruby_paints.append(RubyPaint(ui, si, PaintPair(base, sung)))
        sweep = Sweep() if overlay is None else overlay.reveal
        prepared = _prepare_targets(
            replace(item, window=self.window),
            context,
            paints=PaintPair(before, after),
            spans=tuple(spans),
            ruby_paints=tuple(ruby_paints),
            sweep=sweep,
            tracks=() if overlay is None else None,
            ruby=RubyPolicy(enabled=False) if ruby is None else ruby.policy,
            origin_effect=type(config).__name__,
        )
        # Each reading owns its segment clock; following never copies body time.
        targets = []
        visuals = tuple(
            part
            for visual in prepared.targets
            for part in self._ruby_ranges(visual, item, context)
        )
        for visual in visuals:
            role = Body if visual.kind == "body" else Ruby
            tracks = visual.tracks
            if overlay is None or not overlay.enabled(role):
                tracks = ()
            elif role is Ruby:
                tracks = tuple(
                    HighlightTrack(
                        f"{visual.id}:sweep",
                        visual.sources[0].unit_index or 0,
                        (
                            SingingPass(
                                segment.start_ms,
                                segment.end_ms,
                                visual.body,
                                sweep.progress_curve,
                            ),
                        ),
                    )
                    for segment in visual.singing
                )
            targets.append(replace(visual, tracks=tracks))
        prepared = replace(prepared, targets=tuple(targets))
        materials, bounds = self._bind_materials(prepared.targets, item)
        prepared, properties = resolve_behaviors(
            prepared,
            context,
            self.rules,
            ruby_follow="none" if ruby is None else ruby.following,
            item_id=item.id,
            hierarchical=True,
            lower_native=lower_native,
        )
        return PreparedTrack(prepared, properties, materials, bounds, context, sweep)

    def build(self, item: KaraokeItem, context: EffectContext) -> EffectPlan:
        binding = self.prepare(item, context, lower_native=context.raster is None)
        return self.lower(item, binding)

    def lower(self, item: KaraokeItem, binding: PreparedTrack) -> EffectPlan:
        """Compile an existing preparation without rerunning layout or binding."""
        prepared, properties = binding.lyrics, binding.properties
        materials, bounds = binding.materials, binding.bounds
        context, sweep = binding.context, binding.sweep
        config = self.config
        if context.raster is not None:
            return EffectPlan(
                diagnostics=prepared.diagnostics,
                raster=TrackRasterPlan(
                    prepared,
                    properties,
                    materials,
                    item_id=item.id,
                    resolution=context.resolution,
                    sampling=config.sampling,
                    settings=context.raster,
                    effect_name=type(config).__name__,
                ),
            )
        plan = _compile_targets(
            item.id,
            context,
            prepared,
            sweep=sweep,
            fade=Fade(),
            origin_effect=type(config).__name__,
            max_glow_blur=bounds.blur_radius,
            max_border=bounds.stroke_width,
            max_glow_width=bounds.blur_width,
        )
        if any(
            motion.property == "opacity"
            for motions in properties.values()
            for motion in motions
        ) or any(
            paint.opacity < 1
            for target in prepared.targets
            for paint in (target.paints.before, target.paints.after)
        ):
            plan = replace(
                plan,
                diagnostics=(
                    *plan.diagnostics,
                    "native ASS opacity is applied per drawing layer; overlapping "
                    "parts do not receive post-composite group alpha; use RasterSettings "
                    "when that compositing order is required",
                ),
            )
        property_targets = {
            f"{item.id}/{key}": value for key, value in properties.items()
        }
        layers = lower_offsets(plan.layers, property_targets)
        layers = lower_opacity(layers, property_targets, {})

        def sample(at: SampleContext) -> DynamicProperties:
            return replace(
                DynamicProperties(
                    **sample_hierarchy(
                        property_targets.get(at.target_id, ()), at.time_ms
                    )
                ),
                **sample_materials(materials.get(at.target_id, ()), at.time_ms),
            )

        return replace(
            plan,
            layers=layers,
            dynamic=(
                DynamicEffect(
                    sample,
                    config.sampling,
                    max_glow_blur=bounds.blur_radius,
                    breakpoints=tuple(
                        sorted(
                            {
                                t
                                for motions in property_targets.values()
                                for motion in motions
                                for t in motion.breakpoints
                            }
                        )
                    ),
                )
                if any(property_targets.values()) or materials
                else None
            ),
        )
