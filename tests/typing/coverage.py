from typing import assert_type

from kara_templater import (
    CoveragePartition,
    CoverageResult,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    PreparedTrackCoverage,
    SceneResult,
    ScopeOpacity,
    VisualState,
    compile_coverage,
    prepare_track_coverage,
)


def appearance(state: VisualState, time: float) -> Glow | None:
    return Glow(blur=2) if time < 1 else None


glow = GlowFunction(appearance, max_blur=2, max_border=3)
partition = CoveragePartition(lambda state, time: (), max_regions=1)
opacity = ScopeOpacity("root", lambda time: 1)
assert_type(glow.sample(VisualState(), 0), Glow | None)
assert_type(opacity.sample(0), float)
result = compile_coverage(
    Document.create(), ObjectGroup(id="root", lifetime=Lifetime(0, 1), children=())
)
assert_type(result, CoverageResult)
assert_type(result.document, Document)
assert_type(result.output, SceneResult)
assert_type(result.sample_times, tuple[float, ...])

prepared = prepare_track_coverage(
    Document.create(), tracks=(), max_glow_blur=8, max_glow_border=4
)
assert_type(prepared, PreparedTrackCoverage)
assert_type(prepared.group, ObjectGroup)
assert_type(prepared.glows, dict[str, Glow | GlowFunction])
assert_type(prepared.compile(), CoverageResult)
