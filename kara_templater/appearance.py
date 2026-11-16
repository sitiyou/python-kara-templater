"""Unsung and sung paint values projected from ASS styles."""

from dataclasses import dataclass, field

from .composition import Paint


@dataclass(frozen=True)
class PaintPair:
    """The unsung and sung Paint values for one visual target.

    Paint changes do not rewrite its source singing clock.
    """

    before: Paint = field(default_factory=Paint)
    after: Paint = field(default_factory=Paint)

