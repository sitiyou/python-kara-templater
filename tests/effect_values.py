"""Inspect composed author properties independently of the chosen output path."""

from dataclasses import replace

from kara_templater import DynamicProperties, Paint, SampleContext, prepare_sampling
from kara_templater.ass_output import _animated_opacity, _offset, _transform
from kara_templater.properties import AnimatedProperties, PropertyValue


def properties_at(plan, layer, time):
    value = (
        plan.dynamic.function(
            SampleContext(time, 0, layer.window, layer.animation_id, 0)
        )
        if plan.dynamic
        else DynamicProperties()
    )
    group = tuple(a for a in layer.opacity_animations if a.component == "group")
    glow = tuple(a for a in layer.opacity_animations if a.component == "glow")
    opacity = value.opacity
    glow_opacity = value.glow_opacity
    if group:
        opacity *= _animated_opacity(
            replace(layer, paint=Paint(), opacity_animations=group, component="both"),
            time,
            glow=False,
        )
    if glow:
        base = layer.paint.glow
        if glow_opacity is not None:
            base = replace(base, opacity=glow_opacity)
        glow_opacity = _animated_opacity(
            replace(layer, paint=Paint(glow=base), opacity_animations=glow),
            time,
            glow=True,
        )
    return replace(
        value,
        opacity=opacity,
        glow_opacity=glow_opacity,
        scale=value.scale * _transform(layer, time)[0],
        offset_x=value.offset_x + _offset(layer, time, "x"),
        offset_y=value.offset_y + _offset(layer, time, "y"),
    )


def sampled_layers(plan, layers=None):
    layers = plan.layers if layers is None else layers
    return prepare_sampling(layers, plan.dynamic).evaluate() if plan.dynamic else layers


def same_effect(layer):
    """Compare layers from different effect classes, retaining source metadata."""
    return replace(layer, origin=replace(layer.origin, effect="comparison"))


def animated_property(name: str, value: PropertyValue) -> AnimatedProperties:
    """Construct a checked single-property declaration for parameterized tests."""
    match name:
        case "scale":
            return {"scale": value}
        case "opacity":
            return {"opacity": value}
        case "offset_x":
            return {"offset_x": value}
        case "offset_y":
            return {"offset_y": value}
        case _:
            raise ValueError(name)
