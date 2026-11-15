"""Validated dependency graph and seekable world-state evaluation."""

from dataclasses import replace
from math import atan2, degrees, hypot

from .geometry import Vec2, finite
from .object_references import FollowObject
from .scene import NativeEvent, ObjectGroup, Scene, SceneObject
from .scene_animation import CHANNELS, VisualState
from .sources import EventOrigin


class SceneReferenceError(ValueError):
    def __init__(
        self, message: str, *, object_id: str, origin: EventOrigin | None = None
    ) -> None:
        super().__init__(f"{object_id}: {message}")
        self.object_id = object_id
        self.origin = origin


def compose_states(parent: VisualState, child: VisualState) -> VisualState:
    position = parent.transform.apply(child.position)
    # Preserve the existing decomposed channels when no shear is introduced.
    if (
        parent.skew == Vec2()
        and child.skew == Vec2()
        and (parent.scale.x == parent.scale.y or child.rotation == 0)
    ):
        return replace(
            child,
            position=position,
            scale=Vec2(child.scale.x * parent.scale.x, child.scale.y * parent.scale.y),
            rotation=child.rotation + parent.rotation,
            opacity=child.opacity * parent.opacity,
        )
    matrix = parent.transform @ child.transform
    sx = hypot(matrix.a, matrix.b)
    if sx == 0:
        # The first basis vector has collapsed. Align the surviving y basis
        # without inventing a shear or dividing by its missing x scale.
        sy = hypot(matrix.c, matrix.d)
        return replace(
            child,
            position=position,
            scale=Vec2(0, sy),
            rotation=degrees(atan2(-matrix.c, matrix.d)) if sy else 0,
            skew=Vec2(),
            opacity=child.opacity * parent.opacity,
        )
    ux, uy = matrix.a / sx, matrix.b / sx
    return replace(
        child,
        position=position,
        scale=Vec2(
            sx,
            0 if parent.singular or child.singular else ux * matrix.d - uy * matrix.c,
        ),
        rotation=degrees(atan2(matrix.b, matrix.a)),
        skew=Vec2((ux * matrix.c + uy * matrix.d) / sx, 0),
        opacity=child.opacity * parent.opacity,
    )


class SceneEvaluator:
    """Immutable object snapshot; no previous-frame state or cross-call cache."""

    def __init__(self, scene: Scene) -> None:
        self._nodes: dict[str, SceneObject] = {}
        self._parents: dict[str, str] = {}
        seen: set[str] = set()

        def visit(node: SceneObject | NativeEvent, parent: str | None) -> None:
            if node.id in seen:
                raise SceneReferenceError(
                    "duplicate object identity or group cycle", object_id=node.id
                )
            seen.add(node.id)
            if isinstance(node, NativeEvent):
                return
            self._nodes[node.id] = node
            if parent is not None:
                self._parents[node.id] = parent
            if isinstance(node, ObjectGroup):
                for child in node.children:
                    visit(child, node.id)

        for node in scene.objects:
            visit(node, None)
        self._declared = {
            name: frozenset(node.reference.dependencies)
            for name, node in self._nodes.items()
            if node.reference is not None
        }
        self._writable = {
            name: frozenset(node.reference.channels)
            for name, node in self._nodes.items()
            if node.reference is not None
        }
        edges: dict[str, set[str]] = {}
        for name, node in self._nodes.items():
            dependencies = set(
                node.reference.dependencies if node.reference is not None else ()
            )
            if name in self._parents:
                dependencies.add(self._parents[name])
            for dependency in dependencies:
                if dependency not in self._nodes:
                    raise SceneReferenceError(
                        f"missing visual dependency {dependency!r}",
                        object_id=name,
                        origin=node.origin,
                    )
            edges[name] = dependencies
        remaining = {name: set(deps) for name, deps in edges.items()}
        self._order: list[str] = []
        while remaining:
            ready = [name for name, deps in remaining.items() if not deps]
            if not ready:
                name = next(iter(remaining))
                raise SceneReferenceError(
                    "dependency cycle: " + ", ".join(remaining),
                    object_id=name,
                    origin=self._nodes[name].origin,
                )
            self._order.extend(ready)
            for name in ready:
                del remaining[name]
            completed = set(ready)
            for dependencies in remaining.values():
                dependencies.difference_update(completed)
        self._breaks: dict[str, tuple[float, ...]] = {}
        self._dependent: dict[str, bool] = {}
        for name in self._order:
            node = self._nodes[name]
            points = {node.lifetime.start, node.lifetime.end}
            for clip in node.animations:
                points.update(
                    node.lifetime.start + t
                    for t in (
                        clip.start,
                        clip.end,
                        *(clip.start + t for t in clip.breakpoints),
                    )
                )
            if name in self._parents:
                points.update(self._breaks[self._parents[name]])
            reference = node.reference
            if reference is not None:
                points.update(reference.breakpoints)
                if isinstance(reference, FollowObject):
                    points.update(
                        t + reference.delay for t in self._breaks[reference.target]
                    )
            self._breaks[name] = tuple(sorted(points))
            self._dependent[name] = reference is not None or (
                name in self._parents and self._dependent[self._parents[name]]
            )

    def referenced(self, name: str) -> bool:
        return self._dependent[name]

    def breakpoints(self, name: str) -> tuple[float, ...]:
        return self._breaks[name]

    def at(self, name: str, time: float) -> VisualState:
        finite(time)
        cache: dict[tuple[str, float], VisualState] = {}

        def evaluate(identity: str, requested: float) -> VisualState:
            finite(requested)
            if identity not in self._nodes:
                raise SceneReferenceError("unknown visual object", object_id=identity)
            node = self._nodes[identity]
            t = max(node.lifetime.start, min(node.lifetime.end, requested))
            key = (identity, t)
            if key in cache:
                return cache[key]
            try:
                state = node.at(t)
                if identity in self._parents:
                    state = compose_states(evaluate(self._parents[identity], t), state)
                reference = node.reference
                if reference is not None:

                    def lookup(target: str, at: float) -> VisualState:
                        if target not in self._declared[identity]:
                            raise ValueError(f"undeclared dependency {target!r}")
                        return evaluate(target, at)

                    value = reference.sample(state, t, lookup)
                    if not isinstance(value, VisualState):
                        raise TypeError("reference must return VisualState")
                    if any(
                        getattr(value, c) != getattr(state, c)
                        for c in CHANNELS - self._writable[identity]
                    ):
                        raise ValueError("reference wrote an undeclared channel")
                    state = value
            except SceneReferenceError:
                raise
            except Exception as error:
                raise SceneReferenceError(
                    f"sample at {t:.6f}s: {error}",
                    object_id=identity,
                    origin=node.origin,
                ) from error
            cache[key] = state
            return state

        return evaluate(name, time)
