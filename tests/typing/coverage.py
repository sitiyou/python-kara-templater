from typing import assert_type

from kara_templater import (
    Coverage,
    CoveragePartition,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    Scene,
    SceneResult,
    ScopeOpacity,
    StatePatch,
    Tween,
    VisualState,
)


def appearance(state: VisualState, time: float) -> Glow | None:
    return Glow(blur=2) if time < 1 else None


glow = GlowFunction(appearance, max_blur=2, max_border=3)
partition = CoveragePartition(lambda state, time: (), max_regions=1)
opacity = ScopeOpacity("root", lambda time: 1)
assert_type(glow.sample(VisualState(), 0), Glow | None)
assert_type(opacity.sample(0), float)
result = (
    Scene(Document.create())
    .add(
        ObjectGroup(
            id="root", lifetime=Lifetime(0, 1), children=(), coverage=Coverage()
        )
    )
    .ass.compile()
)
assert_type(result, SceneResult)
assert_type(result.document, Document)

assert_type(
    GlowFunction.from_animation(Tween(StatePatch(blur=2)), duration=1), GlowFunction
)
