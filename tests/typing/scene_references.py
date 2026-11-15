from dataclasses import replace
from typing import assert_type

from kara_templater import (
    Document,
    FollowObject,
    ReferenceFunction,
    Scene,
    SceneEvaluator,
    StateLookup,
    StateReference,
    VisualState,
)


def custom(base: VisualState, time: float, lookup: StateLookup) -> VisualState:
    return replace(base, position=lookup("target", time).position)


def check(reference: StateReference) -> StateReference:
    return reference.shifted(1).retarget({"target": "copy"}, 1)


check(FollowObject("target"))
check(ReferenceFunction(custom, ("target",), frozenset(("position",))))
assert_type(Scene(Document.create()).evaluator(), SceneEvaluator)
