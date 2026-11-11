"""Fixed RGB colors for effects; opacity is always a separate property."""

from .composition import Color

WHITE = Color.hex("#ffffff")
BLACK = Color.hex("#000000")
RED = Color.hex("#ff0000")
GREEN = Color.hex("#00ff00")
BLUE = Color.hex("#0000ff")
YELLOW = Color.hex("#ffff00")
CYAN = Color.hex("#00ffff")
MAGENTA = Color.hex("#ff00ff")
ORANGE = Color.hex("#ffa500")
PURPLE = Color.hex("#800080")
PINK = Color.hex("#ffc0cb")
GRAY = Color.hex("#808080")


def color(value: Color | str) -> Color:
    if isinstance(value, Color):
        return value
    if isinstance(value, str):
        return Color.hex(value)
    raise TypeError("color must be Color or #RRGGBB")
