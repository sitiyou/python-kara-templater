"""Sample prepared Track targets into bounded pre-blur material frames."""

from collections import OrderedDict
from dataclasses import dataclass, replace
from itertools import pairwise
from math import ceil
from typing import Literal

from . import _metrics
from ._coverage_stack import CoverageStack, compose_stacks
from ._material_composition import MaterialLayer, compose_material_layers
from ._material_raster import CoverageMask, MaterialBand
from ._raster import (
    PositionedFrame,
    RasterBudget,
    RasterCanvas,
    compose_frames,
    crop_frame,
    encode_frame,
    quantize_frame,
)
from ._raster_opacity import apply_opacity, opacity_curve
from .ass import EVENT_FORMAT, STYLE_FORMAT, Line, Style
from .ass_output import OutputCapabilityError, escape_text, number, quantize
from .behaviors import BoundProperty, sample_hierarchy, sample_properties
from .composition import Color, Paint
from .material_animation import BoundMaterial, MaterialSamples, sample_materials
from .raster_settings import RasterEstimate, RasterSettings
from .sampling import SamplingSettings
from .sources import EventOrigin, SourceRef, _source_context
from .targets import PreparedLyrics, VisualTarget
from .timeline import DisplayWindow, Region, union_regions


def _patch(paint: Paint, values: MaterialSamples) -> Paint:
    glow = paint.glow
    if glow is not None:
        glow = replace(
            glow,
            color=values.get("glow_color", glow.color),
            blur=values.get("glow_blur", glow.blur),
            border=values.get("glow_width", glow.border),
            opacity=values.get("glow_opacity", glow.opacity),
        )
    return replace(
        paint,
        fill=values.get("fill", paint.fill),
        outline=values.get("stroke", paint.outline),
        border=values.get("stroke_width", paint.border),
        glow=glow,
    )


@dataclass(frozen=True)
class _State:
    scale: float
    x: float
    y: float
    translation_x: float
    before: Paint
    after: Paint
    regions: tuple[Region, ...]
    group_opacity: float
    unit_opacity: float
    local_opacity: float


class TrackRasterPlan:
    def __init__(
        self,
        prepared: PreparedLyrics,
        properties: dict[str, tuple[BoundProperty, ...]],
        materials: dict[str, tuple[BoundMaterial, ...]],
        *,
        item_id: str,
        resolution: tuple[int, int],
        sampling: SamplingSettings,
        settings: RasterSettings,
        effect_name: str,
    ) -> None:
        self.targets = prepared.targets
        self.window = prepared.window
        self.properties, self.materials = properties, materials
        self.item_id, self.resolution, self.settings = item_id, resolution, settings
        self.budget = RasterBudget(
            max_pixels=settings.max_pixels,
            max_images=settings.max_images,
            max_events=settings.max_frame_events,
            max_rectangles=settings.max_rectangles,
            max_path_chars=settings.max_frame_chars,
        )
        self.budget.check_pixels(*resolution)
        self.origin = EventOrigin(
            tuple(
                dict.fromkeys(ref for target in self.targets for ref in target.sources)
            )
            or (SourceRef(item_id),),
            effect_name,
        )
        self.layer_count = len(self.targets)
        self.opacity_curve = opacity_curve(
            tuple(
                tuple(
                    m
                    for m in properties.get(target.id, ())
                    if m.property == "opacity" and m.scope == "group"
                )
                for target in self.targets
            ),
            self.window,
        )
        for target in self.targets:
            if (
                float(target.style.fields.get("Angle", "0")) != 0
                or target.style.fields.get("BorderStyle", "1") != "1"
            ):
                raise OutputCapabilityError(
                    "raster text requires zero style Angle and BorderStyle 1",
                    origin=replace(self.origin, sources=target.sources),
                )
        start, end = quantize(self.window.start_ms), quantize(self.window.end_ms)
        knots = {
            start,
            end,
            *range(
                (start // sampling.step_ms + 1) * sampling.step_ms,
                end,
                sampling.step_ms,
            ),
        }
        for target in self.targets:
            for track in target.tracks:
                for part in track.passes:
                    knots.update(
                        quantize(
                            part.start_ms + fraction * (part.end_ms - part.start_ms)
                        )
                        for fraction, _ in part.curve.knots
                    )
            for motion in properties.get(target.id, ()):
                knots.update(
                    quantize(t) for t in (*motion.interval, *motion.breakpoints)
                )
            for material in materials.get(f"{item_id}/{target.id}", ()):
                knots.update(quantize(t) for t in material.interval)
        times = sorted(t for t in knots if start <= t <= end)
        self.intervals = tuple(pairwise(times))
        frames = len(self.intervals)
        samples = frames * len(self.targets)
        if frames > settings.max_frames or samples > sampling.max_samples:
            raise OutputCapabilityError(
                f"raster preflight exceeds frame/sample budget ({frames} frames, {samples} targets)",
                origin=self.origin,
            )
        self.estimate = RasterEstimate(
            frames,
            samples,
            resolution[0] * resolution[1],
            settings.max_frame_events,
            settings.max_channel_error,
        )
        self._masks: OrderedDict[
            tuple[str, float, float, float, float, str, int], CoverageMask | None
        ] = OrderedDict()
        self._cached_pixels = 0

    def _states(self, time: int) -> tuple[_State, ...]:
        result = []
        for target in self.targets:
            origin = replace(self.origin, sources=target.sources)
            try:
                motions = self.properties.get(target.id, ())
                geometry = sample_hierarchy(
                    tuple(m for m in motions if m.property != "opacity"), time
                )
                scale = geometry.get("scale", 1.0)
                px, py = geometry.get("pivot", (target.box.center, target.box.middle))
                dx, dy = geometry.get("offset_x", 0.0), geometry.get("offset_y", 0.0)
                alphas = tuple(
                    sample_properties(
                        tuple(
                            m
                            for m in motions
                            if m.property == "opacity" and m.scope == scope
                        ),
                        time,
                    ).get("opacity", 1.0)
                    for scope in ("group", "unit", "local")
                )
                values = sample_materials(
                    self.materials.get(f"{self.item_id}/{target.id}", ()), time
                )
                before, after = (
                    _patch(target.paints.before, values),
                    _patch(target.paints.after, values),
                )
                regions = []
                for track in target.tracks:
                    for region in track.regions_at(time):
                        # Release the whole outer ink at completed endpoints;
                        # before the first nonzero region the material stays base.
                        left = -1e12 if region.left <= target.body.left else region.left
                        right = (
                            1e12 if region.right >= target.body.right else region.right
                        )
                        regions.append(
                            Region(
                                left * scale + (1 - scale) * px + dx,
                                right * scale + (1 - scale) * px + dx,
                            )
                        )
                result.append(
                    _State(
                        scale,
                        px + (target.box.center - px) * scale + dx,
                        py + (target.box.middle - py) * scale + dy,
                        (1 - scale) * px + dx,
                        before,
                        after,
                        union_regions(regions),
                        1.0 if self.opacity_curve is not None else alphas[0],
                        alphas[1],
                        alphas[2],
                    )
                )
            except Exception as error:
                raise OutputCapabilityError(
                    f"{target.id}: raster animation failed: {error}",
                    origin=origin,
                    time_ms=time,
                ) from error
        return tuple(result)

    def _mask(
        self,
        target: VisualTarget,
        state: _State,
        border: float,
        kind: Literal["fill", "stroke", "glow"],
        padding: int,
    ) -> CoverageMask | None:
        key = (target.id, state.x, state.y, state.scale, border, kind, padding)
        if key in self._masks:
            self._masks.move_to_end(key)
            return self._masks[key]
        ink = target.ink or target.box
        self.budget.check_pixels(
            max(1, ceil(ink.width * state.scale + 2 * border + 32)),
            max(1, ceil(ink.height * state.scale + 2 * border + 32)),
        )
        width, height = (
            self.resolution[0] + 2 * padding,
            self.resolution[1] + 2 * padding,
        )
        self.budget.check_pixels(width, height)
        fields = dict(
            zip(
                STYLE_FORMAT.split(", "),
                Style().serialize().removeprefix("Style: ").split(","),
                strict=True,
            )
        )
        fields.update(
            {
                name: target.style.fields.get(name, "0")
                for name in ("Underline", "StrikeOut")
            }
        )
        style = replace(
            target.style,
            name="Mask",
            outline=0,
            shadow=0,
            fields=fields,
        )
        fill = "000000" if kind == "stroke" else "FFFFFF"
        text = (
            rf"{{\an5\q2\pos({number(state.x + padding)},{number(state.y + padding)})"
            + rf"\fs{number(style.fontsize)}\fscx{number(style.scale_x * state.scale)}\fscy{number(style.scale_y * state.scale)}"
            + rf"\bord{number(border)}\blur0\shad0\1c&H{fill}&\3c&HFFFFFF&\alpha&H00&}}"
            + escape_text(target.text)
        )
        line = Line(text=text, style="Mask", start_time=0, end_time=1000)
        script = (
            f"[Script Info]\nPlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\n"
            "[V4+ Styles]\nFormat: "
            + STYLE_FORMAT
            + "\n"
            + style.serialize()
            + "\n[Events]\nFormat: "
            + EVENT_FORMAT
            + "\n"
            + line.serialize()
        )
        images = _metrics.rasterize(
            script, 0, width, height, self.budget.max_pixels, self.budget.max_images
        )
        selected = [
            image
            for image in images
            if kind == "glow" or image[4] == (1 if kind == "stroke" else 0)
        ]
        mask = None
        if selected:
            left, top = min(i[0] for i in selected), min(i[1] for i in selected)
            right, bottom = (
                max(i[0] + i[2] for i in selected),
                max(i[1] + i[3] for i in selected),
            )
            canvas = RasterCanvas(right - left, bottom - top, budget=self.budget)
            for x, y, w, h, image_kind, _, data in selected:
                canvas.over((x - left, y - top, w, h, image_kind, 0xFFFFFF00, data))
            mask = CoverageMask(
                left - padding,
                top - padding,
                right - left,
                bottom - top,
                canvas.finish().rgba[3::4],
            )
            self._cached_pixels += mask.width * mask.height
        self._masks[key] = mask
        while (
            len(self._masks) > self.settings.max_cached_masks
            or self._cached_pixels > self.settings.max_pixels
        ):
            _, old = self._masks.popitem(last=False)
            if old is not None:
                self._cached_pixels -= old.width * old.height
        return mask

    def _piece(
        self,
        mask: CoverageMask,
        state: _State,
        *,
        after: bool,
        color: Color,
        opacity: float,
        weights: tuple[float, ...],
        blur_radius: float = 0,
    ) -> MaterialLayer:
        left, right = mask.left, mask.left + mask.width
        cuts = sorted(
            {
                left,
                right,
                *(
                    max(left, min(right, x))
                    for r in state.regions
                    for x in (r.left, r.right)
                ),
            }
        )
        bands = tuple(
            MaterialBand(
                Region(a, b),
                color,
                opacity
                if any(r.left <= (a + b) / 2 < r.right for r in state.regions) == after
                else 0,
            )
            for a, b in pairwise(cuts)
        )
        return MaterialLayer(mask, bands, weights, blur_radius)

    def _component(
        self,
        members: tuple[tuple[VisualTarget, _State], ...],
        padding: int,
        *,
        weighted: bool = False,
    ) -> CoverageStack:
        def piece(
            mask: CoverageMask,
            state: _State,
            paint: Paint,
            *,
            after: bool,
            color: Color,
            opacity: float,
            blur_radius: float = 0,
        ) -> MaterialLayer:
            local = paint.opacity * state.local_opacity
            unit = local * state.unit_opacity
            weights = (1, local, unit, unit * state.group_opacity) if weighted else (1,)
            return self._piece(
                mask,
                state,
                after=after,
                color=color,
                opacity=opacity,
                weights=weights,
                blur_radius=blur_radius,
            )

        strokes: list[MaterialLayer] = []
        fills: list[MaterialLayer] = []
        glows: list[MaterialLayer] = []
        for target, state in members:
            for is_after, paint in ((False, state.before), (True, state.after)):
                fill = self._mask(target, state, 0, "fill", padding)
                if fill is not None:
                    fills.append(
                        piece(
                            fill,
                            state,
                            paint,
                            after=is_after,
                            color=paint.fill,
                            opacity=1,
                        )
                    )
                if paint.border:
                    stroke = self._mask(
                        target, state, paint.border * state.scale, "stroke", padding
                    )
                    if stroke is not None:
                        strokes.append(
                            piece(
                                stroke,
                                state,
                                paint,
                                after=is_after,
                                color=paint.outline,
                                opacity=1,
                            )
                        )
                if paint.glow is not None:
                    radius = paint.glow.blur * state.scale
                    glow = self._mask(
                        target, state, paint.glow.border * state.scale, "glow", padding
                    )
                    if glow is not None:
                        glows.append(
                            piece(
                                glow,
                                state,
                                paint,
                                after=is_after,
                                color=paint.glow.color,
                                opacity=paint.glow.opacity,
                                blur_radius=radius,
                            )
                        )
        combined = compose_material_layers(
            fills=tuple(fills),
            strokes=tuple(strokes),
            glows=tuple(glows),
            budget=self.budget,
        )
        if weighted:
            # Component ownership ends here; its weighted coverage now occludes
            # siblings. Remaining planes carry unit and root opacity weights.
            return combined[1:]
        if not combined:
            return ()
        opacity = members[0][1].before.opacity * members[0][1].local_opacity
        result = compose_frames(combined, opacity=opacity, budget=self.budget)
        return () if result is None else (result,)

    def _frame(self, states: tuple[_State, ...]) -> PositionedFrame | None:
        radius = max(
            (
                paint.glow.blur * state.scale
                for state in states
                for paint in (state.before, state.after)
                if paint.glow is not None
            ),
            default=0,
        )
        if radius > 100:
            raise OutputCapabilityError(
                "scaled raster blur exceeds 100 ASS pixels", origin=self.origin
            )
        # Query the quantized native kernel, including downsample alignment.
        # This is spatial overscan; it never changes the sweep clock.
        padding = _metrics.blur_padding(radius)
        components: dict[
            tuple[int, str, int | None], list[tuple[VisualTarget, _State]]
        ] = {}
        for target, state in zip(self.targets, states, strict=True):
            unit = target.sources[0].unit_index
            assert unit is not None
            reading = target.sources[0].segment_index if target.kind == "ruby" else None
            components.setdefault((unit, target.kind, reading), []).append(
                (target, state)
            )
        # Use the single-plane fast path only when opacity can be factored out
        # at each actual source scope. Numeric equality never defines grouping.
        unit_opacities: dict[int, set[float]] = {}
        for (unit, _, _), members in components.items():
            unit_opacities.setdefault(unit, set()).update(
                state.unit_opacity for _, state in members
            )
        weighted = (
            len({state.group_opacity for state in states}) > 1
            or any(len(values) > 1 for values in unit_opacities.values())
            or any(
                len(
                    {
                        paint.opacity * state.local_opacity
                        for _, state in members
                        for paint in (state.before, state.after)
                    }
                )
                > 1
                for members in components.values()
            )
        )
        units: dict[int, list[CoverageStack]] = {}
        for (unit, _, _), members in components.items():
            stack = self._component(tuple(members), padding, weighted=weighted)
            if stack:
                units.setdefault(unit, []).append(stack)
        if weighted:
            groups = tuple(
                compose_stacks(tuple(parts), additive=False, budget=self.budget)[1:]
                for parts in units.values()
            )
            combined = compose_stacks(groups, additive=False, budget=self.budget)
            group = combined[-1] if combined else None
        else:
            frames = tuple(
                frame
                for unit, parts in units.items()
                if (
                    frame := compose_frames(
                        tuple(part[0] for part in parts),
                        opacity=next(iter(unit_opacities[unit])),
                        budget=self.budget,
                    )
                )
                is not None
            )
            group = compose_frames(
                frames,
                opacity=states[0].group_opacity if states else 1,
                budget=self.budget,
            )
        return None if group is None else crop_frame(group, self.resolution)

    def evaluate(
        self, *, style: str, layer: int, max_events: int, max_chars: int
    ) -> tuple[Line, ...]:
        result: list[Line] = []
        previous: tuple[_State, ...] | None = None
        cached: tuple[Line, ...] = ()
        active: dict[str, Line] = {}
        characters = 0
        for start, end in self.intervals:
            with _source_context(self.origin):
                states = self._states(start)
                if states != previous:
                    frame = self._frame(states)
                    cached = (
                        ()
                        if frame is None
                        else encode_frame(
                            quantize_frame(frame[2], self.settings.max_channel_error),
                            DisplayWindow(start, end),
                            style=style,
                            position=(frame[0], frame[1]),
                            resolution=self.resolution,
                            neutral_style=True,
                            budget=replace(
                                self.budget,
                                max_events=min(
                                    self.budget.max_events, max(1, max_events)
                                ),
                            ),
                        )
                    )
                    previous = states
                current: dict[str, Line] = {}
                frame_characters = 0
                for encoded in cached:
                    if (
                        encoded.text in active
                        and active[encoded.text].end_time == start
                    ):
                        event = active[encoded.text]
                        event.end_time = end
                    else:
                        if len(result) >= max_events:
                            raise OutputCapabilityError(
                                "raster animation exceeds output event budget",
                                origin=self.origin,
                                time_ms=start,
                            )
                        event = replace(
                            encoded,
                            start_time=start,
                            end_time=end,
                            layer=layer,
                            text=apply_opacity(encoded.text, start, self.opacity_curve)
                            if self.opacity_curve is not None
                            else encoded.text,
                        )
                        characters += len(event.text)
                        if characters > max_chars:
                            raise OutputCapabilityError(
                                "raster animation exceeds output character budget",
                                origin=self.origin,
                                time_ms=start,
                            )
                        result.append(event)
                    frame_characters += len(event.text)
                    if frame_characters > self.settings.max_frame_chars:
                        raise OutputCapabilityError(
                            "raster frame character budget exceeded after opacity lowering",
                            origin=self.origin,
                            time_ms=start,
                        )
                    current[encoded.text] = event
                active = current
        return tuple(result)
