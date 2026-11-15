"""Resolve role and source-range styles before output layer expansion."""

from dataclasses import replace

from .appearance import PaintPair
from .ass import Style
from .components import Body, Component, Ruby
from .composition import Color, Paint
from .import_ass import paint_pair_from_style
from .stylesheet import UNSET, StyleSheet
from .text_style import RubySpan, TextSpan


def _values(paint: Paint, font_size: float) -> dict[str, Color | float]:
    return {
        "fill": paint.fill,
        "stroke": paint.outline,
        "stroke_width": paint.border,
        "opacity": paint.opacity,
        "font_size": font_size,
    }


def _resolve(
    sheet: StyleSheet,
    node: Component,
    paint: Paint,
    font_size: float,
    *,
    sung: bool = False,
    inherited: Paint | None = None,
    resolved_parent: Component | None = None,
    check_geometry: bool = True,
) -> Paint:
    values = sheet.resolve(
        node,
        _values(paint, font_size),
        sung=sung,
        state_only=sung,
        inherited=_values(paint if inherited is None else inherited, font_size),
        resolved_parent=resolved_parent,
    )
    if check_geometry and values.get("font_size", font_size) != font_size:
        raise ValueError("range or sung font_size cannot change layout; use scale")
    fill, stroke = values["fill"], values["stroke"]
    width, opacity = values["stroke_width"], values["opacity"]
    assert isinstance(fill, Color) and isinstance(stroke, Color)
    assert isinstance(width, (int, float)) and isinstance(opacity, (int, float))
    return replace(paint, fill=fill, outline=stroke, border=width, opacity=opacity)


def prepare_style(node: Body | Ruby, source: Style, sheet: StyleSheet) -> Style:
    style = node.text_style.apply_to_style(source)
    defaults: dict[str, Color | float] = {"font_size": style.fontsize}
    if node.parent is not None:
        defaults = sheet.resolve(node.parent, defaults)
    values = sheet.resolve(node, defaults)
    sung = sheet.resolve(node, values, sung=True, state_only=True)
    if values["font_size"] != sung["font_size"]:
        raise ValueError("sung font_size cannot change layout; use scale")
    size = values["font_size"]
    assert isinstance(size, (int, float))
    return replace(style, fontsize=size)


def base_paint(node: Body | Ruby, style: Style, sheet: StyleSheet) -> Paint:
    paint = node.text_style.resolve(paint_pair_from_style(style).before)
    if node.parent is not None:
        paint = _resolve(
            sheet, node.parent, paint, style.fontsize, check_geometry=False
        )
    return _resolve(sheet, node, paint, style.fontsize, check_geometry=False)


def range_paints(
    node: Body | Ruby,
    style: Style,
    sheet: StyleSheet,
    base: Paint,
    active: tuple[TextSpan | RubySpan, ...],
    attributes: dict[str, str | int],
) -> tuple[Paint, Component]:
    """Apply normal declarations; return a local node for the sung cascade.

    Callers resolve the shared overlay against the returned per-target base.
    """
    local = Component(
        classes=node.classes | {name for span in active for name in span.classes}
    )
    local.kind, local.parent, local.attributes = node.kind, node, attributes
    paint = base
    for span in active:
        paint = span.style.resolve(paint, inherited=base)
        for name, value in (
            ("fill", span.style.fill),
            ("stroke", span.style.stroke),
            ("stroke_width", span.style.stroke_width),
            ("opacity", span.style.opacity),
        ):
            # Typed setters validate the existing style-cascade representation.
            if value is not UNSET:
                local.style._write(name, value)
    return _resolve(
        sheet, local, paint, style.fontsize, inherited=base, resolved_parent=node
    ), local


def sung_paint(
    node: Body | Ruby,
    local: Component,
    style: Style,
    sheet: StyleSheet,
    base: Paint,
    overlay: Paint,
    active: tuple[TextSpan | RubySpan, ...],
) -> PaintPair:
    if node.parent is not None:
        overlay = _resolve(
            sheet, node.parent, overlay, style.fontsize, sung=True, inherited=base
        )
    sung = _resolve(sheet, node, overlay, style.fontsize, sung=True, inherited=base)
    sung = _resolve(
        sheet,
        local,
        sung,
        style.fontsize,
        sung=True,
        inherited=base,
        resolved_parent=node,
    )
    for span in active:
        sung = span.overlay.resolve(sung, inherited=base)
    return PaintPair(base, sung)
