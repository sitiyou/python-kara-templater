import pytest

from examples.composed_glow import ComposedGlow
from tools.validate_composed_glow import CASES, TIMES, front_error, scene


@pytest.mark.parametrize("target,follow,clip", CASES.values())
def test_combined_native_and_keyframe_curves_have_identical_output(
    target, follow, clip
):
    native = scene(ComposedGlow(target, follow, clip, "native"))
    keyframes = scene(ComposedGlow(target, follow, clip, "keyframes"))
    assert native.document.dumps() == keyframes.document.dumps()
    assert native.event_count < 200
    assert {e.layer for e, _ in native.event_origins} == {0, 2, 5}
    assert all(
        ref.item_id == "combined"
        for _, origin in native.event_origins
        for ref in origin.sources
    )
    assert max(front_error(native, target, follow, t) for t in TIMES) <= 0.75


@pytest.mark.parametrize("target,follow,clip", CASES.values())
def test_sampled_combinations_keep_parallel_front_geometry_and_source_metadata(
    target, follow, clip
):
    result = scene(ComposedGlow(target, follow, clip, "function"))
    assert max(front_error(result, target, follow, t) for t in TIMES) <= 0.75
    assert {
        ref.segment_index
        for _, origin in result.event_origins
        for ref in origin.sources
    } == {0}
    assert {
        track for _, origin in result.event_origins for track in origin.track_ids
    } == {"main", "echo"}
    assert all(
        e.start_time >= 0 and e.end_time <= 3000 for e, _ in result.event_origins
    )
    for time in TIMES:
        active = [
            e for e, _ in result.event_origins if e.start_time <= time < e.end_time
        ]
        assert {e.text.rsplit("}", 1)[-1] for e in active} == {"A", "B", "ab"}
        if time >= 2000:
            assert all(r"\1c&HFFFF00&" in e.text for e in active if e.layer == 5)


def test_per_character_scale_cannot_implicitly_drive_syllable_ruby_follow():
    with pytest.raises(ValueError, match="cannot follow per-character motion"):
        scene(ComposedGlow("characters", True))
