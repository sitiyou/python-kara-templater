"""Nested author composition uses the common evaluator and binding protocol."""

from dataclasses import replace

import pytest
from test_lyric_line import subject

from kara_templater import (
    Lifetime,
    LyricAnimationContext,
    LyricRule,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
)


def animation():
    return (
        Timeline()
        .play(Tween(StatePatch(scale=Vec2(1.2, 1.2))), duration=0.1)
        .wait(0.2)
        .play(Tween(StatePatch(scale=Vec2(1, 1))), duration=0.1)
        .animation
    )


def test_nested_schedule_preserves_boundaries_holds_and_random_access():
    sequence = animation()
    node = TextObject(id="word", text="x", lifetime=Lifetime(0, 3)).animate(
        sequence, duration=2
    )
    assert node.animations[0].breakpoints == pytest.approx((0, 0.5, 1.5, 2))
    for time, scale in ((1.75, 1.1), (0.25, 1.1), (1, 1.2), (2.5, 1)):
        assert node.at(time).scale.x == pytest.approx(scale)
    nested = Timeline().play(sequence, duration=0.8).wait(0.2).repeat(2).animation
    bound = replace(node, animations=()).animate(nested, duration=2)
    assert bound.animations[0].breakpoints == pytest.approx(
        (0, 0.2, 0.6, 0.8, 1, 1.2, 1.6, 1.8)
    )
    assert bound.at(1.1).scale.x == pytest.approx(bound.at(0.1).scale.x)


def test_context_factory_returns_the_same_composable_animation_protocol():
    _, line = subject()
    calls = []

    def factory(timing: LyricAnimationContext):
        calls.append((timing.line.id, timing.target.id))
        return animation()

    bound = line.bind(LyricRule("syllable", "singing", factory, duration=0.5))
    assert len(calls) == 2
    assert len(bound.children[0].animations) == 1
    assert bound.children[0].at(1.25).scale == Vec2(1.2, 1.2)
    assert line.children[0].animations == ()
    direct = TextObject(id="plain", text="x", lifetime=Lifetime(1, 2)).animate(
        animation(), duration=0.5
    )
    for time in (1.1, 1.4, 1.25):
        assert direct.at(time).scale == bound.children[0].at(time).scale


def test_sequence_release_uses_common_underlying_held_state():
    sequence = (
        Timeline()
        .play(Tween(StatePatch(opacity=0.5)), duration=0.1)
        .play(Tween(StatePatch(opacity=0)), duration=0.1, hold=False)
        .wait(0.1)
        .animation
    )
    node = TextObject(id="word", text="x", lifetime=Lifetime(0, 1)).animate(
        sequence, duration=0.3
    )
    assert node.at(0.15).opacity == pytest.approx(0.25)
    assert node.at(0.25).opacity == 0.5
    assert node.at(0.5).opacity == 0.5
    with pytest.raises(ValueError, match="positive duration"):
        _ = Timeline().animation


def test_timeline_sorts_explicit_starts_and_sequence_freezes_its_schedule():
    timeline = Timeline().play(
        Tween(StatePatch(position=Vec2(30, 0))), at=1, duration=1
    )
    timeline.play(Tween(StatePatch(position=Vec2(10, 0))), at=0, duration=1)
    sequence = timeline.animation
    timeline.play(Tween(StatePatch(opacity=0)), duration=1)
    node = TextObject(id="word", text="x", lifetime=Lifetime(0, 3)).animate(
        sequence, duration=2
    )
    for time, x in ((1.5, 20), (0.5, 5), (2.5, 30), (1, 10)):
        assert node.at(time).position.x == pytest.approx(x)
        assert node.at(time).opacity == 1
    assert sequence.duration == 2
    assert timeline.animation.duration == 3


def test_lyric_factory_combines_material_and_geometry_on_common_timeline():
    from kara_templater import RED, Color, ScalePulse, Scene

    document, line = subject()
    calls: list[str] = []

    def factory(timing: LyricAnimationContext):
        calls.append(timing.target.id)
        return (
            Timeline()
            .play(Tween(StatePatch(fill=RED)), at=0, duration=0.5)
            .play(ScalePulse(peak=1.1), at=0, duration=0.5)
            .animation
        )

    animated = line.bind(LyricRule("character", "singing", factory))
    assert calls == [target.id for target in line.query("character")]
    evaluator = Scene(document).add(animated).evaluator()
    target = animated.query("character")[0]
    value = evaluator.at(target.node_id, 1.25)
    assert value.fill == Color(255, 128, 128)
    assert value.scale == Vec2(1.1, 1.1)
    assert len(calls) == len(line.query("character"))


@pytest.mark.parametrize("hold", (False, True))
def test_nested_parallel_release_defines_following_start_for_objects_and_lyrics(hold):
    from kara_templater import FadeIn, FadeOut

    movement = (
        Timeline()
        .play(Tween(StatePatch(position=Vec2(0, 10))), duration=0.05)
        .play(Tween(StatePatch(position=Vec2(10, 10))), duration=0.15)
        .animation
    )
    envelope = (
        Timeline()
        .play(Tween(StatePatch(scale=Vec2(1.1, 1.1))), duration=0.01)
        .wait(0.05)
        .play(Tween(StatePatch(scale=Vec2(1, 1))), duration=0.24)
        .animation
    )
    parallel = (
        Timeline()
        .play(movement, at=0, duration=movement.duration)
        .play(envelope, at=0, duration=envelope.duration)
        .animation
    )
    sequence = (
        Timeline()
        .play(FadeIn(), duration=0.1)
        .play(parallel, duration=parallel.duration)
        .play(FadeOut(), duration=0.08, hold=hold)
        .animation
    )
    assert sequence.duration == pytest.approx(0.48)
    assert sequence.clips[-1].start == pytest.approx(0.4)
    _, line = subject()
    bound = line.bind(LyricRule("line", "enter", sequence))
    node = TextObject(id="plain", text="x", lifetime=line.lifetime).animate(
        sequence, duration=sequence.duration
    )
    for time in (0.44, 0.05, 0.225, 0.28, 0.5):
        assert bound.at(time) == node.at(time)
    assert node.at(0.44).opacity == pytest.approx(0.5)
    assert node.at(0.05).opacity == pytest.approx(0.5)
    assert node.at(0.225).position == Vec2(5, 10)
    assert node.at(0.28).scale.x == pytest.approx(1.05)
    for time in (0.48, 0.5):
        assert node.at(time).opacity == (0 if hold else 1)


@pytest.mark.parametrize("hold", (False, True))
def test_decimal_clip_boundary_matches_the_common_seek_clock(hold):
    node = TextObject(id="word", text="x", lifetime=Lifetime(0, 1)).animate(
        Tween(StatePatch(opacity=0)),
        at=0.1 + 0.2,
        duration=0.3,
        hold=hold,
    )
    assert node.at(0.45).opacity == pytest.approx(0.5)
    for time in (0.6, node.animations[0].end, 0.7):
        assert node.at(time).opacity == (0 if hold else 1)


def test_adjacent_decimal_clips_capture_at_the_same_boundary_without_false_conflict():
    node = TextObject(id="word", text="x", lifetime=Lifetime(0, 1)).animate(
        Tween(StatePatch(opacity=0.5)), at=0.1, duration=0.2
    )
    joined = node.animate(Tween(StatePatch(opacity=0)), at=0.3, duration=0.2)
    assert joined.at(0.3).opacity == 0.5
    assert joined.at(0.4).opacity == pytest.approx(0.25)
    assert joined.at(0.5).opacity == 0
    with pytest.raises(ValueError, match="overlapping animation channels"):
        node.animate(Tween(StatePatch(opacity=0)), at=0.29, duration=0.2)
