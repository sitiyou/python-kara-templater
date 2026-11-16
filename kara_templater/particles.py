"""Bounded particle factories and historical copies of ordinary scene objects."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Protocol

from .geometry import Vec2, finite
from .object_references import (
    FollowObject,
    ReferenceFunction,
    StateLookup,
    StateReference,
)
from .path_geometry import intersect_convex, path_bounds
from .scene import ObjectGroup, PathObject, SceneObject
from .scene_animation import (
    CHANNELS,
    AnimationClip,
    Channel,
    StateFunction,
    VisualState,
)
from .sources import EventOrigin


@dataclass(frozen=True)
class Emission:
    """A stable particle emission ID and nonnegative absolute birth time in seconds.

    Reordering a schedule does not change keyed random values for an existing ID.
    """

    id: str
    birth: float

    def __post_init__(self) -> None:
        finite(self.birth)
        if not self.id or self.birth < 0:
            raise ValueError("emissions need a nonempty id and nonnegative birth time")


@dataclass(frozen=True)
class ParticleContext:
    """Particle factory input with birth, seed, source position, optional origin, and named random channels.

    position_at samples an emitter explicitly; it does not imply continuous
    following.
    """

    id: str
    birth: float
    seed: int
    position: Vec2
    origin: EventOrigin | None
    emitter: Callable[[float], Vec2] | None = None

    def uniform(self, key: str, minimum: float = 0, maximum: float = 1) -> float:
        """Stable keyed random value, independent of access and generation order."""
        finite(minimum, maximum)
        if maximum < minimum:
            raise ValueError("random interval is reversed")
        # Length prefixes distinguish keys containing separators or Unicode.
        fields = (str(self.seed), self.id, key)
        encoded = b"".join(
            len(part.encode()).to_bytes(8, "big") + part.encode() for part in fields
        )
        number = int.from_bytes(sha256(encoded).digest()[:8], "big") >> 11
        return minimum + (maximum - minimum) * (number / (1 << 53))

    def choose[T](self, key: str, values: tuple[T, ...]) -> T:
        """Select deterministically from values using a named random channel."""
        if not values:
            raise ValueError("random choice requires a nonempty tuple")
        return values[min(len(values) - 1, int(self.uniform(key) * len(values)))]

    def position_at(self, age: float) -> Vec2:
        """Continuously follow the emitter; position itself is its birth capture."""
        finite(age)
        return self.position if self.emitter is None else self.emitter(self.birth + age)


class ParticleFactory(Protocol):
    """A callable producing a normal Scene object or group from ParticleContext.

    The factory controls its own geometry, animation, and lifetime.
    """

    def __call__(self, context: ParticleContext, /) -> SceneObject:
        """Create one Scene object or group preserving the context ID and birth time."""
        ...


def _stamp(node: SceneObject, origin: EventOrigin | None) -> SceneObject:
    if isinstance(node, ObjectGroup):
        return replace(
            node,
            origin=node.origin or origin,
            children=tuple(_stamp(child, origin) for child in node.children),
        )
    return replace(node, origin=node.origin or origin)


def emit_particles(
    emissions: Iterable[Emission],
    factory: ParticleFactory,
    *,
    id: str = "particles",
    seed: int = 0,
    emitter: Callable[[float], Vec2] | None = None,
    origin: EventOrigin | None = None,
    max_particles: int = 1000,
) -> tuple[SceneObject, ...]:
    """Validate the finite schedule before calling factories or the emitter.

    A stable emission id owns its random stream. Reordering or adding unrelated
    emissions doesn't change existing particles. Each factory controls geometry,
    state, animation and lifespan through the same normal scene object interface.
    """
    if (
        not id
        or type(seed) is not int
        or type(max_particles) is not int
        or max_particles < 1
    ):
        raise ValueError(
            "particles require an id, integer seed and positive count budget"
        )
    schedule: list[Emission] = []
    identities: set[str] = set()
    for emission in emissions:
        if len(schedule) >= max_particles:
            raise ValueError(
                "particle generation budget exceeded before factory execution"
            )
        if emission.id in identities:
            raise ValueError(f"duplicate emission id: {emission.id!r}")
        identities.add(emission.id)
        schedule.append(emission)
    objects: list[SceneObject] = []
    for emission in schedule:
        context = ParticleContext(
            f"{id}/{emission.id}",
            emission.birth,
            seed,
            Vec2() if emitter is None else emitter(emission.birth),
            origin,
            emitter,
        )
        node = factory(context)
        if node.id != context.id or node.lifetime.start != emission.birth:
            raise ValueError(
                f"particle {context.id}: factory must preserve id and birth time"
            )
        objects.append(_stamp(node, origin))
    return tuple(objects)


def echoes[T: SceneObject](
    source: T,
    *,
    count: int = 4,
    spacing: float = 0.06,
    opacity: float = 0.4,
    decay: float = 0.7,
    layer_step: int = -1,
    max_objects: int = 1000,
) -> tuple[T, ...]:
    """Historical copies of complete animation/geometry, each with independent life.

    Group copies delay their descendants and parent transforms together. Opacity
    remains the library's per-child inherited opacity, not offscreen compositing.
    """
    finite(spacing, opacity, decay)
    if (
        type(count) is not int
        or count < 0
        or spacing <= 0
        or not 0 <= opacity <= 1
        or not 0 <= decay <= 1
    ):
        raise ValueError(
            "echo count must be nonnegative, spacing positive, opacity/decay in 0..1"
        )
    if type(layer_step) is not int or type(max_objects) is not int or max_objects < 1:
        raise ValueError("echo layer step must be integer and object budget positive")
    if count == 0:
        return ()
    seen: set[str] = set()

    def size(node: SceneObject) -> int:
        if node.id in seen:
            raise ValueError("echo source has duplicate identities or a group cycle")
        seen.add(node.id)
        if len(seen) > max_objects:
            raise ValueError("echo object budget exceeded")
        return (
            1 + sum(size(child) for child in node.children)
            if isinstance(node, ObjectGroup)
            else 1
        )

    if count * size(source) > max_objects:
        raise ValueError("echo object budget exceeded before copying")
    duration = source.lifetime.end - source.lifetime.start
    breaks = tuple(
        sorted(
            {
                t + source.time_origin - source.lifetime.start
                for clip in source.animations
                for t in (
                    clip.start,
                    clip.end,
                    *(clip.start + b for b in clip.breakpoints),
                )
                if source.lifetime.start
                <= source.time_origin + t
                <= source.lifetime.end
            }
        )
    )
    channels: frozenset[Channel] = (
        frozenset(("position", "scale", "rotation", "opacity"))
        if isinstance(source, ObjectGroup)
        else CHANNELS
    )
    if source.reference is not None:
        channels = channels - source.reference.channels
    copies: list[T] = []
    for index in range(count):
        factor = opacity * decay**index

        def history(
            base: VisualState, progress: float, multiplier: float = factor
        ) -> VisualState:
            state = source.at(source.lifetime.start + progress * duration)
            state = replace(state, opacity=state.opacity * multiplier)
            return replace(
                base, **{channel: getattr(state, channel) for channel in channels}
            )

        node = source.copy(
            id=f"{source.id}/echo:{index + 1}", delay=(index + 1) * spacing
        )
        reference = node.reference
        if reference is not None and "opacity" in reference.channels:
            if isinstance(reference, FollowObject):
                reference = replace(
                    reference, opacity_factor=reference.opacity_factor * factor
                )
            else:

                def dim(
                    base: VisualState,
                    time: float,
                    lookup: StateLookup,
                    ref: StateReference = reference,
                    alpha: float = factor,
                ) -> VisualState:
                    value = ref.sample(base, time, lookup)
                    return replace(value, opacity=value.opacity * alpha)

                reference = ReferenceFunction(
                    dim,
                    reference.dependencies,
                    reference.channels,
                    reference.breakpoints,
                )
        copies.append(
            replace(
                node,
                reference=reference,
                layer=source.layer + (index + 1) * layer_step,
                animations=(
                    AnimationClip(
                        source.lifetime.start - source.time_origin,
                        duration,
                        StateFunction(history, channels),
                        breakpoints=breaks,
                    ),
                )
                if channels
                else (),
            )
        )
    return tuple(copies)


def split_path(
    source: PathObject,
    *,
    columns: int,
    rows: int,
    tolerance: float = 0.25,
    max_fragments: int = 256,
    max_points: int = 4096,
) -> tuple[PathObject, ...]:
    """Cut static filled geometry into local grid cells, retaining object origin.

    Pieces move with their own geometry, not fixed screen-space clips. Appearance
    is preserved, so borders will also outline newly cut edges. Separate raster
    edges can show seams; use the uncut object for the final assembled hold.
    """
    if any(
        type(value) is not int or value < 1 for value in (columns, rows, max_fragments)
    ):
        raise ValueError("fragment dimensions and budget must be positive integers")
    if columns * rows > max_fragments:
        raise ValueError("fragment generation budget exceeded before subdivision")
    if source.deform is not None:
        raise ValueError("split_path requires static source geometry")
    if (
        type(max_points) is not int
        or max_points < 2
        or source.path.point_count > max_points
    ):
        raise ValueError("fragment source point budget exceeded")
    box = path_bounds(source.path)
    if box.width <= 0 or box.height <= 0:
        raise ValueError("cannot fragment a path with empty area bounds")
    result: list[PathObject] = []
    for row in range(rows):
        for column in range(columns):
            left = box.left + box.width * column / columns
            right = box.left + box.width * (column + 1) / columns
            top = box.top + box.height * row / rows
            bottom = box.top + box.height * (row + 1) / rows
            cut = intersect_convex(
                source.path,
                (
                    Vec2(left, top),
                    Vec2(right, top),
                    Vec2(right, bottom),
                    Vec2(left, bottom),
                ),
                tolerance=tolerance,
                max_points=max_points,
            )
            if cut is not None:
                result.append(
                    replace(source, id=f"{source.id}/cell:{row}:{column}", path=cut)
                )
    return tuple(result)
