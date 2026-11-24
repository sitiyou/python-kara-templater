"""Unsung and sung paint values projected from ASS styles."""

from dataclasses import dataclass, field

from .ass import Style
from .composition import Color, Paint
from .document_text import _packed_color


@dataclass(frozen=True)
class PaintPair:
    """The unsung and sung Paint values for one visual target.

    Paint changes do not rewrite its source singing clock.
    """

    before: Paint = field(default_factory=Paint)
    after: Paint = field(default_factory=Paint)


@dataclass(frozen=True, kw_only=True)
class KaraokeTheme:
    """Color role overrides shared by catalog effects and their inherited cues.

    An omitted role inherits from the outer theme. Ordinary catalog effects
    retain source outlines until an outline role is supplied. Duotone supplies
    contrasting outlines for both singing states. Explicit effect colors win.
    """

    sung: Color | None = None
    unsung: Color | None = None
    sung_outline: Color | None = None
    unsung_outline: Color | None = None
    shine: Color | None = None

    def overlay(self, inner: "KaraokeTheme") -> "KaraokeTheme":
        """Override only roles supplied by the inner theme."""
        return KaraokeTheme(
            sung=inner.sung or self.sung, unsung=inner.unsung or self.unsung,
            sung_outline=inner.sung_outline or self.sung_outline,
            unsung_outline=inner.unsung_outline or self.unsung_outline,
            shine=inner.shine or self.shine,
        )


# One set of ink roles for the catalog. Unstyled lyrics retain their source paint.
_DEFAULT_SUNG = Color(255, 90, 111)
_DEFAULT_UNSUNG = Color(255, 255, 255)
_EMPTY_THEME = KaraokeTheme()


def paint_pair_from_style(style: Style) -> PaintPair:
    """ASS secondary is unsung, primary is sung; decode AABBGGRR at this boundary."""

    def decode(key: str, default: str) -> tuple[Color, float]:
        value = next(
            (v for k, v in style.fields.items() if k.lower() == key.lower()), default
        )
        try:
            packed = _packed_color(value)
        except ValueError as error:
            raise ValueError(f"style {style.name}: invalid {key}") from error
        return (
            Color(packed & 255, (packed >> 8) & 255, (packed >> 16) & 255),
            1 - ((packed >> 24) & 255) / 255,
        )

    outline, outline_opacity = decode("OutlineColour", "&H00000000")
    before, before_opacity = decode("SecondaryColour", "&H000000FF")
    after, after_opacity = decode("PrimaryColour", "&H00FFFFFF")
    if style.outline and (
        outline_opacity != before_opacity or outline_opacity != after_opacity
    ):
        raise ValueError(
            f"style {style.name}: independent outline alpha needs an explicit Paint recipe"
        )
    return PaintPair(
        Paint(before, outline, style.outline, before_opacity),
        Paint(after, outline, style.outline, after_opacity),
    )
