"""Common author animations capture state and compose through the real hierarchy."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    FadeIn,
    FadeOut,
    Jump,
    Lifetime,
    ObjectGroup,
    PathObject,
    ScalePulse,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)


def test_same_fade_instance_on_text_path_and_group_captures_opacity():
    fade = FadeIn()
    nodes = (
        TextObject(id="text", lifetime=Lifetime(1, 3), text="word"),
        PathObject(id="path", lifetime=Lifetime(1, 3), path=VectorPath.rectangle(5, 5)),
        ObjectGroup(id="group", lifetime=Lifetime(1, 3), children=()),
    )
    for node in nodes:
        original = replace(node, state=VisualState(opacity=0.6))
        animated = original.animate(fade, duration=0.4).animate(
            FadeOut(), at=1.6, duration=0.4
        )
        # Non-sequential queries exercise captured state independently of frames.
        for time, opacity in ((2.8, 0.3), (1, 0), (2, 0.6), (1.2, 0.3), (3, 0)):
            assert animated.at(time).opacity == pytest.approx(opacity)
        assert original.animations == ()
        assert animated.animations[0].animation is fade


def test_parent_fade_and_child_jump_share_evaluator_and_compile():
    child = TextObject(
        id="syllable",
        text="Hi",
        lifetime=Lifetime(1, 3),
        state=VisualState(position=Vec2(20, 30), opacity=0.5),
    ).animate(Jump(height=10), duration=1)
    group = ObjectGroup(
        id="line",
        lifetime=Lifetime(1, 3),
        children=(child,),
        state=VisualState(position=Vec2(100, 100), opacity=0.8),
    ).animate(FadeIn(), duration=1)
    scene = Scene(Document.create()).add(group)
    evaluator = scene.evaluator()
    state = evaluator.at("syllable", 1.5)
    assert state.opacity == pytest.approx(0.2)
    assert state.position == Vec2(120, 120)
    assert child.at(2).position == Vec2(20, 30)


def test_binding_validates_atomically_and_release_restores_held_value():
    node = TextObject(id="text", text="word", lifetime=Lifetime(0, 3))
    held = node.animate(Tween(StatePatch(opacity=0.4)), duration=0.5)
    released = held.animate(FadeOut(), at=1, duration=0.5, hold=False)
    assert released.at(1.25).opacity == pytest.approx(0.2)
    assert released.at(1.5).opacity == pytest.approx(0.4)
    with pytest.raises(ValueError, match="overlapping"):
        held.animate(FadeIn(), at=0.25, duration=1)
    with pytest.raises(ValueError, match="beyond lifetime"):
        held.animate(Jump(), at=2.5, duration=1)
    assert len(held.animations) == 1


@pytest.mark.parametrize("rate", [lambda p: float("nan"), lambda p: 2])
def test_invalid_fade_rates_cannot_escape_visual_state_validation(rate):
    with pytest.raises(ValueError):
        FadeIn(rate).sample(VisualState(), 0.5)
    with pytest.raises(ValueError):
        FadeOut(rate).sample(VisualState(), 0.5)


@pytest.mark.parametrize("peak", [0, -1, float("nan"), float("inf")])
def test_scale_pulse_rejects_invalid_peak(peak):
    with pytest.raises(ValueError):
        ScalePulse(peak=peak)


def test_scale_pulse_captures_held_scale_and_conflicts_with_position_writes():
    node = TextObject(
        id="pulse", text="word", lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(20, 30), opacity=0.6),
    ).animate(Tween(StatePatch(scale=Vec2(2, 3))), duration=0.5)
    pulsing = node.animate(ScalePulse(peak=0.5), at=1, duration=1)
    for time, expected in ((1.5, Vec2(1, 1.5)), (2, Vec2(2, 3)), (1, Vec2(2, 3))):
        state = pulsing.at(time)
        assert state.scale == expected
        assert state.position == Vec2(20, 30)
        assert state.opacity == 0.6
    with pytest.raises(ValueError, match="overlapping"):
        pulsing.animate(Jump(), at=1, duration=1)
