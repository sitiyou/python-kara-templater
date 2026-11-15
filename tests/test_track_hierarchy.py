from dataclasses import replace

import pytest
from test_tracks import build, item

from kara_templater import (
    BLUE,
    Animate,
    Animation,
    AnimationTarget,
    Display,
    Follow,
    KaraokeLine,
    LineMatch,
    On,
    Overlay,
    PaintStyle,
    Ruby,
    SampleContext,
    Segment,
    Syllable,
    TextUnit,
    Track,
    on,
    prepare_sampling,
)


class UnitMotion(Animation):
    @on(Syllable.Singing)
    def move(self, event: Syllable.Singing) -> Animate:
        return Animate(event.target, scale=3, offset_x=7, opacity=0.5)


def scene(*, follow="syllable", reverse=False):
    source = replace(
        item(),
        source=KaraokeLine(
            (
                TextUnit("AB", (Segment(1000, 2000, "abc"),)),
                TextUnit("CD", (Segment(1000, 2000, "def"),)),
            )
        ),
    )
    group = On(Display.Start, Animate(scale=2, offset_x=11, opacity=0.5, duration=3000))
    reading = On(
        Display.Start,
        Animate(
            AnimationTarget(source.id, (0,), "ruby", ((0, 0),)),
            scale=4,
            offset_x=5,
            opacity=0.5,
            duration=3000,
        ),
    )
    animations = (group, UnitMotion(), reading)
    if reverse:
        animations = tuple(reversed(animations))
    track = Track(
        source=LineMatch(),
        ruby=Ruby(follow=follow),
        overlay=Overlay(style=PaintStyle(fill=BLUE)),
        animations=animations,
    )
    return build(track, source), build(Track(source=LineMatch(), ruby=Ruby()), source)


def sample(plan, layer, time=1500):
    assert plan.dynamic is not None
    return plan.dynamic.function(
        SampleContext(time, 0.5, layer.window, layer.animation_id, 0)
    )


def test_group_unit_and_reading_affines_compose_inner_to_outer():
    plan, plain = scene()
    body = next(
        layer
        for layer in plan.layers
        if layer.style.name == "Default" and "/unit:0/" in layer.source_id
    )
    ruby = next(
        layer
        for layer in plan.layers
        if layer.style.name == "ruby" and "/ruby:0:0/" in layer.source_id
    )
    body_value, ruby_value = sample(plan, body), sample(plan, ruby)
    assert body_value.scale == 6 and body_value.opacity == 0.25
    assert ruby_value.scale == 24 and ruby_value.opacity == 0.125
    # Use native layout boxes to derive the three independent centers.
    body_boxes = [layer.box for layer in plain.layers if layer.style.name == "Default"]
    group_x = (
        min(box.left for box in body_boxes) + max(box.right for box in body_boxes)
    ) / 2
    unit_boxes = [
        layer.box
        for layer in plain.layers
        if layer.style.name == "Default" and "/unit:0/" in layer.source_id
    ]
    unit_x = (
        min(box.left for box in unit_boxes) + max(box.right for box in unit_boxes)
    ) / 2
    reading_x = ruby.box.center
    # Character positioning is quantized to the font's subpixel grid; the
    # transform center uses the original advance box rather than summed ink.
    assert body_value.offset_x == pytest.approx(-group_x - 4 * unit_x + 25, abs=0.5)
    assert ruby_value.offset_x == pytest.approx(
        -group_x - 4 * unit_x - 18 * reading_x + 55, abs=0.5
    )
    assert body_value.pivot == ruby_value.pivot == (0, 0)
    assert not body.animations and not body.offsets


def test_declaration_order_does_not_change_ancestor_composition():
    forward, _ = scene()
    backward, _ = scene(reverse=True)
    for first, second in zip(forward.layers, backward.layers, strict=True):
        assert sample(forward, first) == sample(backward, second)


def test_ruby_follow_disables_unit_motion_but_not_root_or_own_motion():
    plan, _ = scene(follow=Follow(position=False, scale=False, opacity=False))
    ruby = next(
        layer
        for layer in plan.layers
        if layer.style.name == "ruby" and "/ruby:0:0/" in layer.source_id
    )
    value = sample(plan, ruby)
    assert value.scale == 8
    assert value.opacity == 0.25


def test_sampled_output_applies_the_affine_once_to_text_and_sweep():
    plan, _ = scene()
    assert plan.dynamic is not None
    layers = prepare_sampling(plan.layers, plan.dynamic, max_events=100000).evaluate()
    drawn = next(
        layer
        for layer in layers
        if layer.style.name == "Default"
        and layer.clips
        and layer.active_window is not None
        and layer.active_window.start_ms <= 1520 < layer.active_window.end_ms
    )
    original = next(
        layer
        for layer in plan.layers
        if layer.source_id == drawn.source_id.rsplit("/sample:", 1)[0]
    )
    value = sample(plan, original, 1520)
    (motion,) = drawn.animations
    x, y = motion.point_at(drawn.box.center, drawn.box.middle, 1520)
    assert x == pytest.approx(value.scale * original.box.center + value.offset_x)
    assert y == pytest.approx(value.scale * original.box.middle + value.offset_y)
    assert drawn.clips is not None and original.clips is not None
    clip = drawn.clips[0].at(1520)
    x, _ = motion.point_at(clip.left, 0, 1520)
    assert x == pytest.approx(
        value.scale * original.clips[0].at(1520).left + value.offset_x
    )


def test_root_opacity_multiplies_local_opacity_once():
    source = item()
    track = Track(
        source=LineMatch(),
        ruby=Ruby(follow="syllable"),
        animations=(
            On(Display.Start, Animate(opacity=0.5, duration=3000)),
            On(Syllable.Singing, Animate(opacity=0.5)),
        ),
    )
    plan = build(track, source)
    for layer in plan.layers:
        assert sample(plan, layer).opacity == 0.25
