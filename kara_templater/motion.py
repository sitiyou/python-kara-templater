"""Reusable, explicitly configured animations and compile-time events."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Literal, cast, overload

from .animation import Pulse
from .behaviors import MotionRule, declare_properties
from .characters import TextRange
from .karaoke import KaraokeItem
from .matching import SourceMatch
from .material_animation import ColorValue, MaterialProperty, MaterialRule, PaintBounds
from .properties import (
    AnimatedProperties,
    CompositionMode,
    Envelope,
    Keyframe,
    Keyframes,
    PropertyValue,
    TimeRef,
    Transition,
    linear,
    singing,
    there_and_back,
)
from .stylesheet import UNSET, StyleKeyword
from .timeline import DisplayWindow, _finite, _milliseconds

type Milliseconds = int
type RateFunction = Callable[[float], float]
type _Unset = Literal[StyleKeyword.UNSET]
type AnimationRule = MotionRule | MaterialRule

_DEFAULT_HIGHLIGHT = Pulse()


@dataclass(frozen=True)
class AnimationTarget:
    """A stable source item and unit/segment selection for a Track animation.

    kind determines whether the transform affects a group, syllable, reading, or
    segment.
    """

    item_id: str
    units: tuple[int, ...]
    kind: Literal["group", "syllable", "ruby", "segment"] = "syllable"
    segments: tuple[tuple[int, int], ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id:
            raise ValueError("animation target needs a source item id")
        if any(type(unit) is not int or unit < 0 for unit in self.units):
            raise ValueError("animation target units must be nonnegative integers")
        if len(set(self.units)) != len(self.units):
            raise ValueError("animation target contains duplicate syllables")
        if self.kind not in {"group", "syllable", "ruby", "segment"}:
            raise ValueError("unknown animation target kind")
        if self.kind == "segment" and not self.segments:
            raise ValueError("segment animation targets need segment references")
        if self.segments is not None:
            if len(set(self.segments)) != len(self.segments):
                raise ValueError("animation target contains duplicate segments")
            for unit, segment in self.segments:
                if type(unit) is not int or unit not in self.units:
                    raise ValueError("animation segment is outside selected syllables")
                if type(segment) is not int or segment < 0:
                    raise ValueError("animation segment index must be nonnegative")


@dataclass(frozen=True)
class AnimationEvent:
    """A resolved Track trigger with target, millisecond start/end, source index, and display window.

    Subclasses identify singing or display events.
    """

    target: AnimationTarget
    start: Milliseconds
    end: Milliseconds
    index: int
    window: DisplayWindow


class Syllable:
    """Namespace for a Singing event spanning the first through last segment of each timed source unit, including its internal pauses."""

    class Singing(AnimationEvent):
        """One event per timed syllable; the interval includes internal pauses."""


class Display:
    """Namespace for display Start and End events.

    These refer to original visibility boundaries, independently of optional
    animation extensions.
    """

    class Start(AnimationEvent):
        """Original display start, independent of animation window extensions."""

    class End(AnimationEvent):
        """Original display end."""


class SegmentSinging(AnimationEvent):
    """One event per source segment, including repeated readings."""


@dataclass(frozen=True)
class Transform:
    """Sparse animation output. Omitted properties are not written."""

    scale: float | None = None
    opacity: float | None = None
    offset_x: float | None = None
    offset_y: float | None = None

    def __post_init__(self) -> None:
        for name, value in self.values().items():
            _finite(value, name)
            if name == "scale" and value <= 0:
                raise ValueError("scale must be positive")
            if name == "opacity" and not 0 <= value <= 1:
                raise ValueError("opacity must be in 0..1")

    def values(self) -> dict[str, float]:
        """Return only explicitly written geometry values as a typed scalar mapping."""
        return {
            name: value
            for name, value in (
                ("scale", self.scale),
                ("opacity", self.opacity),
                ("offset_x", self.offset_x),
                ("offset_y", self.offset_y),
            )
            if value is not None
        }


@dataclass(frozen=True)
class TimeSpan:
    """Seconds relative to the current composition's origin."""

    start: float
    end: float

    def __post_init__(self) -> None:
        _finite(self.start, "interval start")
        _finite(self.end, "interval end")
        if self.end < self.start:
            raise ValueError("interval end must not precede start")

    @property
    def duration(self) -> float:
        """The seconds difference between end and start."""
        return self.end - self.start

    @property
    def interval(self) -> TimeSpan:
        """This seconds interval, suitable for Timeline.play(during=...)."""
        return self


@dataclass(frozen=True)
class AnimationContext:
    """A Track item, current event, and local composition clock.

    syllable/next_syllable expose seconds-based TimeSpan values while event fields
    retain milliseconds.
    """

    item: KaraokeItem
    event: AnimationEvent | None = None
    origin: float = 0.0
    duration: float = 0.0
    initial: Transform = Transform(scale=1, opacity=1, offset_x=0, offset_y=0)

    @property
    def target(self) -> AnimationTarget:
        """Return the current event target; raise when the context is not event-bound."""
        if self.event is None:
            raise ValueError("animation context is not bound to an event")
        return self.event.target

    def _syllable_time(self, index: int) -> TimeSpan | None:
        if not 0 <= index < len(self.item.source.units):
            return None
        segments = self.item.source.units[index].segments
        if not segments:
            return None
        return TimeSpan(
            segments[0].start_ms / 1000 - self.origin,
            segments[-1].end_ms / 1000 - self.origin,
        )

    @property
    def syllable(self) -> TimeSpan:
        """Return the selected source syllable interval as local seconds.

        A single timed syllable is required.
        """
        if self.event is None or len(self.event.target.units) != 1:
            raise ValueError("a single syllable target is required")
        timing = self._syllable_time(self.event.target.units[0])
        if timing is None:
            raise ValueError("target syllable has no timing")
        return timing

    @property
    def next_syllable(self) -> TimeSpan | None:
        """Return the following source syllable interval in local seconds, or None if unavailable."""
        if self.event is None or len(self.event.target.units) != 1:
            raise ValueError("a single syllable target is required")
        return self._syllable_time(self.event.target.units[0] + 1)

    def events[E: AnimationEvent](self, event_type: type[E]) -> Iterator[E]:
        """Enumerate supported display, syllable, or segment events from the original source clocks."""
        item = self.item
        units = tuple(range(len(item.source.units)))
        if event_type in (Display.Start, Display.End):
            at = (
                item.window.start_ms
                if event_type is Display.Start
                else item.window.end_ms
            )
            yield event_type(
                AnimationTarget(item.id, units, "group"), at, at, 0, item.window
            )
        elif event_type is Syllable.Singing:
            for index, unit in enumerate(item.source.units):
                if unit.segments:
                    yield event_type(
                        AnimationTarget(item.id, (index,)),
                        unit.segments[0].start_ms,
                        unit.segments[-1].end_ms,
                        index,
                        item.window,
                    )
        elif event_type is SegmentSinging:
            for ui, unit in enumerate(item.source.units):
                for si, segment in enumerate(unit.segments):
                    yield event_type(
                        AnimationTarget(item.id, (ui,), "segment", ((ui, si),)),
                        segment.start_ms,
                        segment.end_ms,
                        si,
                        item.window,
                    )
        else:
            raise ValueError(f"unsupported animation event {event_type.__qualname__}")


class Animate:
    """A sparse Track event animation declaration for geometry or material properties.

    Duration and offset are milliseconds; sampled functions receive normalized
    progress, and bounds declare costly material extents.
    """

    def __init__(
        self,
        target: AnimationTarget | None = None,
        *,
        scale: PropertyValue | Envelope | _Unset = UNSET,
        opacity: PropertyValue | Envelope | _Unset = UNSET,
        offset_x: PropertyValue | Envelope | _Unset = UNSET,
        offset_y: PropertyValue | Envelope | _Unset = UNSET,
        fill: ColorValue | _Unset = UNSET,
        stroke: ColorValue | _Unset = UNSET,
        stroke_width: PropertyValue | Envelope | _Unset = UNSET,
        blur_color: ColorValue | _Unset = UNSET,
        blur_radius: PropertyValue | Envelope | _Unset = UNSET,
        blur_width: PropertyValue | Envelope | _Unset = UNSET,
        blur_opacity: PropertyValue | Envelope | _Unset = UNSET,
        bounds: PaintBounds | None = None,
        duration: Milliseconds | None = None,
        offset: int = 0,
        rate: RateFunction = linear,
        keep: bool = False,
        compose: CompositionMode = "replace",
    ) -> None:
        materials = (
            fill,
            stroke,
            stroke_width,
            blur_color,
            blur_radius,
            blur_width,
            blur_opacity,
        )
        if all(
            value is UNSET for value in (scale, opacity, offset_x, offset_y, *materials)
        ):
            raise ValueError("Animate requires at least one property")
        if any(value is not UNSET for value in materials) and compose not in {
            "replace",
            "override",
        }:
            raise ValueError(
                "material properties support replace or override composition"
            )
        if duration is not None:
            _milliseconds(duration, "animation duration")
        if type(keep) is not bool:
            raise TypeError("animation keep must be bool")
        if type(offset) is not int:
            raise TypeError("animation offset must be integer milliseconds")
        if not callable(rate):
            raise TypeError("animation rate must be callable")
        self.target = target
        self.scale, self.opacity = scale, opacity
        self.offset_x, self.offset_y = offset_x, offset_y
        self.fill, self.stroke, self.stroke_width = fill, stroke, stroke_width
        self.blur_color, self.blur_radius = blur_color, blur_radius
        self.blur_width, self.blur_opacity, self.bounds = (
            blur_width,
            blur_opacity,
            bounds,
        )
        self.duration, self.offset, self.rate = duration, offset, rate
        self.keep, self.compose = keep, compose

    def _bind(
        self, event: AnimationEvent, offset: int = 0
    ) -> tuple[AnimationRule, ...]:
        target = self.target or event.target
        if target.item_id != event.target.item_id:
            raise ValueError("animation target belongs to a different input item")
        duration = event.end - event.start if self.duration is None else self.duration
        start = event.start + self.offset + offset
        result: list[AnimationRule] = []
        for name, value in (
            ("scale", self.scale),
            ("opacity", self.opacity),
            ("offset_x", self.offset_x),
            ("offset_y", self.offset_y),
        ):
            if value is UNSET:
                continue
            end = start + duration
            if isinstance(value, Envelope):
                end += value.release
                value = value._keyframes(
                    duration, 1 if name in {"scale", "opacity"} else 0
                )
            elif isinstance(value, tuple):
                value = Transition(*value, rate=self.rate)
            values: AnimatedProperties = {}
            # The property name is selected exclusively from the four fields above.
            if name == "scale":
                values["scale"] = value
            elif name == "opacity":
                values["opacity"] = value
            elif name == "offset_x":
                values["offset_x"] = value
            else:
                values["offset_y"] = value
            result.extend(
                declare_properties(
                    values,
                    during=(start, end),
                    keep=self.keep,
                    compose=self.compose,
                    units=target.units,
                    mode="syllable" if target.kind == "segment" else target.kind,
                    segments=target.segments,
                )
            )
        materials: tuple[
            tuple[MaterialProperty, ColorValue | PropertyValue | Envelope | _Unset], ...
        ] = (
            ("fill", self.fill),
            ("stroke", self.stroke),
            ("stroke_width", self.stroke_width),
            ("blur_color", self.blur_color),
            ("blur_radius", self.blur_radius),
            ("blur_width", self.blur_width),
            ("blur_opacity", self.blur_opacity),
        )
        for name, material in materials:
            if material is UNSET:
                continue
            if self.compose not in {"replace", "override"}:
                raise ValueError(
                    "material properties support replace or override composition"
                )
            end = (
                start
                + duration
                + (material.release if isinstance(material, Envelope) else 0)
            )
            result.append(
                MaterialRule(
                    name,
                    material,
                    target.units,
                    "syllable" if target.kind == "segment" else target.kind,
                    target.segments,
                    (start, end),
                    event.window,
                    self.keep,
                    self.compose,
                    None if self.bounds is None else self.bounds.for_property(name),
                    self.rate,
                )
            )
        return tuple(result)


class Parallel:
    """Run Track event animation declarations simultaneously.

    Conflicting writes require a supported composition rule rather than implicit
    ordering.
    """

    def __init__(self, *animations: AnimationResult) -> None:
        if not animations:
            raise ValueError("Parallel requires at least one animation")
        self.animations = animations

    def _bind(
        self, event: AnimationEvent, offset: int = 0
    ) -> tuple[AnimationRule, ...]:
        return tuple(
            rule for action in self.animations for rule in action._bind(event, offset)
        )


class Sequence:
    """Run Track event animation declarations consecutively. Child durations and event-

    relative offsets determine the composed schedule.
    """

    def __init__(self, *animations: AnimationResult) -> None:
        if not animations:
            raise ValueError("Sequence requires at least one animation")
        self.animations = animations

    def _bind(
        self, event: AnimationEvent, offset: int = 0
    ) -> tuple[AnimationRule, ...]:
        result: list[AnimationRule] = []
        for action in self.animations:
            rules = action._bind(event, offset)
            result.extend(rules)
            endpoints = [rule.during[1] for rule in rules]
            if endpoints:
                if not all(isinstance(end, int) for end in endpoints):
                    raise ValueError("sequence requires concrete time intervals")
                offset = max(cast(int, end) for end in endpoints) - event.start
        return tuple(result)


type AnimationResult = Animate | Parallel | Sequence


class _EventHandler[A, E: AnimationEvent, R: AnimationResult]:
    def __init__(
        self,
        event_type: type[E],
        function: Callable[[A, E], R],
        where: SourceMatch | None,
    ) -> None:
        self.event_type, self.function, self.where = event_type, function, where

    @overload
    def __get__(self, instance: None, owner: type[A]) -> _EventHandler[A, E, R]: ...

    @overload
    def __get__(self, instance: A, owner: type[A]) -> Callable[[E], R]: ...

    def __get__(
        self, instance: A | None, owner: type[A]
    ) -> _EventHandler[A, E, R] | Callable[[E], R]:
        if instance is None:
            return self
        return lambda event: self.function(instance, event)

    def dispatch(
        self, owner: object, context: AnimationContext
    ) -> Iterator[AnimationResultWithEvent]:
        if self.where is not None and not self.where(context.item):
            return
        for event in context.events(self.event_type):
            assert isinstance(event, self.event_type)
            # Descriptors are read only from the owner's own MRO below.
            yield event, self.function(cast(A, owner), event)


type AnimationResultWithEvent = tuple[AnimationEvent, AnimationResult]


class _EventDecorator[E: AnimationEvent]:
    def __init__(self, event_type: type[E], where: SourceMatch | None) -> None:
        self.event_type, self.where = event_type, where

    def __call__[A, R: AnimationResult](
        self, function: Callable[[A, E], R]
    ) -> _EventHandler[A, E, R]:
        return _EventHandler(self.event_type, function, self.where)


def on[E: AnimationEvent](
    event_type: type[E], *, where: SourceMatch | None = None
) -> _EventDecorator[E]:
    """Declare a typed event handler on an Animation subclass.

    The handler receives the requested event type and returns supported animation
    declarations.
    """
    return _EventDecorator(event_type, where)


class Animation:
    """A reusable Track animation implemented by a typed sample function or @on event handlers.

    Sampled time and duration are seconds; event declarations are resolved to source
    targets before compilation.
    """

    def __init__(
        self,
        function: Callable[[float, AnimationContext], Transform] | None = None,
        *,
        duration: float | None = None,
        extend_display: bool = False,
        hold: bool = False,
    ) -> None:
        if duration is not None:
            _finite(duration, "animation duration")
            if duration <= 0:
                raise ValueError("animation duration must be positive")
        if type(hold) is not bool:
            raise TypeError("animation hold must be bool")
        if function is not None and not callable(function):
            raise TypeError("animation function must be callable")
        self.function = function
        self.duration = duration
        self.hold = hold
        if type(extend_display) is not bool:
            raise TypeError("extend_display must be bool")
        self.extend_display = extend_display

    def sample(self, t: float, context: AnimationContext) -> Transform:
        """Evaluate local seconds, independently of previously sampled frames.

        Without a function or override this raises NotImplementedError.
        Event-only animations use bind() instead.
        """
        if self.function is not None:
            return self.function(t, context)
        raise NotImplementedError("implement sample() or use event handlers")

    def actions(self, context: AnimationContext) -> Iterable[AnimationResultWithEvent]:
        """Yield typed event-bound declarations from this animation and its inherited handlers."""
        seen: set[str] = set()
        for cls in type(self).__mro__:
            for name, member in vars(cls).items():
                if name in seen:
                    continue
                seen.add(name)
                if isinstance(member, _EventHandler):
                    yield from member.dispatch(self, context)

    def bind(self, context: AnimationContext) -> tuple[AnimationRule, ...]:
        """Resolve this animation against the source context without changing the original lyric."""
        if type(self).sample is not Animation.sample or self.function is not None:
            from .choreography import bind_sampled

            return bind_sampled(self, context)
        rules = tuple(
            rule
            for event, result in self.actions(context)
            for rule in result._bind(event)
        )
        resolved: list[AnimationRule] = []
        for rule in rules:
            for unit in rule.units:
                if not 0 <= unit < len(context.item.source.units):
                    raise ValueError("animation target references a missing syllable")
            if rule.segments is not None:
                for unit, segment in rule.segments:
                    if not 0 <= segment < len(context.item.source.units[unit].segments):
                        raise ValueError(
                            "animation target references a missing segment"
                        )
            if rule.mode == "ruby":
                readings = tuple(
                    segment.ruby
                    for ui in rule.units
                    for si, segment in enumerate(context.item.source.units[ui].segments)
                    if rule.segments is None or (ui, si) in rule.segments
                )
                if not readings or not all(readings):
                    raise ValueError(
                        "animation target references a missing ruby reading"
                    )
            if (
                isinstance(rule, MotionRule)
                and isinstance(rule.value, Keyframes)
                and any(isinstance(frame.at, TimeRef) for frame in rule.value.frames)
            ):
                segments = tuple(
                    segment
                    for ui in rule.units
                    for si, segment in enumerate(context.item.source.units[ui].segments)
                    if rule.segments is None or (ui, si) in rule.segments
                )
                start, end = rule.during
                assert isinstance(start, int) and isinstance(end, int)
                points = rule.value.resolve((start, end), segments, context.item.window)
                # Freeze the original source clock before extend_display changes
                # output exposure or row occupancy. Keyframes remain unchanged.
                frames = Keyframes(
                    *(
                        Keyframe(
                            (at - start) / (end - start)
                            if end > start
                            else index / (len(points) - 1),
                            value,
                            rate,
                        )
                        for index, (at, value, rate) in enumerate(points)
                    )
                )
                rule = replace(rule, value=frames)
            resolved.append(rule)
        return tuple(resolved)


class On(Animation):
    """Bind an Animate, Sequence, or Parallel declaration to a selected Track event type.

    Optional source filtering and display extension are explicit.
    """

    def __init__(
        self,
        event: type[AnimationEvent],
        animation: AnimationResult | Animation,
        *,
        extend_display: bool = False,
    ) -> None:
        super().__init__(
            extend_display=extend_display
            or (isinstance(animation, Animation) and animation.extend_display)
        )
        self.event, self.animation = event, animation

    def bind(self, context: AnimationContext) -> tuple[AnimationRule, ...]:
        """Resolve the configured event declaration into Track motion and material rules."""
        animation = self.animation
        if isinstance(animation, Animation):
            return tuple(
                rule
                for event in context.events(self.event)
                for rule in animation.bind(replace(context, event=event))
            )
        return super().bind(context)

    def actions(self, context: AnimationContext) -> Iterable[AnimationResultWithEvent]:
        """Enumerate declarations for matching source events without changing the source clocks."""
        animation = self.animation
        if isinstance(animation, Animation):
            raise TypeError("sampled animations are resolved by bind()")
        return ((event, animation) for event in context.events(self.event))


class FadeInAnimation(On):
    """Fade a Track group from transparent to opaque after display start.

    duration is milliseconds and rate receives normalized progress.
    """

    def __init__(
        self, *, duration: Milliseconds = 400, rate: RateFunction = linear
    ) -> None:
        super().__init__(
            Display.Start, Animate(opacity=(0, 1), duration=duration, rate=rate)
        )


class FadeOutAnimation(On):
    """Fade a Track group to transparent ending at display end.

    duration is milliseconds and the declaration starts that duration before the
    end.
    """

    def __init__(
        self, *, duration: Milliseconds = 200, rate: RateFunction = linear
    ) -> None:
        super().__init__(
            Display.End,
            Animate(opacity=(1, 0), duration=duration, offset=-duration, rate=rate),
        )


class SingingPulseAnimation(Animation):
    """Apply a syllable scale envelope around singing with millisecond attack/release and configurable rise/fall rates.

    Optional extension affects display, not original singing time.
    """

    def __init__(
        self,
        *,
        peak: float = 1.1,
        attack: Milliseconds = 80,
        release: Milliseconds = 160,
        rise: RateFunction = linear,
        fall: RateFunction = linear,
        extend_display: bool = False,
    ) -> None:
        super().__init__(extend_display=extend_display)
        self.envelope = Envelope(
            peak=peak, attack=attack, release=release, rise=rise, fall=fall
        )

    @on(Syllable.Singing)
    def pulse(self, event: Syllable.Singing) -> Animate:
        return Animate(event.target, scale=self.envelope)


class HighlightAnimation(Animation):
    """Animate drawable characters at a highlight or syllable trigger.

    ``trigger`` controls threshold, duration in milliseconds, and retriggering.
    Properties receive normalized progress, including traversal across pauses.
    With no properties, apply a scale pulse using ``trigger.scale``. Optional
    ranges select source text; layout validates their drawable cluster bounds.
    """

    def __init__(
        self,
        *,
        trigger: Pulse = _DEFAULT_HIGHLIGHT,
        ranges: tuple[TextRange, ...] | None = None,
        keep: bool = False,
        compose: CompositionMode = "replace",
        scale: PropertyValue | _Unset = UNSET,
        opacity: PropertyValue | _Unset = UNSET,
        offset_x: PropertyValue | _Unset = UNSET,
        offset_y: PropertyValue | _Unset = UNSET,
    ) -> None:
        super().__init__()
        if trigger.target == "syllable":
            raise ValueError(
                "HighlightAnimation targets characters; use SingingPulseAnimation for syllables"
            )
        self.trigger = trigger
        self.ranges = ranges
        values: AnimatedProperties = {}
        if scale is not UNSET:
            values["scale"] = scale
        if opacity is not UNSET:
            values["opacity"] = opacity
        if offset_x is not UNSET:
            values["offset_x"] = offset_x
        if offset_y is not UNSET:
            values["offset_y"] = offset_y
        if not values:
            values["scale"] = Transition(1, trigger.scale, rate=there_and_back)
        # Validate declarations before binding to a specific lyric.
        self.rules = declare_properties(
            values,
            during=(singing.start, singing.end),
            mode="character",
            ranges=ranges,
            arrival=trigger,
            keep=keep,
            compose=compose,
        )

    def bind(self, context: AnimationContext) -> tuple[AnimationRule, ...]:
        """Bind character rules without measuring text or evaluating callbacks."""
        units = tuple(range(len(context.item.source.units)))
        return tuple(replace(rule, units=units) for rule in self.rules)
