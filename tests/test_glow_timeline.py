"""Glow callbacks reuse ordinary state timelines instead of a material evaluator."""

from dataclasses import replace

import pytest

from kara_templater import (
    RED,
    WHITE,
    AnimationSequence,
    Color,
    Glow,
    GlowFunction,
    Lifetime,
    StateFunction,
    StateKeyframe,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VisualState,
)


def glow_from(
    animation: AnimationSequence,
    base: VisualState,
    *,
    max_blur: float,
    max_border: float,
) -> GlowFunction:
    return GlowFunction.from_animation(
        animation,
        base=Glow(base.fill, blur=base.blur, border=base.border, opacity=base.opacity),
        max_blur=max_blur,
        max_border=max_border,
    )


def test_glow_multi_property_tween_matches_the_same_animation_on_a_drawing():
    base = VisualState(fill=WHITE, outline=WHITE, border=3, blur=2, opacity=0.8)
    sequence = (
        Timeline()
        .play(
            Tween(StatePatch(fill=RED, border=7, blur=10, opacity=0.4)),
            duration=1,
        )
        .animation
    )
    glow = glow_from(sequence, base, max_blur=10, max_border=7)
    drawing = TextObject(
        id="direct", text="A", lifetime=Lifetime(0, 1), state=base
    ).animate(sequence, duration=1)
    mid = drawing.at(0.5)
    assert mid.fill == Color(255, 128, 128)
    assert mid.border == 5 and mid.blur == 6
    assert mid.opacity == pytest.approx(0.6)
    for time in (0.9, 0.1, 0.5):
        state = drawing.at(time)
        assert glow.sample(VisualState(), time) == Glow(
            state.fill, blur=state.blur, border=state.border, opacity=state.opacity
        )


def test_glow_envelope_release_and_next_action_use_timeline_seconds():
    base = VisualState(blur=2)
    sequence = (
        Timeline()
        .play(Tween(StatePatch(blur=10)), duration=0.1)
        .wait(0.9)
        .play(Tween(StatePatch(blur=2)), duration=0.2)
        .play(Tween(StatePatch(fill=RED)), duration=0.1)
        .animation
    )
    glow = glow_from(sequence, base, max_blur=10, max_border=0)
    for time, radius in ((1.1, 6), (0.05, 6), (0.5, 10), (1.2, 2), (1.3, 2)):
        value = glow.sample(VisualState(), time)
        assert value is not None and value.blur == pytest.approx(radius)
    value = glow.sample(VisualState(), 1.25)
    assert value is not None
    assert (value.color.red, value.color.green, value.color.blue) == pytest.approx(
        (255, 127.5, 127.5), abs=0.5
    )
    assert sequence.duration == pytest.approx(1.3)
    assert glow.breakpoints == pytest.approx((0, 0.1, 1, 1.2, 1.3))


def test_glow_keyframes_combine_with_custom_numeric_animation():
    base = VisualState(blur=2, border=2)
    sequence = (
        Timeline()
        .keyframes(
            StateKeyframe(0.5, StatePatch(blur=10)),
            StateKeyframe(1, StatePatch(blur=2)),
        )
        .play(
            StateFunction(
                lambda state, p: replace(state, border=2 + 4 * p),
                frozenset(("border",)),
            ),
            at=0,
            duration=1,
        )
        .animation
    )
    glow = glow_from(sequence, base, max_blur=10, max_border=6)
    value = glow.sample(VisualState(), 0.5)
    assert value is not None and value.blur == 10 and value.border == 4
    with pytest.raises(ValueError, match="bounds"):
        replace(glow, max_border=3).sample(VisualState(), 0.5)


def test_animation_glow_infers_nested_linear_bounds_without_sampling_callbacks():
    calls: list[float] = []
    color = StateFunction(
        lambda state, p: calls.append(p) or replace(state, fill=RED),
        frozenset(("fill",)),
    )
    inner = (
        Timeline()
        .play(Tween(StatePatch(blur=10, border=6)), duration=0.1)
        .play(Tween(StatePatch(blur=2, border=1)), duration=0.2)
        .animation
    )
    animation = (
        Timeline()
        .play(inner, at=0, duration=0.3)
        .play(color, at=0, duration=0.3)
        .repeat(2)
        .animation
    )
    glow = GlowFunction.from_animation(animation, base=Glow(WHITE, blur=12, border=3))
    assert not calls
    assert glow.max_blur == 12 and glow.max_border == 6
    assert glow.breakpoints == pytest.approx((0, 0.1, 0.3, 0.4, 0.6))
    for time in (0.5, 0.05, 0.35):
        value = glow.sample(VisualState(), time)
        assert value is not None and value.blur <= 12 and value.border <= 6
    assert calls


def test_animation_glow_custom_spatial_rate_needs_bounds_and_checks_samples():
    calls: list[float] = []
    animation = Tween(StatePatch(blur=10), rate=lambda p: calls.append(p) or 2 * p)
    with pytest.raises(ValueError, match="requires max_blur"):
        GlowFunction.from_animation(animation, duration=1)
    assert not calls
    glow = GlowFunction.from_animation(animation, duration=1, max_blur=10)
    assert not calls
    with pytest.raises(ValueError, match="declared.*bounds"):
        glow.sample(VisualState(), 0.9)
    assert calls
    for base, animation, bound in (
        (Glow(blur=5), Tween(StatePatch(blur=2)), 4),
        (Glow(blur=2), Tween(StatePatch(blur=10)), 9),
    ):
        with pytest.raises(ValueError, match="omits base or known"):
            GlowFunction.from_animation(
                animation, base=base, duration=1, max_blur=bound
            )


def test_animation_glow_uses_common_start_release_and_channel_filtering():
    base = Glow(WHITE, blur=2)
    glow = GlowFunction.from_animation(
        Tween(StatePatch(blur=10)), base=base, start=0.2, duration=0.5, hold=False
    )
    assert glow.breakpoints == pytest.approx((0.2, 0.7))
    for time, blur in ((0.8, 2), (0.1, 2), (0.45, 6), (0.7, 2)):
        value = glow.sample(VisualState(), time)
        assert value is not None and value.blur == pytest.approx(blur)
    # Undeclared fields obey the same channel filtering as a drawing animation.
    custom = StateFunction(
        lambda state, p: replace(state, fill=RED, blur=99), frozenset(("fill",))
    )
    value = GlowFunction.from_animation(custom, duration=1, base=base).sample(
        VisualState(), 0.5
    )
    assert value == Glow(RED, blur=2)
    with pytest.raises(ValueError, match="duration"):
        GlowFunction.from_animation(Tween(StatePatch(blur=2)))
    with pytest.raises(ValueError, match="support"):
        GlowFunction.from_animation(Tween(StatePatch(scale=Vec2(2, 2))), duration=1)


@pytest.mark.parametrize("opacity", (-0.01, 1.01, float("nan"), float("inf")))
def test_glow_opacity_is_validated_for_static_and_animated_values(opacity):
    with pytest.raises(ValueError):
        Glow(opacity=opacity)
    effect = GlowFunction(
        lambda state, time: Glow(opacity=opacity), max_blur=0, max_border=0
    )
    with pytest.raises(ValueError):
        effect.sample(VisualState(), 0.5)
