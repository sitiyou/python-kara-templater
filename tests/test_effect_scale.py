from math import pi, sin

import pytest
from test_effect_halo import build

from kara_templater import (
    Body,
    Effect,
    Halo,
    Keyframe,
    Keyframes,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    Segment,
    Transition,
    compile_layers,
    prepare_sampling,
    singing,
    smooth,
    there_and_back,
)


class Scaling(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby(follow="syllable"), Halo(blur=10, width=3))

    def configure(self):
        self.text.sweep()
        self.syllables.on_singing(pulse=1.2)


def test_native_pulse_shares_group_center_and_clock_with_ruby_and_halo():
    plan, _, context = build(Scaling())
    assert plan.dynamic is None
    box = context.layout.units[0].box
    assert all(
        layer.animations[0].pivot == (box.center, box.middle) for layer in plan.layers
    )
    assert all(
        layer.animations[0].start_ms == 1000 and layer.animations[0].end_ms == 2400
        for layer in plan.layers
    )
    assert all(layer.animations[0].scale_at(1700) == 1.2 for layer in plan.layers)
    assert all(layer.animations[0].scale_at(2400) == 1 for layer in plan.layers)
    assert any(r"\fscx120" in e.text for e in compile_layers(plan.layers).events)


def test_lambda_scale_is_deferred_and_transforms_all_followers_once():
    calls = []

    class Function(Scaling):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(
                scale=lambda p: calls.append(p) or 1 + 0.2 * sin(pi * p)
            )

    plan, _, context = build(Function())
    assert calls == []
    with pytest.raises(OutputCapabilityError, match="preflight"):
        prepare_sampling(plan.layers, plan.dynamic, max_events=1)
    assert calls == []
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert calls
    box = context.layout.units[0].box
    mid = [
        layer
        for layer in sampled
        if layer.active_window.start_ms <= 1700 < layer.active_window.end_ms
    ]
    assert mid
    for layer in mid:
        assert len(layer.animations) == 1
        animation = layer.animations[0]
        assert animation.pivot == (box.center, box.middle)
        assert animation.scale_at(1700) == pytest.approx(
            1 + 0.2 * sin(pi * (1680 - 1000) / 1400)
        )


def test_explicit_offsets_keep_original_clock_when_display_clips_interval():
    class Early(Scaling):
        def configure(self):
            self.syllables.animate(
                scale=Transition(1, 1.4),
                during=(singing.start - 800, singing.start + 200),
                keep=True,
            )

    plan, _, _ = build(Early())
    scale = plan.layers[0].animations[0]
    assert (scale.start_ms, scale.end_ms) == (200, 1200)
    assert scale.scale_at(500) == pytest.approx(1.12)
    assert scale.scale_at(2800) == 1.4
    events = compile_layers(plan.layers).events
    assert min(e.start_time for e in events) == 500
    assert any(
        r"\t(-300,700,1,\fscx140" in e.text for e in events if e.start_time == 500
    )
    assert all(r"\fscx140" in e.text for e in events if e.start_time >= 1200)


def test_no_spurious_transition_before_start_or_after_reset():
    class Reset(Scaling):
        def configure(self):
            self.syllables.animate(
                scale=Transition(1.2, 1.4), during=(singing.start, singing.end)
            )

    plan, _, _ = build(Reset())
    events = compile_layers(plan.layers).events
    outside = [e for e in events if e.end_time <= 1000 or e.start_time >= 2400]
    assert outside and all(
        r"\fscx100" in e.text
        and r"\fscx120" not in e.text
        and r"\fscx140" not in e.text
        for e in outside
    )
    inside = [e for e in events if e.start_time == 1000]
    assert any(r"\fscx120" in e.text for e in inside)


def test_native_keyframes_support_asymmetric_peak_and_hold():
    class Hold(Scaling):
        def configure(self):
            self.syllables.on_singing(
                scale=Keyframes(
                    Keyframe(0, 1),
                    Keyframe(0.2, 1.3),
                    Keyframe(0.65, 1.3),
                    Keyframe(1, 1),
                )
            )

    plan, _, _ = build(Hold())
    assert plan.dynamic is None
    a = plan.layers[0].animations[0]
    assert [p[0] for p in a.points] == [1000, 1280, 1910, 2400]
    assert a.scale_at(1500) == 1.3
    assert a.scale_at(2190) == pytest.approx(1 + 0.3 * (2400 - 2190) / 490)
    assert compile_layers(plan.layers).events


def test_curve_and_direct_lambda_return_same_sampled_values():
    rate = there_and_back(peak_at=0.2, return_at=0.65, rise=smooth)

    class Rate(Scaling):
        def configure(self):
            self.syllables.on_singing(scale=Transition(1, 1.3, rate=rate))

    class Function(Scaling):
        def configure(self):
            self.syllables.on_singing(scale=lambda p: 1 + 0.3 * rate(p))

    a, _, _ = build(Rate())
    b, _, _ = build(Function())
    left = prepare_sampling(a.layers, a.dynamic).evaluate()
    right = prepare_sampling(b.layers, b.dynamic).evaluate()
    assert [l.active_window for l in left] == [l.active_window for l in right]
    for x, y in zip(left, right, strict=True):
        assert (
            x.animations[0].peak_scale == pytest.approx(y.animations[0].peak_scale)
            if x.animations
            else not y.animations
        )


def test_short_syllable_rejects_reversed_absolute_keyframes():
    class Reversed(Scaling):
        def configure(self):
            self.syllables.on_singing(
                scale=Keyframes(
                    Keyframe(0, 1),
                    Keyframe(singing.start + 300, 1.3),
                    Keyframe(singing.end - 100, 1.3),
                    Keyframe(1, 1),
                )
            )

    with pytest.raises(ValueError, match="keyframe times must increase"):
        build(Reversed(), segments=(Segment(1000, 1200),))


def test_scale_conflicts_include_target_and_absolute_interval():
    class Conflict(Scaling):
        def configure(self):
            self.syllables.on_singing(pulse=1.2)
            self.syllables.animate(scale=1.3, during=(singing.start + 100, singing.end))

    with pytest.raises(
        ValueError, match=r"line/unit:0/text:0:1: scale conflict at 1100..2400 ms"
    ):
        build(Conflict())


def test_per_character_center_and_ruby_opt_out():
    class Individual(Scaling):
        def compose(self):
            yield Lyrics(Body(), Ruby(follow="none"), Halo())

        def configure(self):
            self.characters.on_singing(pulse=1.2)

    plan, _, _ = build(Individual())
    for layer in plan.layers:
        if layer.style.name == "ruby":
            assert not layer.animations
        else:
            assert layer.animations[0].pivot == (layer.box.center, layer.box.middle)


@pytest.mark.parametrize("keep", [False, True])
def test_zero_duration_native_scale_is_an_instant_switch(keep):
    class Instant(Scaling):
        def configure(self):
            self.syllables.on_singing(scale=Transition(1, 1.3), keep=keep)

    plan, _, _ = build(Instant(), segments=(Segment(1500, 1500),))
    events = compile_layers(plan.layers).events
    assert all(r"\fscx100" in e.text for e in events if e.end_time <= 1500)
    assert all(
        (r"\fscx130" if keep else r"\fscx100") in e.text
        for e in events
        if e.start_time >= 1500
    )


def test_static_source_does_not_run_scale_function():
    class Static(Scaling):
        def configure(self):
            self.syllables.on_singing(scale=lambda p: 1 / 0)

    plan, _, _ = build(Static(), segments=())
    assert plan.dynamic is None
    assert all(not l.animations for l in plan.layers)


def test_invalid_function_scale_is_diagnosed_at_sample_source():
    class Negative(Scaling):
        def configure(self):
            self.syllables.on_singing(scale=lambda p: -1)

    plan, _, _ = build(Negative())
    with pytest.raises(
        OutputCapabilityError, match="scale must be positive"
    ) as failure:
        prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert failure.value.origin.sources[0].item_id == "line"


def test_configurable_linear_return_curve_uses_native_keyframes():
    class Back(Scaling):
        def configure(self):
            self.syllables.on_singing(
                scale=Transition(
                    1, 1.3, rate=there_and_back(peak_at=0.2, return_at=0.65)
                )
            )

    plan, _, _ = build(Back())
    assert plan.dynamic is None
    assert plan.layers[0].animations[0].points == (
        (1000, 1),
        (1280, 1.3),
        (1910, 1.3),
        (2400, 1),
    )


def test_native_and_sampled_schedules_cannot_overlap_via_keep():
    class Conflict(Scaling):
        def configure(self):
            self.syllables.animate(
                scale=1.2, during=(singing.start, singing.start + 100), keep=True
            )
            self.syllables.animate(
                scale=lambda p: 1 + p * 0.1, during=(singing.start + 200, singing.end)
            )

    with pytest.raises(ValueError, match="scale conflict"):
        build(Conflict())


def test_nonoverlapping_native_and_sampled_scale_rules_share_one_evaluator():
    class Sequential(Scaling):
        def configure(self):
            self.syllables.animate(
                scale=Transition(1, 1.2), during=(singing.start, singing.start + 200)
            )
            self.syllables.animate(
                scale=lambda p: 1 + 0.2 * p, during=(singing.start + 400, singing.end)
            )

    plan, _, _ = build(Sequential())
    assert all(not layer.animations for layer in plan.layers)
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert sampled
    assert compile_layers(sampled).events


def test_character_iteration_selects_glyphs_within_a_single_unit():
    class Selected(Scaling):
        def compose(self):
            yield Lyrics(Body(), Halo())

        def configure(self):
            assert [c.text for c in self.characters] == ["A", "B"]
            assert len(self.syllables) == 1
            self.characters[1].on_singing(pulse=1.2)

    plan, _, _ = build(Selected())
    assert all(bool(layer.animations) == (layer.text == "B") for layer in plan.layers)


@pytest.mark.parametrize(
    "peak,hold", [(0, 0.5), (0.8, 0.4), (0.5, 1), (float("nan"), 0.5)]
)
def test_return_curve_rejects_invalid_time_relationships(peak, hold):
    with pytest.raises(ValueError):
        there_and_back(peak_at=peak, return_at=hold)


def test_nonlinear_keyframe_rates_are_deferred_and_keep_endpoint():
    class Curved(Scaling):
        def configure(self):
            self.syllables.on_singing(
                scale=Keyframes(
                    Keyframe(0, 1, rate=smooth), Keyframe(0.5, 1.2), Keyframe(1, 1.1)
                ),
                keep=True,
            )

    plan, _, _ = build(Curved())
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    final = [
        l for l in sampled if l.active_window.start_ms <= 2800 < l.active_window.end_ms
    ]
    assert final and all(l.animations[0].scale_at(2800) == 1.1 for l in final)


def test_zero_duration_keyframes_keep_the_actual_last_value():
    class Instant(Scaling):
        def configure(self):
            self.syllables.on_singing(
                scale=Keyframes(Keyframe(0, 1), Keyframe(0.5, 1.5), Keyframe(1, 1.2)),
                keep=True,
            )

    plan, _, _ = build(Instant(), segments=(Segment(1500, 1500),))
    final = [e for e in compile_layers(plan.layers).events if e.start_time >= 1500]
    assert final and all(r"\fscx120" in e.text for e in final)
