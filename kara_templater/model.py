from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    """An axis-aligned layout rectangle in script pixels.

    right, center, and middle are derived from left, top, width, and height.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """The rectangle left coordinate plus its width, in script pixels."""
        return self.left + self.width

    @property
    def center(self) -> float:
        """The horizontal midpoint of the layout rectangle."""
        return self.left + self.width / 2

    @property
    def middle(self) -> float:
        """The vertical midpoint of the layout rectangle."""
        return self.top + self.height / 2
