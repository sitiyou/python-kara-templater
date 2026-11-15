"""Independent inheritance switches for associated visual objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Follow:
    """Choose which body motion properties a reading or decoration follows.

    Position, scale, opacity, and fade are independent switches.
    """

    position: bool = True
    scale: bool = True
    opacity: bool = True
    fade: bool = True

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, name)) is not bool
            for name in ("position", "scale", "opacity", "fade")
        ):
            raise TypeError("follow switches must be bool")

    def allows(self, property: str) -> bool:
        """Whether this following policy enables the requested motion property."""
        return (
            self.position
            if property in {"offset_x", "offset_y"}
            else {"scale": self.scale, "opacity": self.opacity, "fade": self.fade}[
                property
            ]
        )


DEFAULT_FOLLOW = Follow()
