"""Explicit, pure world-state dependencies for scene objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from .geometry import Vec2, finite
from .scene_animation import CHANNELS, Channel, VisualState

type StateLookup = Callable[[str, float], VisualState]


class StateReference(Protocol):
    @property
    def dependencies(self) -> tuple[str, ...]: ...
    @property
    def channels(self) -> frozenset[Channel]: ...
    @property
    def breakpoints(self) -> tuple[float, ...]: ...
    def sample(
        self, base: VisualState, time: float, lookup: StateLookup
    ) -> VisualState: ...
    def shifted(self, seconds: float) -> StateReference: ...
    def translated(self, offset: Vec2) -> StateReference: ...
    def retarget(
        self, names: Mapping[str, str], time_shift: float = 0
    ) -> StateReference: ...


@dataclass(frozen=True)
class FollowObject:
    """Replace selected world channels with a target's state at time-delay.

    offset is a screen-space position offset, independent of target rotation.
    The target state clamps to its own lifetime at the evaluator boundary.
    """

    target: str
    offset: Vec2 = Vec2()
    delay: float = 0
    opacity_factor: float = 1
    channels: frozenset[Channel] = frozenset(("position",))

    def __post_init__(self) -> None:
        finite(self.delay, self.opacity_factor)
        if not 0 <= self.opacity_factor <= 1:
            raise ValueError("follow opacity factor must be in 0..1")
        if not self.target or not self.channels or not self.channels <= CHANNELS:
            raise ValueError("follow needs a target and valid channels")

    @property
    def dependencies(self) -> tuple[str, ...]:
        return (self.target,)

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return ()

    def sample(
        self, base: VisualState, time: float, lookup: StateLookup
    ) -> VisualState:
        target = lookup(self.target, time - self.delay)
        return replace(
            base,
            **{
                channel: getattr(target, channel) + self.offset
                if channel == "position"
                else getattr(target, channel) * self.opacity_factor
                if channel == "opacity"
                else getattr(target, channel)
                for channel in self.channels
            },
        )

    def translated(self, offset: Vec2) -> FollowObject:
        return (
            replace(self, offset=self.offset + offset)
            if "position" in self.channels
            else self
        )

    def shifted(self, seconds: float) -> FollowObject:
        return replace(self, delay=self.delay + seconds)

    def retarget(self, names: Mapping[str, str], time_shift: float = 0) -> FollowObject:
        return replace(
            self,
            target=names.get(self.target, self.target),
            delay=self.delay - time_shift if self.target in names else self.delay,
        )


@dataclass(frozen=True)
class ReferenceFunction:
    function: Callable[[VisualState, float, StateLookup], VisualState]
    dependencies: tuple[str, ...]
    channels: frozenset[Channel]
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(*self.breakpoints)
        if (
            not self.dependencies
            or len(set(self.dependencies)) != len(self.dependencies)
            or any(not value for value in self.dependencies)
        ):
            raise ValueError("reference dependencies must be nonempty and unique")
        if not self.channels or not self.channels <= CHANNELS:
            raise ValueError("reference needs valid output channels")

    def sample(
        self, base: VisualState, time: float, lookup: StateLookup
    ) -> VisualState:
        return self.function(base, time, lookup)

    def translated(self, offset: Vec2) -> ReferenceFunction:
        if offset == Vec2() or "position" not in self.channels:
            return self

        def sample(base: VisualState, time: float, lookup: StateLookup) -> VisualState:
            value = self.sample(base, time, lookup)
            return replace(value, position=value.position + offset)

        return replace(self, function=sample)

    def shifted(self, seconds: float) -> ReferenceFunction:
        if seconds == 0:
            return self
        return replace(
            self,
            function=lambda base, time, lookup: self.sample(
                base, time - seconds, lookup
            ),
            breakpoints=tuple(t + seconds for t in self.breakpoints),
        )

    def retarget(
        self, names: Mapping[str, str], time_shift: float = 0
    ) -> ReferenceFunction:
        mapping = dict(names)

        def sample(base: VisualState, time: float, lookup: StateLookup) -> VisualState:
            return self.sample(
                base,
                time,
                lambda name, t: lookup(
                    mapping.get(name, name), t + time_shift if name in mapping else t
                ),
            )

        return replace(
            self,
            function=sample,
            dependencies=tuple(mapping.get(name, name) for name in self.dependencies),
        )
