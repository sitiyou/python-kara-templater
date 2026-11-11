"""Independent inheritance switches for associated visual objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Follow:
    position: bool = True
    scale: bool = True
    opacity: bool = True
    fade: bool = True

    def __post_init__(self):
        if any(
            type(getattr(self, name)) is not bool
            for name in ("position", "scale", "opacity", "fade")
        ):
            raise TypeError("follow switches must be bool")

    def allows(self, property):
        return (
            self.position
            if property in {"offset_x", "offset_y"}
            else getattr(self, property)
        )


DEFAULT_FOLLOW = Follow()
