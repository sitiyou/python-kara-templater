"""Convert prepared Track geometry to editable scene nodes before ASS lowering."""

from dataclasses import replace
from math import floor

from ._compiler import _compile_targets
from ._track_compiler import PreparedTrack
from ._track_raster import _patch
from .ass_output import Fade, OutputCapabilityError, TextLayer, quantize
from .behaviors import sample_hierarchy
from .geometry import Vec2
from .material_animation import sample_materials
from .scene import (
    Lifetime,
    ObjectGroup,
    RectangleClip,
    RectangleFunction,
    SceneObject,
    TextObject,
)
from .scene_animation import AnimationClip, Channel, StateFunction, VisualState
from .sources import EventOrigin
from .targets import VisualTarget


def track_objects(
    item_id: str, prepared: PreparedTrack, *, diagnostics: list[str] | None = None
) -> ObjectGroup:
    """Build editable text layers using the shared native sweep partitioner.

    This internal adapter uses per-layer native alpha, matching native Track
    output. It does not claim post-composite group alpha or raster materials.
    """
    if diagnostics is not None:
        diagnostics.extend(prepared.lyrics.diagnostics)
    window = prepared.lyrics.window
    lifetime = Lifetime(window.start_ms / 1000, window.end_ms / 1000)
    children: list[SceneObject] = []
    for target in prepared.lyrics.targets:
        origin = EventOrigin(
            target.sources, "Track", tuple(t.id for t in target.tracks)
        )
        _validate_target(target, origin)
        if not target.tracks or (
            target.paints.before == target.paints.after
            and not prepared.highlight_styles
            and prepared.overlap == "union"
        ):
            for glow in (True, False):
                if glow and target.paints.before.glow is None:
                    continue
                children.append(
                    _text_object(item_id, prepared, target, lifetime, origin, glow)
                )
            continue
        plan = _compile_targets(
            item_id,
            prepared.context,
            replace(prepared.lyrics, targets=(target,)),
            sweep=prepared.sweep,
            fade=Fade(),
            track_styles=prepared.highlight_styles,
            overlap=prepared.overlap,
            origin_effect="Track",
            max_glow_blur=prepared.bounds.blur_radius,
            max_border=prepared.bounds.stroke_width,
            max_glow_width=prepared.bounds.blur_width,
        )
        if diagnostics is not None:
            diagnostics.extend(plan.diagnostics)
        for index, layer in enumerate(plan.layers):
            painted = replace(target, paints=replace(target.paints, before=layer.paint))
            for glow in (True, False):
                if glow and layer.paint.glow is None:
                    continue
                node = _text_object(item_id, prepared, painted, lifetime, origin, glow)
                node = replace(
                    node,
                    id=f"{node.id}/region:{index}",
                    layer=2 * layer.order + (0 if glow else 1),
                )
                if layer.clips is None:
                    exposure = layer.active_window or layer.window
                    start, end = (
                        quantize(exposure.start_ms) / 1000,
                        quantize(exposure.end_ms) / 1000,
                    )
                    if end > start:
                        children.append(
                            ObjectGroup(
                                id=f"{node.id}/exposure",
                                lifetime=Lifetime(start, end),
                                children=(node,),
                            )
                        )
                else:
                    children.append(
                        replace(
                            node,
                            clip=_sweep_clip(
                                layer,
                                lifetime,
                                prepared.context.resolution[1],
                                native_clock=not any(
                                    m.property in ("scale", "offset_x", "offset_y")
                                    for m in prepared.properties.get(target.id, ())
                                ),
                            ),
                        )
                    )
    return ObjectGroup(id=item_id, lifetime=lifetime, children=tuple(children))


def _validate_target(target: VisualTarget, origin: EventOrigin) -> None:
    if target.animations or target.fade is not None:
        raise OutputCapabilityError(
            "editable Track needs preparation without native animation lowering",
            origin=origin,
        )
    if float(target.style.fields.get("BorderStyle", "1")) != 1:
        raise OutputCapabilityError(
            "editable Track text requires ordinary outline BorderStyle",
            origin=origin,
        )
    for key in ("Underline", "StrikeOut", "Angle"):
        if float(target.style.fields.get(key, "0")) != 0:
            raise OutputCapabilityError(
                f"editable Track text cannot represent style {key}", origin=origin
            )


def _text_object(
    item_id: str,
    prepared: PreparedTrack,
    target: VisualTarget,
    lifetime: Lifetime,
    origin: EventOrigin,
    glow: bool,
) -> TextObject:
    paint = target.paints.before
    style = target.style
    position = Vec2(target.box.center, target.box.middle)
    scale = Vec2(style.scale_x / 100, style.scale_y / 100)
    motions = prepared.properties.get(target.id, ())
    materials = prepared.materials.get(f"{item_id}/{target.id}", ())
    duration_ms = prepared.lyrics.window.end_ms - prepared.lyrics.window.start_ms

    def appearance(base: VisualState, progress: float) -> VisualState:
        time = prepared.lyrics.window.start_ms + progress * duration_ms
        values = sample_hierarchy(motions, time)
        colors = _patch(paint, sample_materials(materials, time))
        factor = values.get("scale", 1)
        pivot = Vec2(*values.get("pivot", (position.x, position.y)))
        offset = Vec2(values.get("offset_x", 0), values.get("offset_y", 0))
        # Base position/scale remain editable and are honored by delayed copies.
        point = pivot + (base.position - pivot) * factor + offset
        opacity = colors.opacity * values.get("opacity", 1)
        if glow:
            halo = colors.glow
            assert halo is not None
            return replace(
                base,
                position=point,
                scale=base.scale * factor,
                fill=halo.color,
                outline=halo.color,
                border=halo.border * factor,
                blur=(
                    halo.blur
                    if values.get("glow_blur") is None
                    else float(values["glow_blur"] or 0)
                )
                * factor,
                opacity=opacity * halo.opacity,
            )
        return replace(
            base,
            position=point,
            scale=base.scale * factor,
            fill=colors.fill,
            outline=colors.outline,
            border=colors.border * factor,
            opacity=opacity,
        )

    halo = paint.glow
    base = VisualState(
        position=position,
        scale=scale,
        fill=halo.color if glow and halo is not None else paint.fill,
        outline=halo.color if glow and halo is not None else paint.outline,
        border=halo.border if glow and halo is not None else paint.border,
        blur=halo.blur if glow and halo is not None else 0,
        opacity=paint.opacity * (halo.opacity if glow and halo is not None else 1),
    )
    channels: set[Channel] = set()
    for motion in motions:
        if motion.property == "scale":
            channels.update(("position", "scale", "border", "blur"))
        elif motion.property in ("offset_x", "offset_y"):
            channels.add("position")
        elif motion.property == "opacity":
            channels.add("opacity")
        elif motion.property == "glow_blur" and glow:
            channels.add("blur")
    material_channels: dict[str, tuple[Channel, ...]] = (
        {
            "glow_color": ("fill", "outline"),
            "glow_width": ("border",),
            "glow_blur": ("blur",),
            "glow_opacity": ("opacity",),
        }
        if glow
        else {"fill": ("fill",), "stroke": ("outline",), "stroke_width": ("border",)}
    )
    for material in materials:
        channels.update(material_channels.get(material.rule.property, ()))
    points = {
        point for motion in motions for point in (*motion.interval, *motion.breakpoints)
    } | {
        point
        for material in materials
        for point in (
            *material.interval,
            *(frame[0] for frame in material.frames),
            *(material.numeric.breakpoints if material.numeric is not None else ()),
        )
    }
    return TextObject(
        id=f"{item_id}/{target.id}/{'glow' if glow else 'text'}",
        text=target.text,
        lifetime=lifetime,
        font=style.fontname,
        font_size=style.fontsize,
        bold=style.bold,
        italic=style.italic,
        spacing=style.spacing,
        encoding=style.encoding,
        alignment=5,
        state=base,
        layer=0 if glow else 1,
        origin=origin,
        animations=(
            AnimationClip(
                0,
                duration_ms / 1000,
                StateFunction(appearance, frozenset(channels)),
                breakpoints=tuple(
                    sorted(
                        (point - prepared.lyrics.window.start_ms) / 1000
                        for point in points
                        if prepared.lyrics.window.start_ms
                        <= point
                        <= prepared.lyrics.window.end_ms
                    )
                ),
            ),
        )
        if motions or materials
        else (),
    )


def _sweep_clip(
    layer: TextLayer, lifetime: Lifetime, height: int, *, native_clock: bool
) -> RectangleClip:
    """Keep native exposure clocks; transform the mask with its text anchor."""
    position = Vec2(layer.box.center, layer.box.middle)
    sx, sy = layer.style.scale_x / 100, layer.style.scale_y / 100
    if sx <= 0 or sy <= 0:
        raise OutputCapabilityError(
            "Track sweep needs positive initial font scale", origin=layer.origin
        )
    spans = layer.clips
    assert spans is not None
    exposure = layer.active_window or layer.window

    def sample(time: float) -> tuple[float, float, float, float] | None:
        absolute = (lifetime.start + time) * 1000
        if not quantize(exposure.start_ms) <= absolute < quantize(exposure.end_ms):
            return None
        span = next(
            (s for s in spans if quantize(s.start_ms) <= absolute < quantize(s.end_ms)),
            None,
        )
        if span is None:
            return None
        start, end = quantize(span.start_ms), quantize(span.end_ms)
        if end <= start:
            return None
        progress = (absolute - start) / (end - start)
        if native_clock:
            left = (
                floor(span.start.left + 0.5)
                + (floor(span.end.left + 0.5) - floor(span.start.left + 0.5)) * progress
            )
            right = (
                floor(span.start.right + 0.5)
                + (floor(span.end.right + 0.5) - floor(span.start.right + 0.5))
                * progress
            )
            left, right = float(int(left)), float(int(right))
        else:
            left = span.start.left + (span.end.left - span.start.left) * progress
            right = span.start.right + (span.end.right - span.start.right) * progress
        if left >= right:
            return None
        return (
            (left - position.x) / sx,
            -position.y / sy,
            (right - position.x) / sx,
            (height - position.y) / sy,
        )

    points = {exposure.start_ms, exposure.end_ms}
    if spans is not None:
        points.update(t for span in spans for t in (span.start_ms, span.end_ms))
    return RectangleClip(
        0,
        0,
        1,
        1,
        space="local",
        deform=RectangleFunction(
            sample,
            tuple(
                sorted(
                    (t / 1000 - lifetime.start)
                    for t in points
                    if lifetime.start <= t / 1000 <= lifetime.end
                )
            ),
        ),
    )
