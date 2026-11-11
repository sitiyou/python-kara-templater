import re
from dataclasses import replace

import pytest
from test_effect_halo import build

from kara_templater import (
    Body,
    Box,
    ClipSpan,
    DisplayWindow,
    DynamicEffect,
    DynamicProperties,
    Effect,
    Halo,
    Lyrics,
    OffsetAnimation,
    OutputCapabilityError,
    Region,
    Ruby,
    ScaleAnimation,
    Segment,
    Style,
    TextLayer,
    compile_layers,
    prepare_sampling,
    singing,
)
from kara_templater.ass_output import _mask, _offset, _transform

BASE = TextLayer("offset", "A", Style(), Box(100, 100, 100, 40), DisplayWindow(0, 3000))


def test_native_xy_have_independent_clocks_and_keep_reset_boundaries():
    layer = replace(
        BASE,
        offsets=(
            OffsetAnimation(((1000, 10), (2000, 30)), "x", keep=True),
            OffsetAnimation(((1500, -10), (2500, 10)), "y"),
        ),
    )
    assert _transform(layer, 999)[1:3] == (150, 120)
    assert _transform(layer, 1500)[1:3] == (170, 110)
    assert _transform(layer, 2500)[1:3] == (180, 120)
    result = compile_layers((layer,)).events
    at = next(e for e in result if e.start_time == 1500)
    assert r"\move(170,110,180,120,0,500)" in at.text
    assert r"\pos(180,120)" in result[-1].text


def test_offset_is_applied_after_scale_to_text_and_mask_once():
    span = ClipSpan(1000, 2000, Region(100, 100), Region(100, 200))
    layer = replace(
        BASE,
        clips=(span,),
        offsets=(OffsetAnimation(((1000, 0), (2000, 100)), "x"),),
        animations=(
            ScaleAnimation(
                "scale",
                "test",
                0,
                500,
                1500,
                2,
                (100, 100),
                ((500, 1), (1500, 2)),
                True,
            ),
        ),
    )
    assert _transform(layer, 1250)[1:3] == (212.5, 135)
    assert _mask(layer, span, 1250) == Region(125, 168.75)
    events = compile_layers((layer,)).events
    for event in events:
        if 1000 <= event.start_time < event.end_time <= 1500:
            move = re.search(r"\\move\(175,130,250,140,(-?\d+),(-?\d+)\)", event.text)
            assert move
            assert event.start_time + int(move[1]) == 1000
            assert event.start_time + int(move[2]) == 1500
            assert r"\fscx100\fscy100" in event.text


def test_sample_exposure_preserves_native_move_and_clip_clocks():
    layer = replace(
        BASE,
        offsets=(OffsetAnimation(((1000, 0), (2000, 100)), "x"),),
        clips=(ClipSpan(1000, 2000, Region(100, 100), Region(100, 200)),),
        active_window=DisplayWindow(1600, 1700),
    )
    (event,) = compile_layers((layer,)).events
    assert r"\move(150,120,250,120,-600,400)" in event.text
    assert r"\clip(100,0,100,1080)" in event.text
    assert r"\t(-600,400,1,\clip(200,0,300,1080))" in event.text


def test_vertical_motion_does_not_reanchor_horizontal_sweep_clips():
    layer = replace(
        BASE,
        offsets=(OffsetAnimation(((1200, 0), (1800, 20)), "y"),),
        clips=(ClipSpan(1000, 2000, Region(100, 100), Region(100, 200)),),
    )
    event = next(e for e in compile_layers((layer,)).events if e.start_time == 1200)
    assert r"\clip(100,0,100,1080)" in event.text
    assert r"\t(-200,800,1,\clip(100,0,200,1080))" in event.text


def test_offset_validation_and_centisecond_collapse():
    with pytest.raises(ValueError, match="overlapping x"):
        replace(
            BASE,
            offsets=(
                OffsetAnimation(((0, 0), (2000, 20)), "x"),
                OffsetAnimation(((1000, 0), (2500, 10)), "x"),
            ),
        )
    with pytest.raises(OutputCapabilityError, match="offset keyframes collapse"):
        compile_layers(
            (replace(BASE, offsets=(OffsetAnimation(((1000, 0), (1004, 20)), "x"),)),)
        )
    with pytest.raises(ValueError):
        OffsetAnimation(((0, 0), (1000, float("inf"))), "x")


class Moved(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby(follow="syllable"), Halo())

    def configure(self):
        self.text.sweep()
        self.syllables.on_singing(offset_x=(0, 20), offset_y=(0, -10), pulse=1.2)


def test_author_offsets_lower_with_scale_ruby_and_halo_following():
    plan, _, _ = build(Moved())
    assert plan.dynamic is None
    assert all(len(layer.offsets) == 2 and layer.animations for layer in plan.layers)
    assert compile_layers(plan.layers).events


def test_one_sampled_axis_can_coexist_with_other_native_axis():
    class Mixed(Moved):
        def configure(self):
            self.syllables.on_singing(offset_x=(0, 20), offset_y=lambda p: -10 * p)

    plan, _, _ = build(Mixed())
    assert plan.dynamic is not None
    assert all([m.axis for m in l.offsets] == ["x"] for l in plan.layers)
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert all(l.offsets for l in sampled)
    assert compile_layers(sampled).events


def test_short_offset_remains_sampled_in_author_layer():
    class Short(Moved):
        def configure(self):
            self.syllables.on_singing(offset_x=(0, 20))

    plan, _, _ = build(Short(), segments=(Segment(1000, 1004),))
    assert plan.dynamic is not None
    assert not any(l.offsets for l in plan.layers)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events


@pytest.mark.parametrize("mode", ["add", "override"])
def test_known_offset_composition_preserves_jumps_release_and_keep(mode):
    class Composed(Moved):
        def configure(self):
            self.syllables.on_singing(offset_x=(0, 20), keep=True, compose=mode)
            self.syllables.animate(
                offset_x=(100, 200),
                during=(singing.start + 500, singing.start + 800),
                compose=mode,
            )
            self.syllables.animate(
                offset_x=(0, 3),
                during=(singing.end + 200, singing.end + 200),
                keep=True,
                compose=mode,
            )

    plan, _, _ = build(Composed(), segments=(Segment(1000, 2000),))
    assert plan.dynamic is None
    expected = {
        999: 0,
        1250: 5,
        1500: 110 if mode == "add" else 100,
        1650: 163 if mode == "add" else 150,
        1800: 16,
        2000: 20,
        2200: 23 if mode == "add" else 3,
        2900: 23 if mode == "add" else 3,
    }
    for layer in plan.layers:
        for time, value in expected.items():
            assert _offset(layer, time, "x") == pytest.approx(value)
        assert _offset(layer, 1500, "x", left=True) == 10
        assert _offset(layer, 1800, "x", left=True) == (216 if mode == "add" else 200)
    assert compile_layers(plan.layers).events


def test_unknown_composed_offset_does_not_execute_during_lowering():
    calls = []

    class Mixed(Moved):
        def configure(self):
            self.syllables.on_singing(offset_x=(0, 20), compose="add")
            self.syllables.on_singing(
                offset_x=lambda p: calls.append(p) or 5, compose="add"
            )

    plan, _, _ = build(Mixed())
    assert not calls
    assert plan.dynamic is not None
    assert not any(layer.offsets for layer in plan.layers)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events
    assert calls


def test_sampled_scale_and_y_preserve_native_x_after_scaling():
    span = ClipSpan(1000, 2000, Region(100, 100), Region(100, 200))
    layer = replace(
        BASE,
        offsets=(OffsetAnimation(((1000, 0), (2000, 100)), "x"),),
        clips=(span,),
    )
    sampled = prepare_sampling(
        (layer,),
        DynamicEffect(
            lambda ctx: DynamicProperties(scale=2, pivot=(100, 100), offset_y=-10)
        ),
    ).evaluate()
    assert len(sampled) == 1
    # Scale about the source pivot, then add x=25 and y=-10 once.
    assert _transform(sampled[0], 1250)[1:3] == (225, 130)
    assert _mask(sampled[0], span, 1250) == Region(125, 175)
    assert compile_layers(sampled).events
