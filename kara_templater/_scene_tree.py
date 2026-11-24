"""Resolve drawable leaves in scene order and intersect their visible lifetimes."""

from dataclasses import dataclass

from .scene import (
    NativeEvent,
    ObjectGroup,
    PathObject,
    Scene,
    SceneCompileError,
    SceneObject,
    TextObject,
)
from .scene_animation import VisualState
from .scene_evaluation import SceneEvaluator
from .text_geometry import _VectorGuideText, text_to_path


@dataclass(frozen=True)
class SceneLeaf:
    node: TextObject | PathObject
    parents: tuple[ObjectGroup, ...]
    start: float
    end: float
    evaluator: SceneEvaluator

    def at(self, time: float) -> VisualState:
        return self.evaluator.at(self.node.id, time)


def scene_leaves(
    scene: Scene,
    evaluator: SceneEvaluator,
) -> tuple[
    tuple[SceneLeaf, ...],
    tuple[NativeEvent, ...],
    tuple[str, ...],
]:
    leaves: list[SceneLeaf] = []
    native: list[NativeEvent] = []
    order: list[str] = []
    ids: set[str] = set()

    def visit(
        node: SceneObject | NativeEvent, parents: tuple[ObjectGroup, ...]
    ) -> None:
        if node.id in ids:
            raise SceneCompileError(
                "duplicate object identity or group cycle", object_id=node.id
            )
        ids.add(node.id)
        if isinstance(node, NativeEvent):
            native.append(node)
            order.append(node.id)
            return
        if isinstance(node, ObjectGroup):
            for child in node.children:
                visit(child, (*parents, node))
            return
        start = max(n.lifetime.start for n in (*parents, node))
        end = min(n.lifetime.end for n in (*parents, node))
        if end > start:
            if isinstance(node, _VectorGuideText):
                node = text_to_path(node, path=node.outline.path)
            leaves.append(SceneLeaf(node, parents, start, end, evaluator))
            order.append(node.id)

    for node in scene.objects:
        visit(node, ())
    return tuple(leaves), tuple(native), tuple(order)
