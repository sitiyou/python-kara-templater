"""Relative lyric parameters, evaluated when a measured target or interval is bound."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Self

from .geometry import finite


@dataclass(frozen=True)
class _Expression:
    _field: str
    _steps: tuple[tuple[Literal["add", "multiply", "divide", "clamp"], float, float], ...] = ()

    def __add__(self, value: float) -> Self:
        finite(value)
        return replace(self, _steps=(*self._steps, ("add", value, 0)))

    def __sub__(self, value: float) -> Self:
        return self + -value

    def __mul__(self, value: float) -> Self:
        finite(value)
        return replace(self, _steps=(*self._steps, ("multiply", value, 0)))

    def __truediv__(self, value: float) -> Self:
        finite(value)
        if value == 0:
            raise ZeroDivisionError("relative parameter divisor is zero")
        return replace(self, _steps=(*self._steps, ("divide", value, 0)))

    __rmul__ = __mul__
    __radd__ = __add__

    def clamp(self, minimum: float, maximum: float) -> Self:
        """Limit the resolved value to inclusive bounds in the parameter's units."""
        finite(minimum, maximum)
        if minimum > maximum:
            raise ValueError("minimum exceeds maximum")
        return replace(self, _steps=(*self._steps, ("clamp", minimum, maximum)))

    def __repr__(self) -> str:
        result = self._field
        for index, (operation, a, b) in enumerate(self._steps):
            if index:
                result = f"({result})"
            if operation == "clamp":
                result += f".clamp({a!r}, {b!r})"
            else:
                symbol = {"add": "+", "multiply": "*", "divide": "/"}[operation]
                result += f" {symbol} {a!r}"
        return result

    def _apply(self, value: float | None, path: str) -> float:
        if value is None:
            raise ValueError(f"{path} requires {self._field} at binding")
        for operation, a, b in self._steps:
            if operation == "add":
                value += a
            elif operation == "multiply":
                value *= a
            elif operation == "divide":
                value /= a
            else:
                value = min(b, max(a, value))
        finite(value)
        return value


class LengthExpr(_Expression):
    """A script-pixel length measured from a glyph or canvas at preparation."""

    def _pixels(self, size: float | None, height: float, path: str) -> float:
        if self._field == "Canvas.height":
            return self._apply(height, path)
        if self._field == "Glyph.font_size":
            return self._apply(size, path)
        raise ValueError(f"{path}: unknown length field {self._field}")


class TimeExpr(_Expression):
    """Seconds measured from a singing interval or its bound animation."""

    def _seconds(self, note: float | None, animation: float | None, path: str) -> float:
        if self._field == "Animation.duration":
            return self._apply(animation, path)
        if self._field == "Note.duration":
            return self._apply(note, path)
        raise ValueError(f"{path}: unknown time field {self._field}")


class Glyph:
    """Glyph.font_size reads the current body or reading's authored font size."""

    font_size = LengthExpr("Glyph.font_size")


class Canvas:
    """Canvas.height reads the document's vertical script resolution."""

    height = LengthExpr("Canvas.height")


class Note:
    """Note.duration reads the source singing interval, including each repeat."""

    duration = TimeExpr("Note.duration")


class Animation:
    """Animation.duration reads the requested animation duration or its bound interval."""

    duration = TimeExpr("Animation.duration")


def _width(value: float | LengthExpr, size: float, height: float, path: str) -> float:
    result = value._pixels(size, height, path) if isinstance(value, LengthExpr) else value
    finite(result)
    if result < 0:
        raise ValueError(f"{path} must be nonnegative")
    return result
