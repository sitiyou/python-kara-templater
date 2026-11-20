"""Unsung and sung paint values projected from ASS styles."""

from dataclasses import dataclass, field

from .composition import Color, Paint


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
