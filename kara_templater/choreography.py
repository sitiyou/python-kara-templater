"""Seekable animations and declarative timelines, using seconds at the boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from .motion import (
    Animate,
    Animation,
    AnimationContext,
    AnimationRule,
    RateFunction,
    Syllable,
    TimeSpan,
    Transform,
)
from .properties import Keyframe, Keyframes, linear
from .stylesheet import UNSET
from .timeline import _finite


def _seconds(value: float, label: str, *, positive: bool = False) -> float:
    _finite(value, label)
    result = round(value * 1000) / 1000
    if value < 0 or (positive and result <= 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'}")
    return result


def _transform(values: dict[str, float]) -> Transform:
    return Transform(
        scale=values.get("scale"),
        opacity=values.get("opacity"),
        offset_x=values.get("offset_x"),
        offset_y=values.get("offset_y"),
    )


class Timeline:
    """Record simultaneous plays at explicit local times, or after the cursor."""

    def __init__(self, context: AnimationContext) -> None:
        self._context = context
        self._ancestors: tuple[int, ...] = ()
        self._recordings: list[tuple[float, _Recording]] = []
        self._cursor = 0.0

    def play(
        self,
        *animations: Animation,
        at: float | None = None,
        during: TimeSpan | None = None,
        duration: float | None = None,
    ) -> None:
        """Schedule composed animations at local seconds or during an explicit TimeSpan.

        Omitted start uses the composition cursor.
        """
        if not animations:
            raise ValueError("play requires at least one animation")
        if any(not isinstance(animation, Animation) for animation in animations):
            raise TypeError("play accepts Animation instances")
        if at is not None and during is not None:
            raise ValueError("use only one of at or during")
        if during is not None and duration is not None:
            raise ValueError("during already defines duration")
        if during is not None:
            start, duration = during.start, during.duration
        else:
            start = self._cursor if at is None else at
        start = _seconds(start, "animation start")
        if duration is not None:
            duration = _seconds(duration, "play duration", positive=True)
        self._cursor = start
        for animation in animations:
            child = _record(
                animation,
                replace(self._context, origin=self._context.origin + start),
                duration,
                self._ancestors,
            )
            self._recordings.append((start, child))
            self._cursor = max(self._cursor, start + child.duration)


@dataclass(frozen=True)
class _Clip:
    start: float
    duration: float
    channels: frozenset[str]
    evaluate: Callable[[float], Transform]
    hold: bool
    first_writes: dict[str, float]

    def value(self, t: float) -> Transform:
        return self.evaluate(min(max(round(t - self.start, 12), 0.0), self.duration))


def _state(
    clips: list[_Clip], t: float, initial: Transform, *, include_end: bool = False
) -> Transform:
    t = round(t, 12)
    values = initial.values()
    # Later starts take ownership per channel. Completed non-held clips release
    # to the base, not to an earlier animation which they have already replaced.
    owners: dict[str, _Clip] = {}
    for clip in clips:
        if clip.start <= t:
            for channel in clip.channels:
                owners[channel] = clip
    for channel, clip in owners.items():
        if (
            clip.hold
            or t < round(clip.start + clip.duration, 12)
            or (include_end and t == round(clip.start + clip.duration, 12))
        ):
            values[channel] = clip.value(t).values()[channel]
    return _transform(values)


class Composition(Animation):
    """An animation built by recording child animations on a local timeline."""

    def __init__(
        self,
        builder: Callable[[Timeline, AnimationContext], None] | None = None,
        *,
        extend_display: bool = False,
        hold: bool = True,
    ) -> None:
        if builder is not None and not callable(builder):
            raise TypeError("composition builder must be callable")
        super().__init__(extend_display=extend_display, hold=hold)
        self.builder = builder

    def compose(self, timeline: Timeline, context: AnimationContext) -> None:
        """Override to schedule seconds-based child animations on the supplied Timeline."""
        if self.builder is None:
            raise NotImplementedError("implement compose() or supply a builder")
        self.builder(timeline, context)

    def sample(self, t: float, context: AnimationContext) -> Transform:
        """Evaluate this composition at local seconds and return a sparse Transform."""
        record = _record(self, context)
        return _prepare(record, context).value(t)

    def bind(self, context: AnimationContext) -> tuple[AnimationRule, ...]:
        """Resolve the composed schedule into Track property declarations with source-local timing."""
        return bind_sampled(self, context)


class TransformTo(Animation):
    """Interpolate only the supplied properties from the state at this start."""

    def __init__(
        self,
        transform: Transform,
        *,
        duration: float | None = None,
        rate: RateFunction = linear,
    ) -> None:
        if not transform.values():
            raise ValueError("TransformTo requires at least one property")
        if not callable(rate):
            raise TypeError("rate must be callable")
        super().__init__(duration=duration, hold=True)
        self.transform, self.rate = transform, rate

    def sample(self, t: float, context: AnimationContext) -> Transform:
        """Interpolate the configured sparse geometry target at local seconds."""
        progress = self.rate(t / context.duration)
        _finite(progress, "animation rate result")
        initial = context.initial.values()
        return _transform(
            {
                name: initial[name] + (end - initial[name]) * progress
                for name, end in self.transform.values().items()
            }
        )


class ScaleTo(TransformTo):
    """A seconds-based composition transition to a target uniform scale.

    The enclosing Timeline determines its start and duration.
    """

    def __init__(
        self,
        scale: float,
        *,
        duration: float | None = None,
        rate: RateFunction = linear,
    ) -> None:
        super().__init__(Transform(scale=scale), duration=duration, rate=rate)


class OpacityTo(TransformTo):
    """A seconds-based composition transition to a target opacity.

    Use it with Timeline.play and a duration or TimeSpan.
    """

    def __init__(
        self,
        opacity: float,
        *,
        duration: float | None = None,
        rate: RateFunction = linear,
    ) -> None:
        super().__init__(Transform(opacity=opacity), duration=duration, rate=rate)


class MoveTo(TransformTo):
    """Offsets in layout pixels, relative to the unanimated target."""

    def __init__(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        duration: float | None = None,
        rate: RateFunction = linear,
    ) -> None:
        super().__init__(
            Transform(offset_x=x, offset_y=y),
            duration=duration,
            rate=rate,
        )


@dataclass(frozen=True)
class _Recording:
    animation: Animation
    duration: float
    children: tuple[tuple[float, _Recording], ...] = ()


def _record(
    animation: Animation,
    context: AnimationContext,
    duration: float | None = None,
    ancestors: tuple[int, ...] = (),
) -> _Recording:
    if id(animation) in ancestors:
        raise ValueError("recursive animation composition")
    if not isinstance(animation, Composition):
        if type(animation).sample is Animation.sample and animation.function is None:
            raise TypeError("timeline children must implement sample() or compose()")
        resolved = duration if duration is not None else animation.duration
        resolved = context.duration if resolved is None else resolved
        return _Recording(
            animation, _seconds(resolved, "animation duration", positive=True)
        )
    timeline = Timeline(context)
    timeline._ancestors = (*ancestors, id(animation))
    animation.compose(timeline, context)
    if not timeline._recordings:
        raise ValueError("composition must contain at least one play")
    natural = max(start + child.duration for start, child in timeline._recordings)
    if duration is not None:
        # Time stretching also stretches gaps and descendant timelines uniformly.
        factor = duration / natural
        children = tuple(
            (start * factor, _stretch(child, factor))
            for start, child in timeline._recordings
        )
        return _Recording(animation, duration, children)
    return _Recording(animation, natural, tuple(timeline._recordings))


def _stretch(recording: _Recording, factor: float) -> _Recording:
    return _Recording(
        recording.animation,
        recording.duration * factor,
        tuple(
            (start * factor, _stretch(child, factor))
            for start, child in recording.children
        ),
    )


def _prepare(record: _Recording, context: AnimationContext, start: float = 0) -> _Clip:
    context = replace(context, duration=record.duration)
    if record.children:
        clips: list[_Clip] = []
        for child_start, child in sorted(record.children, key=lambda entry: entry[0]):
            initial = _state(clips, child_start, context.initial, include_end=True)
            clip = _prepare(
                child,
                replace(context, initial=initial, origin=context.origin + child_start),
                child_start,
            )
            for previous in clips:
                if previous.start == clip.start and previous.channels & clip.channels:
                    channels = ", ".join(sorted(previous.channels & clip.channels))
                    raise ValueError(
                        f"simultaneous animation writes at {clip.start}s: {channels}"
                    )
            clips.append(clip)
        channels = frozenset(channel for clip in clips for channel in clip.channels)
        first_writes = {
            channel: min(clip.start for clip in clips if channel in clip.channels)
            for channel in channels
        }

        def evaluate(t: float) -> Transform:
            state = _state(clips, t, context.initial, include_end=t == record.duration)
            return _transform(
                {key: value for key, value in state.values().items() if key in channels}
            )

    else:
        first = record.animation.sample(0, context)
        channels = frozenset(first.values())
        first_writes = dict.fromkeys(channels, 0.0)
        if not channels:
            raise ValueError("sample() must return a nonempty, fixed set of properties")

        def evaluate(t: float) -> Transform:
            result = record.animation.sample(t, context)
            if frozenset(result.values()) != channels:
                raise ValueError(
                    "sample() must write the same properties at every time"
                )
            return result

    return _Clip(
        round(start, 12),
        record.duration,
        channels,
        evaluate,
        record.animation.hold,
        first_writes,
    )


def _schedule_times(record: _Recording) -> set[float]:
    times = {0.0, record.duration}
    for start, child in record.children:
        times.update(start + t for t in _schedule_times(child))
    return {min(max(t, 0), record.duration) for t in times}


def _linear_times(record: _Recording) -> set[float] | None:
    """Retain exact native keyframes for built-in linear timelines."""
    if not record.children:
        if type(record.animation) in {TransformTo, ScaleTo, OpacityTo, MoveTo}:
            assert isinstance(record.animation, TransformTo)
            if record.animation.rate is linear:
                return {0.0, record.duration}
        return None
    times = {0.0, record.duration}
    for start, child in record.children:
        child_times = _linear_times(child)
        if child_times is None or not child.animation.hold:
            return None
        times.update(start + t for t in child_times)
    return times


def bind_sampled(
    animation: Animation, context: AnimationContext
) -> tuple[AnimationRule, ...]:
    rules: list[AnimationRule] = []
    events = (
        (context.event,)
        if context.event is not None
        else context.events(Syllable.Singing)
    )
    for event in events:
        local = replace(
            context,
            event=event,
            origin=event.start / 1000,
            duration=(event.end - event.start) / 1000,
        )
        record = _record(animation, local)
        clip = _prepare(record, local)
        duration_ms = round(record.duration * 1000)
        if duration_ms <= 0:
            raise ValueError("animation duration must span at least one millisecond")

        # Trim each writer to its first scheduled start so independent Track
        # animations do not conflict with a composition's initial idle period.
        times = _linear_times(record)
        for name in sorted(clip.channels):
            first = clip.first_writes[name]
            start_ms = round(first * 1000)
            value = _property_value(name, clip, times, first)
            action = Animate(
                event.target,
                scale=value if name == "scale" else UNSET,
                opacity=value if name == "opacity" else UNSET,
                offset_x=value if name == "offset_x" else UNSET,
                offset_y=value if name == "offset_y" else UNSET,
                duration=duration_ms - start_ms,
                offset=start_ms,
                keep=animation.hold,
            )
            breakpoints = tuple(
                sorted(
                    {
                        event.start + round(t * 1000)
                        for t in _schedule_times(record)
                        if t >= first
                    }
                )
            )
            rules.extend(
                replace(rule, breakpoints=breakpoints) for rule in action._bind(event)
            )
    return tuple(rules)


def _property_value(
    name: str,
    bound: _Clip,
    times: set[float] | None,
    start: float,
) -> Callable[[float], float] | Keyframes:
    duration = bound.duration - start
    if times is not None:
        return Keyframes(
            *(
                Keyframe((t - start) / duration, bound.evaluate(t).values()[name])
                for t in sorted(times | {start})
                if t >= start
            )
        )
    return lambda progress: bound.evaluate(start + progress * duration).values()[name]
