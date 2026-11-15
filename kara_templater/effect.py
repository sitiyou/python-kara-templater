"""Effects and visual components, bound to source lyrics before text layout."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import replace
from typing import Literal, Self, TypeVar, overload

from ._compiler import _compile_targets, _prepare_targets
from .appearance import ColorSpan, PaintPair, RubyPaint
from .ass import Style
from .ass_output import Fade, OutputCapabilityError, TextLayer
from .behaviors import (
    MotionRule,
    TargetSelection,
    bind_property,
    check_motion_conflicts,
    resolve_behaviors,
    sample_properties,
)
from .characters import (
    TextRange,
    layout_characters,
    select_characters,
)
from .colors import WHITE
from .components import Body, Component, Halo, Lyrics, Ruby
from .composition import Color, Glow, Paint
from .import_ass import paint_pair_from_style
from .lowering import lower_offsets, lower_opacity
from .model import LaidOutLine
from .properties import (
    PropertyTarget,
    resolve_interval,
)
from .recipe import (
    EffectContext,
    EffectPlan,
    KaraokeItem,
    RubyPolicy,
    Sweep,
    TrackStyle,
)
from .sampling import DynamicEffect, DynamicProperties, SamplingSettings
from .sources import EventOrigin, SourceRef, _source_context
from .stylesheet import (
    UNSET,
    ColorStyle,
    Selector,
    StyleOverrides,
    StyleSheet,
)
from .timeline import DisplayWindow, EdgeSweep, HighlightTrack, ProgressCurve

_ComponentT = TypeVar("_ComponentT", bound="Component")


class _Text:
    def __init__(self, effect: Effect) -> None:
        self.sweep_settings: Sweep | None = None
        self.effect = effect
        self.fade_settings = Fade()
        self._has_fade = False
        self.tracks: (
            Iterable[HighlightTrack]
            | Callable[[LaidOutLine], Iterable[HighlightTrack]]
            | None
        ) = None
        self.track_styles: tuple[TrackStyle, ...] = ()
        self.overlap = "union"

    def sweep(
        self,
        *,
        fill: ColorStyle | None = None,
        stroke: ColorStyle | None = None,
        curve: ProgressCurve | Literal["linear"] | None = None,
        padding: float = 0,
        lead: int = 0,
        tail: int = 0,
        tracks: (
            Iterable[HighlightTrack]
            | Callable[[LaidOutLine], Iterable[HighlightTrack]]
            | None
        ) = None,
        track_styles: Iterable[TrackStyle] = (),
        overlap: Literal["union", "priority", "layer"] = "union",
    ) -> None:
        if self.sweep_settings is not None:
            raise ValueError("sweep already configured for text")
        if overlap not in {"union", "priority", "layer"}:
            raise ValueError("sweep overlap must be union, priority or layer")
        self.tracks = tracks
        self.track_styles = tuple(track_styles)
        self.overlap = overlap
        # Use exactly the same validation/cascade path as explicit sung styles.
        values = StyleOverrides()
        if fill is not None:
            values.fill = fill
        if stroke is not None:
            values.stroke = stroke
        self.sweep_settings = Sweep(
            progress_curve=ProgressCurve() if curve in (None, "linear") else curve,
            edges=EdgeSweep(padding_px=padding, lead_ms=lead, tail_ms=tail),
        )
        # self.text is a shorthand for both text components. Write the same
        # declarations as .style.sung, including UNSET removal and INHERIT.
        for node in (*self.effect.query("body"), *self.effect.query("ruby")):
            if fill is not None:
                node.style.sung.fill = fill
            if stroke is not None:
                node.style.sung.stroke = stroke

    def fade(self, *, in_ms: int = 0, out_ms: int = 0) -> None:
        if self._has_fade:
            raise ValueError("fade already configured for text")
        self.fade_settings = Fade(in_ms, out_ms)
        self._has_fade = True


def _properties(paint):
    return {
        "fill": paint.fill,
        "stroke": paint.outline,
        "stroke_width": paint.border,
        "opacity": paint.opacity,
    }


def _paint(values):
    return Paint(
        values["fill"], values["stroke"], values["stroke_width"], values["opacity"]
    )


class Effect:
    """Declare components in compose(), then configure a fresh instance per line."""

    # Bound on a fresh instance by _prepare(), before compose/configure run.
    source: KaraokeItem
    text: _Text
    syllables: TargetSelection
    characters: TargetSelection
    segments: TargetSelection
    rubies: TargetSelection
    _nodes: tuple[Component, ...]
    _motion_rules: list[MotionRule]
    _ruby_targets: dict[tuple[int, int], Component]
    _source_paints: PaintPair

    styles = StyleSheet()
    sampling = SamplingSettings()

    def compose(self) -> Iterable[Lyrics]:
        yield Lyrics(Body(), Ruby())

    def configure(self) -> None:
        pass

    @overload
    def query(self, selector: type[_ComponentT]) -> tuple[_ComponentT, ...]: ...

    @overload
    def query(self, selector: str) -> tuple[Component, ...]: ...

    def query(
        self, selector: str | type[_ComponentT]
    ) -> tuple[Component, ...] | tuple[_ComponentT, ...]:
        """Find components by selector or class, preserving class query types."""
        if isinstance(selector, type):
            return tuple(node for node in self._nodes if isinstance(node, selector))
        parsed = Selector.parse(selector)
        return tuple(node for node in self._nodes if parsed.matches(node))

    @overload
    def query_one(self, selector: type[_ComponentT]) -> _ComponentT: ...

    @overload
    def query_one(
        self, selector: str, expect_type: type[_ComponentT]
    ) -> _ComponentT: ...

    @overload
    def query_one(self, selector: str) -> Component: ...

    def query_one(
        self,
        selector: str | type[_ComponentT],
        expect_type: type[_ComponentT] | None = None,
    ) -> Component | _ComponentT:
        """Require exactly one match, then validate its expected class if supplied."""
        found = self.query(selector)
        if len(found) != 1:
            raise ValueError(
                f"selector {selector!r} expected one component, found {len(found)}"
            )
        node = found[0]
        if expect_type is not None:
            if not isinstance(node, expect_type):
                raise TypeError(
                    f"selector {selector!r} expected {expect_type.__name__}, "
                    f"found {type(node).__name__}"
                )
            return node
        return node

    @property
    def body(self) -> Body:
        return self.query_one(Body)

    @property
    def ruby(self) -> Ruby:
        return self.query_one(Ruby)

    def _selection_query_node(self, selection):
        # Read-only adapters: querying a candidate must not create style ranges
        # that force otherwise unnecessary shaping-boundary validation.
        mode, member = selection.mode, selection._members[0]
        ui = (
            member[0]
            if mode in {"segment", "ruby"}
            else (member.unit_index if mode == "character" else member)
        )
        unit = self.source.source.units[ui]
        offset = sum(len(u.text) for u in self.source.source.units[:ui])

        def node(kind, identity, attrs, parent, classes=()):
            result = Component(id=identity, classes=classes)
            result.kind, result.parent = kind, parent
            result.attributes = {"style": self.source.style, "unit": ui, **attrs}
            return result

        def classes_for(start, end):
            if start == end:
                return set()
            return set().union(
                *(
                    n.classes
                    for (a, b), n in self.body._ranges.items()
                    if a <= start and end <= b
                )
            )

        whole = node(
            "syllable",
            f"unit-{ui}",
            {"text": unit.text},
            self.body,
            classes_for(offset, offset + len(unit.text)),
        )
        if mode == "syllable":
            return whole
        if mode == "character":
            return node(
                "character",
                f"char-{ui}-{member.start}-{member.end}",
                {
                    "text": unit.text[member.start : member.end],
                    "start": member.start,
                    "end": member.end,
                },
                whole,
                classes_for(offset + member.start, offset + member.end),
            )
        si = member[1]
        segment = unit.segments[si]
        timed = node(
            "segment",
            f"segment-{ui}-{si}",
            {
                "segment": si,
                "text": unit.text,
                "reading": segment.ruby,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
            },
            whole,
        )
        if mode == "segment":
            return timed
        styled = self._ruby_targets.get((ui, si))
        return node(
            "ruby",
            f"ruby-{ui}-{si}",
            {
                "segment": si,
                "text": segment.ruby,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
            },
            timed,
            styled.classes if styled is not None else (),
        )

    def _selection_style_nodes(self, selection):
        if selection.mode == "segment":
            raise ValueError(
                "segments are timing targets; style syllables, characters or rubies"
            )
        if selection.mode == "ruby":
            parent = self.ruby
            nodes = []
            for ui, si in selection._members:
                key = (ui, si)
                if key not in self._ruby_targets:
                    node = Component()
                    node.kind, node.parent = "ruby", parent
                    node.attributes = {
                        "unit": ui,
                        "segment": si,
                        "style": self.source.style,
                        "text": self.source.source.units[ui].segments[si].ruby,
                    }
                    self._ruby_targets[key] = node
                nodes.append(self._ruby_targets[key])
            return tuple(nodes)
        offsets, offset = [], 0
        for unit in self.source.source.units:
            offsets.append(offset)
            offset += len(unit.text)
        ranges = (
            selection._members
            if selection.mode == "character"
            else tuple(
                TextRange(ui, 0, len(self.source.source.units[ui].text))
                for ui in selection.units
                if self.source.source.units[ui].text
            )
        )
        return tuple(
            self.body.text_range(
                offsets[r.unit_index] + r.start, offsets[r.unit_index] + r.end
            )
            for r in ranges
        )

    def _prepare(
        self, item: KaraokeItem, style: Style, ruby_style: Style
    ) -> tuple[Self, Style, Style]:
        bound = deepcopy(self)
        bound.source = item
        bound.text = _Text(bound)
        bound._motion_rules = []
        bound._ruby_targets = {}
        bound.syllables = TargetSelection(
            item.source,
            bound._motion_rules,
            item_id=item.id,
            style_targets=bound._selection_style_nodes,
            query_target=bound._selection_query_node,
        )
        bound.characters = TargetSelection(
            item.source,
            bound._motion_rules,
            item_id=item.id,
            style_targets=bound._selection_style_nodes,
            query_target=bound._selection_query_node,
            mode="character",
        )
        bound.segments = bound.syllables.segments
        bound.rubies = bound.segments.rubies
        roots = deepcopy(tuple(bound.compose()))
        if len(roots) != 1 or not isinstance(roots[0], Lyrics):
            raise ValueError("compose() must yield one Lyrics component")
        bound._nodes = tuple(roots[0].walk())
        ids = [node.id for node in bound._nodes if node.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate component id in lyric")
        if len(bound.query("body")) != 1 or len(bound.query("ruby")) > 1:
            raise ValueError("Lyrics requires one Body and at most one Ruby")
        for node in bound._nodes:
            if isinstance(node, (Body, Ruby)):
                if node.spans:
                    raise ValueError(
                        "TextSpan/RubySpan require tracks=; legacy Effect does not bind range declarations"
                    )
                if (
                    node.text_style.blur is not UNSET
                    or node.text_style.font_name is not None
                    or node.text_style.spacing is not None
                ):
                    raise ValueError(
                        "TextStyle blur/font_name/spacing require tracks=; legacy Effect does not bind these fields"
                    )
            if node.kind not in {"lyrics", "body", "ruby", "halo"}:
                raise ValueError(f"unsupported component {node.kind!r}")
            node.attributes["style"] = item.style
        bound.body._length = sum(len(unit.text) for unit in item.source.units)
        bound.configure()
        bound._source_paints = paint_pair_from_style(style)
        # Font sizes are measured only after author configuration. A range font
        # size needs mixed-style shaping support; fail explicitly for now.
        for node, original in (
            (bound.body, style),
            *((r, ruby_style) for r in bound.query("ruby")),
        ):
            assert node.parent is not None
            inherited = bound.styles.resolve(
                node.parent, {"font_size": original.fontsize}
            )
            inherited_sung = bound.styles.resolve(
                node.parent, {"font_size": original.fontsize}, sung=True
            )
            values = bound.styles.resolve(node, inherited)
            sung = bound.styles.resolve(node, inherited_sung, sung=True)
            if values.get("font_size") != sung.get("font_size"):
                raise ValueError(
                    "font_size cannot change in :sung; use scale animation"
                )
            changed = replace(original, fontsize=values["font_size"])
            if node.kind == "body":
                style = changed
            else:
                ruby_style = changed
        return bound, style, ruby_style

    def build(self, item: KaraokeItem, context: EffectContext) -> EffectPlan:
        if not hasattr(self, "_nodes"):
            raise ValueError("Effect must be bound before layout by render_karaoke")
        body = self.body
        assert body.parent is not None
        defaults = []
        for sung, paint in (
            (False, self._source_paints.before),
            (True, self._source_paints.after),
        ):
            inherited = self.styles.resolve(body.parent, _properties(paint), sung=sung)
            values = self.styles.resolve(body, inherited, sung=sung)
            defaults.append(values)
        chars = layout_characters(context.layout, style=context.style)
        offsets, offset = [], 0
        for unit in item.source.units:
            offsets.append(offset)
            offset += len(unit.text)
        # Validate every requested boundary, even if its declarations are empty.
        for start, end in body._ranges:
            for ui, unit in enumerate(item.source.units):
                left, right = (
                    max(start, offsets[ui]),
                    min(end, offsets[ui] + len(unit.text)),
                )
                if left < right:
                    select_characters(
                        chars, TextRange(ui, left - offsets[ui], right - offsets[ui])
                    )
        spans = []
        for char in chars:
            start = offsets[char.source.unit_index] + char.source.start
            end = offsets[char.source.unit_index] + char.source.end
            ranges = [
                node for (a, b), node in body._ranges.items() if a <= start and end <= b
            ]
            paints = []
            for sung, base in enumerate(defaults):
                values = base
                if ranges:
                    node = Component()
                    node.kind, node.parent = "body", body
                    node.attributes = {"start": start, "end": end, "style": item.style}
                    node.classes = body.classes | set.union(
                        *(r.classes for r in ranges)
                    )
                    # Direct writes use declaration order for overlapping ranges.
                    for selected in ranges:
                        node.style._values.update(selected.style._values)
                        node.style.sung._values.update(selected.style.sung._values)
                    values = self.styles.resolve(
                        node,
                        base,
                        sung=bool(sung),
                        inherited=base,
                        resolved_parent=body,
                    )
                if (
                    values.get("font_size", context.style.fontsize)
                    != context.style.fontsize
                ):
                    raise ValueError(
                        "range font_size requires mixed-style layout support"
                    )
                paints.append(_paint(values))
            spans.append(ColorSpan(char.source, *paints))
        ruby_paints = []
        if self.query("ruby") and self.ruby.policy.enabled:
            ruby_base = paint_pair_from_style(context.ruby_style)
            for ui, unit in enumerate(context.layout.units):
                for si, segment in enumerate(unit.segments):
                    if segment.ruby is None:
                        continue
                    if segment.right <= segment.left:
                        raise OutputCapabilityError(
                            f"{item.id}/ruby:{ui}:{si}: zero-width body mapping requires explicit timing",
                            origin=EventOrigin(
                                (SourceRef(item.id, ui, si),), type(self).__name__
                            ),
                        )
                    associated = [
                        span
                        for char, span in zip(chars, spans, strict=True)
                        if char.source.unit_index == ui
                        and char.timing_region.left < segment.right
                        and char.timing_region.right > segment.left
                    ]
                    with _source_context(
                        EventOrigin((SourceRef(item.id, ui, si),), type(self).__name__)
                    ):
                        pair = []
                        for sung, state in ((False, "before"), (True, "after")):
                            inherited = _properties(getattr(ruby_base, state))
                            # Inherit colors only, keeping ruby's own geometry.
                            for prop in ("fill", "stroke"):
                                choices = {
                                    _properties(getattr(span, state))[prop]
                                    for span in associated
                                }
                                if len(choices) == 1:
                                    inherited[prop] = choices.pop()
                                else:
                                    inherited.pop(prop)
                            values = self.styles.resolve(
                                self.ruby, inherited, sung=sung
                            )
                            node = self._ruby_targets.get((ui, si))
                            if node is not None:
                                values = self.styles.resolve(
                                    node,
                                    values,
                                    sung=sung,
                                    inherited=values,
                                    resolved_parent=self.ruby,
                                )
                                if (
                                    values.get("font_size", context.ruby_style.fontsize)
                                    != context.ruby_style.fontsize
                                ):
                                    raise ValueError(
                                        "target ruby font_size requires mixed-style layout support"
                                    )
                            if any(prop not in values for prop in ("fill", "stroke")):
                                raise ValueError(
                                    f"unit {ui}/segment {si}: ruby needs explicit appearance for ambiguous body colors"
                                )
                            pair.append(_paint(values))
                        ruby_paints.append(RubyPaint(ui, si, PaintPair(*pair)))
        tracks = (
            self.text.tracks(context.layout)
            if callable(self.text.tracks)
            else self.text.tracks
        )
        sweep = self.text.sweep_settings or Sweep()
        prepared = _prepare_targets(
            item,
            context,
            paints=PaintPair(*(_paint(v) for v in defaults)),
            spans=tuple(spans),
            ruby_paints=tuple(ruby_paints),
            tracks=tracks if self.text.sweep_settings is not None else (),
            track_styles=self.text.track_styles,
            sweep=sweep,
            ruby=self.ruby.policy if self.query("ruby") else RubyPolicy(enabled=False),
            origin_effect=type(self).__name__,
        )
        prepared, sampled_behaviors = resolve_behaviors(
            prepared,
            context,
            self._motion_rules,
            ruby_follow=self.ruby.following if self.query("ruby") else "none",
            item_id=item.id,
        )
        if self.query("ruby") and not self.ruby.following.fade:
            prepared = replace(
                prepared,
                targets=tuple(
                    replace(v, fade=Fade()) if v.kind == "ruby" else v
                    for v in prepared.targets
                ),
            )
        property_targets = {
            f"{item.id}/{key}": value for key, value in sampled_behaviors.items()
        }
        plan = _compile_targets(
            item.id,
            context,
            prepared,
            sweep=sweep,
            fade=self.text.fade_settings,
            track_styles=self.text.track_styles,
            overlap=self.text.overlap,
            origin_effect=type(self).__name__,
        )
        halos, motions, blur_limits = [], {}, {}
        diagnostics = list(plan.diagnostics)
        decorations = self.query(Halo)
        for index, halo in enumerate(decorations):
            if (
                any(r.property == "glow_blur" for r in halo._property_rules)
                and halo.max_blur is None
            ):
                raise ValueError("animated Halo blur requires max_blur")
            if halo.max_blur is not None:
                Glow(blur=halo.max_blur)
                if halo.blur > halo.max_blur:
                    raise ValueError("Halo max_blur must cover its base blur")
            for visual in prepared.targets:
                with _source_context(EventOrigin(visual.sources, type(self).__name__)):
                    if not halo._selects(visual, item.id):
                        continue
                # A decoration stays independently white unless the winning
                # declaration explicitly inherits its attachment's state color.
                values = self.styles.resolve(
                    halo,
                    {"fill": WHITE, "opacity": 1},
                    inherited={"fill": visual.paints.before.fill, "opacity": 1},
                )
                sung_values = self.styles.resolve(
                    halo,
                    {"fill": WHITE, "opacity": 1},
                    sung=True,
                    inherited={"fill": visual.paints.after.fill, "opacity": 1},
                )
                identity = f"{item.id}/{visual.id}/halo:{index}"
                fill, opacity = values["fill"], values["opacity"]
                sung_fill, sung_opacity = sung_values["fill"], sung_values["opacity"]
                assert isinstance(fill, Color) and isinstance(sung_fill, Color)
                assert isinstance(opacity, (int, float))
                assert isinstance(sung_opacity, (int, float))
                glow = Glow(
                    fill,
                    blur=halo.blur,
                    border=halo.ruby_width if visual.kind == "ruby" else halo.width,
                    opacity=opacity,
                )
                sung_glow = replace(
                    glow,
                    color=sung_fill,
                    opacity=sung_opacity,
                )
                origin = EventOrigin(
                    visual.sources,
                    type(self).__name__,
                    tuple(t.id for t in visual.tracks),
                )
                window = prepared.window
                if halo.window is not None:
                    interval = resolve_interval(
                        halo.window, visual.singing, prepared.window
                    )
                    if interval is None:
                        raise ValueError(
                            f"{identity}: Halo window needs a timed target"
                        )
                    window = DisplayWindow(*interval)
                fade = (
                    (visual.fade or self.text.fade_settings)
                    if halo.following.fade
                    else Fade()
                )
                animations = visual.animations if halo.following.scale else ()
                followers = tuple(
                    m
                    for m in sampled_behaviors.get(visual.id, ())
                    if halo.following.allows(m.property)
                )
                check_motion_conflicts(followers, window, origin, identity)
                # A longer decoration window can expose native overlaps that
                # were outside the body's output window. Validate them here.
                for left_index, left in enumerate(animations):
                    for right in animations[left_index + 1 :]:
                        start = max(left.start_ms, right.start_ms, window.start_ms)
                        end = min(
                            window.end_ms,
                            window.end_ms if left.keep else left.end_ms,
                            window.end_ms if right.keep else right.end_ms,
                        )
                        if start < end:
                            raise OutputCapabilityError(
                                f"{identity}: followed scale conflict at {start}..{end} ms",
                                origin=origin,
                            )
                if halo.clip == "none" and glow == sung_glow:
                    halos.append(
                        TextLayer(
                            identity,
                            visual.text,
                            visual.style,
                            visual.box,
                            window,
                            Paint(glow=glow),
                            fade,
                            animations=animations,
                            order=index - len(decorations),
                            animation_id=identity,
                            origin=origin,
                            component="glow",
                            fade_window=(
                                prepared.window if halo.following.fade else None
                            ),
                        )
                    )
                else:
                    decorated = replace(
                        visual,
                        id=f"{visual.id}/halo:{index}",
                        paints=PaintPair(
                            Paint(opacity=0 if halo.clip == "sung" else 1, glow=glow),
                            Paint(glow=sung_glow),
                        ),
                        animations=animations,
                        fade=fade,
                    )
                    # Use the shared mask compiler on unsplit source targets.
                    # Union coverage avoids doubling a halo where tracks overlap.
                    halo_context = replace(
                        context,
                        max_regions=max(
                            1, context.max_regions - len(halos) - len(plan.layers)
                        ),
                    )
                    clipped = _compile_targets(
                        item.id,
                        halo_context,
                        replace(
                            prepared,
                            targets=(decorated,),
                            window=window,
                            diagnostics=(),
                        ),
                        component="glow",
                        sweep=sweep,
                        fade=fade,
                        max_glow_blur=halo.max_blur,
                        order_offset=index - len(decorations),
                        origin_effect=type(self).__name__,
                        fade_window=prepared.window if halo.following.fade else None,
                    )
                    halos.extend(clipped.layers)
                    diagnostics.extend(clipped.diagnostics)
                if followers:
                    property_targets[identity] = followers
                if len(halos) + len(plan.layers) > context.max_regions:
                    raise OutputCapabilityError(
                        f"{item.id}: decorated effect exceeds {context.max_regions} layers",
                        origin=origin,
                    )
                if halo._property_rules:
                    bound = []
                    with _source_context(origin):
                        for rule in halo._property_rules:
                            motion = bind_property(
                                rule,
                                visual.singing,
                                window,
                                (visual.box.center, visual.box.middle),
                                target=PropertyTarget(
                                    identity,
                                    visual.text,
                                    "halo",
                                    visual.sources,
                                    f"{item.id}/{visual.id}",
                                ),
                            )
                            if motion is not None:
                                bound.append(motion)
                        check_motion_conflicts(bound, window, origin, identity)
                    motions[identity] = (
                        tuple(bound),
                        glow.opacity if glow.opacity == sung_glow.opacity else None,
                    )
                    if any(m.property == "glow_blur" for m in bound):
                        blur_limits[identity] = halo.max_blur
        if len(halos) + len(plan.layers) > context.max_regions:
            raise OutputCapabilityError(
                f"{item.id}: decorated effect exceeds {context.max_regions} layers"
            )

        layers = lower_offsets((*halos, *plan.layers), property_targets)
        layers = lower_opacity(layers, property_targets, motions)

        def properties(sample):
            values = sample_properties(
                property_targets.get(sample.target_id, ()), sample.time_ms
            )
            opacity = None
            blur = None
            if sample.target_id in motions:
                bound, base = motions[sample.target_id]
                glow_values = sample_properties(bound, sample.time_ms)
                opacity = glow_values.get("opacity", base)
                blur = glow_values.get("glow_blur")
                if blur is not None and blur > blur_limits[sample.target_id]:
                    raise ValueError("Halo blur exceeds its declared max_blur")
            values["glow_blur"] = blur
            return DynamicProperties(glow_opacity=opacity, **values)

        return replace(
            plan,
            layers=layers,
            diagnostics=tuple(diagnostics),
            dynamic=(
                DynamicEffect(
                    properties,
                    self.sampling,
                    max_glow_blur=max(blur_limits.values()) if blur_limits else None,
                )
                if motions or property_targets
                else None
            ),
        )
