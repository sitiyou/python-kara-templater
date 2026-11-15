"""Typed material animation values and bounded source-target evaluation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import floor
from typing import Literal, TypedDict

from .behaviors import BoundProperty, MotionRule, bind_property
from .composition import Color, Paint
from .model import Segment
from .properties import (
    BackRate,
    Contextual,
    Envelope,
    Keyframes,
    PropertyTarget,
    PropertyValue,
    TimeInterval,
    TimeRef,
    Transition,
    ease_in,
    ease_in_out,
    ease_out,
    linear,
    smooth,
    there_and_back,
)
from .timeline import DisplayWindow, _finite


def _mix(start: Color, end: Color, progress: float) -> Color:
    _finite(progress, "color interpolation progress")
    if not 0 <= progress <= 1:
        raise ValueError("color interpolation progress must be in 0..1")
    return Color(
        *(
            floor(a + (b - a) * progress + 0.5)
            for a, b in zip(
                (start.red, start.green, start.blue),
                (end.red, end.green, end.blue),
                strict=True,
            )
        )
    )


@dataclass(frozen=True)
class ColorTransition:
    start: Color
    end: Color
    rate: Callable[[float], float] = linear

    def __post_init__(self) -> None:
        if not isinstance(self.start, Color) or not isinstance(self.end, Color):
            raise TypeError("color transition endpoints must be Color")
        if not callable(self.rate):
            raise TypeError("color transition rate must be callable")

    def __call__(self, progress: float) -> Color:
        return _mix(self.start, self.end, self.rate(progress))


@dataclass(frozen=True)
class ColorKeyframe:
    at: float | TimeRef
    value: Color
    rate: Callable[[float], float] = linear

    def __post_init__(self) -> None:
        if not isinstance(self.at, TimeRef):
            _finite(self.at, "color keyframe position")
            if not 0 <= self.at <= 1:
                raise ValueError("color keyframe fraction must be in 0..1")
        if not isinstance(self.value, Color) or not callable(self.rate):
            raise TypeError("color keyframes require Color and a callable rate")


@dataclass(frozen=True, init=False)
class ColorKeyframes:
    frames: tuple[ColorKeyframe, ...]

    def __init__(self, *frames: ColorKeyframe) -> None:
        if len(frames) < 2 or any(
            not isinstance(frame, ColorKeyframe) for frame in frames
        ):
            raise ValueError("ColorKeyframes requires at least two color keyframes")
        object.__setattr__(self, "frames", frames)

    def resolve(
        self,
        interval: tuple[float, float],
        segments: tuple[Segment, ...],
        window: DisplayWindow,
    ) -> tuple[tuple[float, Color, Callable[[float], float]], ...]:
        start, end = interval
        points = []
        for frame in self.frames:
            at = (
                frame.at.resolve(segments, window)
                if isinstance(frame.at, TimeRef)
                else start + (end - start) * frame.at
            )
            if at is None:
                raise ValueError("color keyframe has no singing time")
            points.append((at, frame.value, frame.rate))
        if points[0][0] != start or points[-1][0] != end:
            raise ValueError(
                "color keyframes must start and end at the animation endpoints"
            )
        fractions = [
            frame.at for frame in self.frames if not isinstance(frame.at, TimeRef)
        ]
        if any(a >= b for a, b in pairwise(fractions)):
            raise ValueError("color keyframe fractions must increase")
        if not (start == end and all(point[0] == start for point in points)) and any(
            a[0] >= b[0] for a, b in pairwise(points)
        ):
            raise ValueError("color keyframe times must increase")
        return tuple(points)


type ColorValue = (
    Color
    | tuple[Color, Color]
    | ColorTransition
    | ColorKeyframes
    | Callable[[float], Color]
)
type MaterialProperty = Literal[
    "fill",
    "stroke",
    "stroke_width",
    "blur_color",
    "blur_radius",
    "blur_width",
    "blur_opacity",
]


@dataclass(frozen=True, kw_only=True)
class PaintBounds:
    """Required only when geometry callbacks have no statically known bound."""

    stroke_width: float | None = None
    blur_radius: float | None = None
    blur_width: float | None = None

    def __post_init__(self) -> None:
        for value in (self.stroke_width, self.blur_radius, self.blur_width):
            if value is not None:
                _finite(value, "paint bound")
                if value < 0:
                    raise ValueError("paint bounds must be nonnegative")

    def for_property(self, name: MaterialProperty) -> float | None:
        return {
            "stroke_width": self.stroke_width,
            "blur_radius": self.blur_radius,
            "blur_width": self.blur_width,
        }.get(name)


@dataclass(frozen=True)
class MaterialRule:
    property: MaterialProperty
    value: ColorValue | PropertyValue | Envelope
    units: tuple[int, ...]
    mode: str
    segments: tuple[tuple[int, int], ...] | None
    during: TimeInterval
    window: DisplayWindow
    keep: bool = False
    compose: Literal["replace", "override"] = "replace"
    bound: float | None = None
    rate: Callable[[float], float] = linear


def material_value(paint: Paint, name: MaterialProperty) -> Color | float:
    if name == "fill":
        return paint.fill
    if name == "stroke":
        return paint.outline
    if name == "stroke_width":
        return paint.border
    if paint.glow is None:
        raise ValueError(f"{name} requires an enabled Blur style on the target")
    return {
        "blur_color": paint.glow.color,
        "blur_radius": paint.glow.blur,
        "blur_width": paint.glow.border,
        "blur_opacity": paint.glow.opacity,
    }[name]


_BOUNDED_RATES = (linear, smooth, ease_in, ease_out, ease_in_out, there_and_back)


def _bounded_rate(rate: Callable[[float], float]) -> bool:
    return rate in _BOUNDED_RATES or (
        isinstance(rate, BackRate)
        and _bounded_rate(rate.rise)
        and _bounded_rate(rate.fall)
    )


def _upper(value: PropertyValue, explicit: float | None, base: float) -> float | None:
    candidates: tuple[float, ...] | None = None
    if isinstance(value, (int, float)):
        candidates = (value,)
    elif isinstance(value, tuple):
        a, b = value
        assert isinstance(a, (int, float)) and isinstance(b, (int, float))
        candidates = (a, b)
    elif isinstance(value, Transition) and _bounded_rate(value.rate):
        candidates = (value.start, value.end)
    elif isinstance(value, Keyframes) and all(
        _bounded_rate(f.rate) for f in value.frames
    ):
        candidates = tuple(f.value for f in value.frames)
    if candidates is not None:
        if any(v < 0 for v in candidates):
            raise ValueError("material geometry cannot be negative")
        known = max(base, *candidates)
        if explicit is not None and explicit < known:
            raise ValueError(
                "declared paint bound does not cover known animation values"
            )
        return known if explicit is None else explicit
    if explicit is not None and explicit < base:
        raise ValueError("declared paint bound does not cover the base style")
    return explicit


@dataclass(frozen=True)
class BoundMaterial:
    rule: MaterialRule
    interval: tuple[int, int]
    color: Color | ColorTransition | Callable[[float], Color] | None = None
    frames: tuple[tuple[float, Color, Callable[[float], float]], ...] = ()
    numeric: BoundProperty | None = None
    upper: float | None = None

    def at(self, time: float) -> Color | float | None:
        start, end = self.interval
        if time < start or (time >= end and not self.rule.keep):
            return None
        if self.numeric is not None:
            value = self.numeric.at(time)
            assert value is not None
            _finite(value, self.rule.property)
            if value < 0 or (self.upper is not None and value > self.upper):
                raise ValueError(f"{self.rule.property} exceeds its paint bound")
            return value
        if self.frames:
            if time >= end:
                return self.frames[-1][1]
            for (a, av, rate), (b, bv, _) in pairwise(self.frames):
                if a <= time < b:
                    return _mix(av, bv, rate((time - a) / (b - a)))
            raise ValueError("color sample is outside its keyframe interval")
        value = self.color
        if callable(value):
            progress = 1.0 if start == end else min(1.0, (time - start) / (end - start))
            value = value(progress)
        if not isinstance(value, Color):
            raise TypeError("color animation callbacks must return Color")
        return value


def bind_material(
    rule: MaterialRule,
    paint: Paint,
    segments: tuple[Segment, ...],
    *,
    target: PropertyTarget | None = None,
) -> BoundMaterial:
    start, end = rule.during
    assert isinstance(start, int) and isinstance(end, int)
    base = material_value(paint, rule.property)
    value = rule.value
    if isinstance(base, Color):
        if isinstance(value, ColorKeyframes):
            return BoundMaterial(
                rule,
                (start, end),
                frames=value.resolve((start, end), segments, rule.window),
            )
        if isinstance(value, tuple):
            a, b = value
            if not isinstance(a, Color) or not isinstance(b, Color):
                raise TypeError("color transitions require Color endpoints")
            value = ColorTransition(a, b, rule.rate)
        if isinstance(value, (Color, ColorTransition)):
            return BoundMaterial(rule, (start, end), color=value)
        if callable(value) and not isinstance(value, (Contextual, Transition)):
            # The public ColorValue signature and runtime Color check retain
            # a precise callback contract without treating arbitrary values as colors.
            return BoundMaterial(rule, (start, end), color=_checked_color(value))
        raise TypeError("invalid color animation value")
    if isinstance(value, Envelope):
        duration = end - start - value.release
        value = value._keyframes(duration, base)
    if isinstance(value, tuple):
        a, b = value
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise TypeError("numeric material transitions require numbers")
        value = Transition(a, b, rule.rate)
    if isinstance(value, (Color, ColorKeyframes, ColorTransition)):
        raise TypeError("numeric material properties require numeric values")
    # A checked adapter narrows the color/numeric callable union at this boundary.
    numeric_value: PropertyValue
    if isinstance(value, (int, float, Keyframes, Contextual, Transition)):
        numeric_value = value
    else:
        numeric_value = _checked_number(value)
    upper = (
        1.0
        if rule.property == "blur_opacity"
        else _upper(numeric_value, rule.bound, base)
    )
    if upper is None:
        raise ValueError(
            f"{rule.property} callback requires an explicit PaintBounds upper bound"
        )
    numeric_rule = MotionRule(
        rule.units,
        rule.mode,
        numeric_value,
        (start, end),
        rule.keep,
        property="opacity" if rule.property == "blur_opacity" else "glow_blur",
    )
    numeric = bind_property(numeric_rule, segments, rule.window, (0, 0), target=target)
    assert numeric is not None
    return BoundMaterial(rule, (start, end), numeric=numeric, upper=upper)


def _checked_color(function: Callable[[float], object]) -> Callable[[float], Color]:
    def checked(progress: float) -> Color:
        value = function(progress)
        if not isinstance(value, Color):
            raise TypeError("color animation callbacks must return Color")
        return value

    return checked


def _checked_number(function: Callable[[float], object]) -> Callable[[float], float]:
    def checked(progress: float) -> float:
        value = function(progress)
        if not isinstance(value, (int, float)):
            raise TypeError("numeric material callbacks must return numbers")
        return value

    return checked


class MaterialSamples(TypedDict, total=False):
    fill: Color
    stroke: Color
    stroke_width: float
    glow_color: Color
    glow_blur: float
    glow_width: float
    glow_opacity: float


def sample_materials(motions: Sequence[BoundMaterial], time: float) -> MaterialSamples:
    values: MaterialSamples = {}
    for motion in motions:
        value = motion.at(time)
        if value is None:
            continue
        name = motion.rule.property
        if isinstance(value, Color):
            if name == "fill":
                values["fill"] = value
            elif name == "stroke":
                values["stroke"] = value
            else:
                values["glow_color"] = value
        elif name == "stroke_width":
            values["stroke_width"] = value
        elif name == "blur_radius":
            values["glow_blur"] = value
        elif name == "blur_width":
            values["glow_width"] = value
        else:
            values["glow_opacity"] = value
    return values
