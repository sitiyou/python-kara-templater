"""Immutable appearance values, independent of components and the renderer."""

from dataclasses import dataclass, replace

from .ass import Style
from .colors import color
from .composition import Color, Glow, Paint
from .stylesheet import INHERIT, UNSET, ColorStyle, NumberStyle, StyleKeyword
from .timeline import _finite


def _number(value: NumberStyle, default: float, inherited: float) -> float:
    if value is UNSET:
        return default
    if value is INHERIT:
        return inherited
    assert not isinstance(value, StyleKeyword)
    return value


def _color(value: ColorStyle, default: Color, inherited: Color) -> Color:
    if value is UNSET:
        return default
    if value is INHERIT:
        return inherited
    assert not isinstance(value, StyleKeyword)
    return color(value)


def _validate_number(value: NumberStyle, name: str, *, alpha: bool = False) -> None:
    if isinstance(value, StyleKeyword):
        return
    _finite(value, name)
    if value < 0 or (alpha and value > 1):
        raise ValueError(f"invalid {name}: {value}")


@dataclass(frozen=True, kw_only=True)
class Blur:
    color: ColorStyle = UNSET
    radius: NumberStyle = UNSET
    width: NumberStyle = UNSET
    opacity: NumberStyle = UNSET

    def __post_init__(self) -> None:
        if not isinstance(self.color, StyleKeyword):
            color(self.color)
        _validate_number(self.radius, "blur radius")
        _validate_number(self.width, "blur width")
        _validate_number(self.opacity, "blur opacity", alpha=True)

    def resolve(self, base: Glow, inherited: Glow) -> Glow:
        return Glow(
            color=_color(self.color, base.color, inherited.color),
            blur=_number(self.radius, base.blur, inherited.blur),
            border=_number(self.width, base.border, inherited.border),
            opacity=_number(self.opacity, base.opacity, inherited.opacity),
        )


@dataclass(frozen=True, kw_only=True)
class PaintStyle:
    fill: ColorStyle = UNSET
    stroke: ColorStyle = UNSET
    stroke_width: NumberStyle = UNSET
    opacity: NumberStyle = UNSET
    blur: Blur | StyleKeyword | None = UNSET

    def __post_init__(self) -> None:
        for value in (self.fill, self.stroke):
            if not isinstance(value, StyleKeyword):
                color(value)
        if self.blur is not None and not isinstance(self.blur, (Blur, StyleKeyword)):
            raise TypeError("blur must be Blur, None or a style keyword")
        _validate_number(self.stroke_width, "stroke width")
        _validate_number(self.opacity, "opacity", alpha=True)

    def resolve(self, base: Paint, *, inherited: Paint | None = None) -> Paint:
        inherited = base if inherited is None else inherited
        glow = base.glow
        if self.blur is None:
            glow = None
        elif self.blur is INHERIT:
            glow = inherited.glow
        elif isinstance(self.blur, Blur):
            glow = self.blur.resolve(
                base.glow or Glow(color=base.fill),
                inherited.glow or Glow(color=inherited.fill),
            )
        return Paint(
            fill=_color(self.fill, base.fill, inherited.fill),
            outline=_color(self.stroke, base.outline, inherited.outline),
            border=_number(self.stroke_width, base.border, inherited.border),
            opacity=_number(self.opacity, base.opacity, inherited.opacity),
            glow=glow,
        )


@dataclass(frozen=True, kw_only=True)
class TextStyle(PaintStyle):
    font_size: NumberStyle = UNSET
    font_name: str | None = None
    spacing: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_number(self.font_size, "font size")
        if self.font_size == 0:
            raise ValueError("font size must be positive")
        if self.font_name is not None and not self.font_name:
            raise ValueError("font name must not be empty")
        if self.spacing is not None:
            _finite(self.spacing, "spacing")

    def apply_to_style(self, style: Style) -> Style:
        return replace(
            style,
            fontsize=_number(self.font_size, style.fontsize, style.fontsize),
            fontname=style.fontname if self.font_name is None else self.font_name,
            spacing=style.spacing if self.spacing is None else self.spacing,
        )


@dataclass(frozen=True)
class TextSpan:
    """Codepoint range in the complete body text; later spans take precedence."""

    start: int
    end: int
    style: PaintStyle = PaintStyle()
    overlay: PaintStyle = PaintStyle()
    classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int:
            raise TypeError("text span boundaries must be integers")
        if not 0 <= self.start < self.end:
            raise ValueError("text span must be a nonempty, nonnegative range")
        _validate_span_style(self.style, self.overlay, self.classes)


def _validate_span_style(
    style: PaintStyle, overlay: PaintStyle, classes: tuple[str, ...]
) -> None:
    if isinstance(style, TextStyle) or isinstance(overlay, TextStyle):
        raise TypeError("range styles require PaintStyle; geometry belongs to the text")
    if any(not name or any(c.isspace() for c in name) for name in classes):
        raise ValueError("range classes must be nonempty names without whitespace")


@dataclass(frozen=True)
class RubySpan:
    """A codepoint range within one source reading, independent of its layout."""

    unit_index: int
    segment_index: int
    style: PaintStyle = PaintStyle()
    overlay: PaintStyle = PaintStyle()
    start: int = 0
    end: int | None = None
    classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for index in (self.unit_index, self.segment_index, self.start):
            if type(index) is not int or index < 0:
                raise ValueError("ruby span indices must be nonnegative integers")
        if self.end is not None and (
            type(self.end) is not int or self.end <= self.start
        ):
            raise ValueError("ruby span end must be an integer after start")
        _validate_span_style(self.style, self.overlay, self.classes)
