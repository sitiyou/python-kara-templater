"""State keyframes share Scene's timing, channel and ownership contracts."""

import pytest

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    PathObject,
    Scene,
    SceneTimeline,
    StateKeyframe,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)


def square(timeline: SceneTimeline) -> PathObject:
    return PathObject(
        id="square",
        lifetime=Lifetime(1, 5),
        path=VectorPath.rectangle(20, 20),
        state=VisualState(fill=CYAN),
        animations=timeline.clips,
    )


def test_keyframes_capture_state_keep_omitted_channels_and_seek():
    timeline = SceneTimeline().keyframes(
        StateKeyframe(0.5, StatePatch(position=Vec2(20, 0))),
        StateKeyframe(1.5, StatePatch(position=Vec2(60, 0)), lambda p: p * p),
        StateKeyframe(2, StatePatch(fill=PINK)),
        at=0.25,
    )
    node = square(timeline)
    for time, x in ((4, 60), (1.5, 10), (2.25, 30), (1, 0), (2.75, 60)):
        assert node.at(time).position.x == pytest.approx(x)
    assert node.at(4).fill == PINK
    assert node.at(2.75).fill == CYAN
    timeline.play(Tween(StatePatch(opacity=0)), duration=0.5)
    assert timeline.clips[-1].start == 2.25


def test_keyframes_compile_identically_to_explicit_plays_and_repeat():
    frames = (
        StateKeyframe(0.35, StatePatch(position=Vec2(30, 10))),
        StateKeyframe(0.75, StatePatch(position=Vec2(), fill=PINK)),
    )
    keyed = SceneTimeline().wait(0.1).keyframes(*frames).repeat(2)
    explicit = SceneTimeline().wait(0.1)
    explicit.play(Tween(frames[0].target), duration=0.35)
    explicit.play(Tween(frames[1].target), duration=0.4).repeat(2)
    actual = Scene(Document.create()).add(square(keyed)).compile()
    expected = Scene(Document.create()).add(square(explicit)).compile()
    assert actual.document.dumps() == expected.document.dumps()


def test_keyframe_conflict_is_atomic_and_parallel_channels_work():
    timeline = SceneTimeline().play(Tween(StatePatch(opacity=0.5)), duration=2)
    before = timeline.clips
    with pytest.raises(ValueError, match="overlapping"):
        timeline.keyframes(
            StateKeyframe(0.5, StatePatch(position=Vec2(20, 0))),
            StateKeyframe(1, StatePatch(opacity=0)),
            at=0,
        )
    assert timeline.clips == before
    timeline.keyframes(StateKeyframe(1, StatePatch(position=Vec2(20, 0))), at=0)
    assert square(timeline).at(1.5).opacity == pytest.approx(0.875)
    assert square(timeline).at(1.5).position.x == 10


@pytest.mark.parametrize("time", [0, -1, float("nan"), float("inf")])
def test_keyframe_rejects_invalid_time(time: float):
    with pytest.raises(ValueError):
        StateKeyframe(time, StatePatch(opacity=0))


def test_keyframe_rejects_empty_invalid_or_unordered_targets():
    with pytest.raises(ValueError, match="property"):
        StateKeyframe(1, StatePatch())
    with pytest.raises(ValueError, match="opacity"):
        StateKeyframe(1, StatePatch(opacity=2))
    timeline = SceneTimeline().wait(0.2)
    for times in ((1, 1), (1, 0.5)):
        with pytest.raises(ValueError, match="strictly increase"):
            timeline.keyframes(
                *(StateKeyframe(t, StatePatch(opacity=0)) for t in times)
            )
    with pytest.raises(ValueError, match="at least one"):
        timeline.keyframes()
    assert timeline.clips == ()
    timeline.keyframes(StateKeyframe(1, StatePatch(opacity=0)))
    assert timeline.clips[0].start == 0.2
