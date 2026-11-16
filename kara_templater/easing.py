"""Pure easing functions for common state animations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import overload

from .geometry import finite
from .scene_animation import linear_rate


def ease_in(p: float) -> float:
    """An accelerating scalar easing curve for normalized progress."""
    return p * p


def ease_out(p: float) -> float:
    """A decelerating scalar easing curve for normalized progress."""
    return 1 - (1 - p) ** 2


def ease_in_out(p: float) -> float:
    """A scalar easing curve that accelerates then decelerates across normalized progress."""
    return 2 * p * p if p < 0.5 else 1 - 2 * (1 - p) ** 2


@overload
def there_and_back(
    p: float,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> float: ...


@overload
def there_and_back(
    p: None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> BackRate: ...


def there_and_back(
    p: float | None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> float | BackRate:
    """Use as a rate directly, or configure a peak, hold, rise and fall."""
    return_at = peak_at if return_at is None else return_at
    finite(peak_at)
    finite(return_at)
    if not 0 < peak_at <= return_at < 1:
        raise ValueError("require 0 < peak_at <= return_at < 1")
    if not callable(rise) or not callable(fall):
        raise TypeError("rise and fall must be rate functions")

    rate = BackRate(peak_at, return_at, rise, fall)
    return rate if p is None else rate(p)


@dataclass(frozen=True)
class BackRate:
    """Piecewise rise, hold and fall on normalized progress, independent of clocks."""

    peak_at: float
    return_at: float
    rise: Callable[[float], float]
    fall: Callable[[float], float]

    def __post_init__(self) -> None:
        finite(self.peak_at, self.return_at)
        if not 0 < self.peak_at <= self.return_at < 1:
            raise ValueError("require 0 < peak_at <= return_at < 1")
        if not callable(self.rise) or not callable(self.fall):
            raise TypeError("rise and fall must be rate functions")

    def __call__(self, progress: float) -> float:
        """Evaluate the configured rise, hold or fall without advancing state."""
        if progress < self.peak_at:
            return self.rise(progress / self.peak_at)
        if progress <= self.return_at:
            return 1.0
        return 1 - self.fall((progress - self.return_at) / (1 - self.return_at))
