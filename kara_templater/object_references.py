"""Explicit, pure world-state dependencies for scene objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from .geometry import Vec2, finite
from .scene_animation import CHANNELS, Channel, VisualState

type StateLookup = Callable[[str, float], VisualState]


class StateReference(Protocol):
    """Protocol for seekable state relationships evaluated through a world-state lookup.

    Declare dependencies and channels so references can be ordered and checked for
    cycles.
    """

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Object identities that the world-state evaluator must resolve first."""
        ...

    @property
    def channels(self) -> frozenset[Channel]:
        """The state channels this reference may change."""
        ...

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Declared seconds boundaries used when sampling dependent objects."""
        ...

    def sample(
        self, base: VisualState, time: float, lookup: StateLookup
    ) -> VisualState:
        """Evaluate a pure state relationship using the supplied world-state lookup."""
        ...

    def shifted(self, seconds: float) -> StateReference:
        """Return a reference with a seconds clock shift for delayed copying."""
        ...

    def translated(self, offset: Vec2) -> StateReference:
        """Return a reference adjusted for a spatial translation."""
        ...

    def retarget(
        self, names: Mapping[str, str], time_shift: float = 0
    ) -> StateReference:
        """Remap dependencies and delay for a copied object hierarchy."""
        ...


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
        """The source object IDs required for world-state evaluation."""
        return (self.target,)

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Declared time boundaries that must be considered while sampling this reference."""
        return ()

    def sample(
        self, base: VisualState, time: float, lookup: StateLookup
    ) -> VisualState:
        """Resolve the followed object through the supplied world-state lookup and apply the requested relationship."""
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
        """Return a reference with its coordinate offset translated for object copying."""
        return (
            replace(self, offset=self.offset + offset)
            if "position" in self.channels
            else self
        )

    def shifted(self, seconds: float) -> FollowObject:
        """Return a reference with its time relationship shifted by a seconds delay."""
        return replace(self, delay=self.delay + seconds)

    def retarget(self, names: Mapping[str, str], time_shift: float = 0) -> FollowObject:
        """Remap dependency IDs and time shifts when copying a referenced hierarchy."""
        return replace(
            self,
            target=names.get(self.target, self.target),
            delay=self.delay - time_shift if self.target in names else self.delay,
        )


@dataclass(frozen=True)
class ReferenceFunction:
    """A pure world-state callback with explicit dependency IDs, written channels, and second-based breakpoints.

    Retargeting and clock translation support copied groups.
    """

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
        """Evaluate the pure reference callback with the incoming state, seconds time, and world-state lookup."""
        return self.function(base, time, lookup)

    def translated(self, offset: Vec2) -> ReferenceFunction:
        """Return a reference adjusted for a spatial translation."""
        if offset == Vec2() or "position" not in self.channels:
            return self

        def sample(base: VisualState, time: float, lookup: StateLookup) -> VisualState:
            value = self.sample(base, time, lookup)
            return replace(value, position=value.position + offset)

        return replace(self, function=sample)

    def shifted(self, seconds: float) -> ReferenceFunction:
        """Return a reference adjusted for a seconds clock shift."""
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
        """Remap dependency identities and delay when copying a group."""
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
