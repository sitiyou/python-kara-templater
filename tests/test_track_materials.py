import pytest
from test_tracks import build, item
from track_helpers import compile_tracks

from examples._lyrics import document
from kara_templater import (
    BLUE,
    CYAN,
    RED,
    WHITE,
    Animate,
    Animation,
    AnimationContext,
    Blur,
    Body,
    Color,
    ColorKeyframe,
    ColorKeyframes,
    ColorTransition,
    Contextual,
    Display,
    Envelope,
    Keyframe,
    Keyframes,
    LineMatch,
    On,
    OutputCapabilityError,
    Overlay,
    PaintBounds,
    PaintStyle,
    SampleContext,
    Sequence,
    SingingPulseAnimation,
    Syllable,
    TextStyle,
    Track,
    display,
    on,
    prepare_sampling,
    there_and_back,
)


def track_for(action, *, overlay=None):
    return Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(
                fill=WHITE,
                stroke_width=2,
                blur=Blur(color=WHITE, radius=2, width=3, opacity=0.8),
            )
        ),
        overlay=overlay,
        animations=(On(Syllable.Singing, action),),
    )


def value_at(plan, time):
    layer = plan.layers[0]
    assert plan.dynamic is not None
    return plan.dynamic.function(
        SampleContext(time, 0.5, layer.window, layer.animation_id, 0)
    )


def test_color_numeric_and_blur_animation_reach_sampled_paint():
    plan = build(
        track_for(
            Animate(
                fill=(RED, BLUE),
                stroke=(WHITE, CYAN),
                stroke_width=(2, 6),
                blur_radius=(2, 10),
                blur_width=(3, 7),
                blur_opacity=(0.8, 0.4),
                blur_color=(WHITE, RED),
            )
        )
    )
    value = value_at(plan, 1500)
    assert value.fill == Color(128, 0, 128)
    assert value.stroke == Color(128, 255, 255)
    assert value.stroke_width == 4
    assert value.glow_blur == 6 and value.glow_width == 5
    assert value.glow_opacity == pytest.approx(0.6)
    assert value.glow_color == Color(255, 128, 128)
    assert value_at(plan, 999).fill is None
    assert value_at(plan, 2000).fill is None
    assert plan.dynamic is not None
    sampled = prepare_sampling(plan.layers, plan.dynamic, max_events=10000).evaluate()
    at = next(
        layer
        for layer in sampled
        if layer.active_window is not None
        and layer.active_window.start_ms <= 1520 < layer.active_window.end_ms
    )
    expected = value_at(plan, 1520)
    assert at.paint.fill == expected.fill
    assert at.paint.border == expected.stroke_width
    assert at.paint.glow is not None and at.paint.glow.blur == expected.glow_blur
    assert at.paint.glow.color == expected.glow_color


def test_material_envelope_returns_to_target_base_and_contributes_release():
    action = Animate(blur_radius=Envelope(peak=10, attack=100, release=200))
    plan = build(track_for(action))
    assert value_at(plan, 1050).glow_blur == pytest.approx(6)
    assert value_at(plan, 1500).glow_blur == 10
    assert value_at(plan, 2100).glow_blur == pytest.approx(6)
    assert value_at(plan, 2200).glow_blur is None
    sequence = On(Syllable.Singing, Sequence(action, Animate(fill=RED, duration=100)))
    assert [rule.during for rule in sequence.bind(AnimationContext(item()))] == [
        (1000, 2200),
        (2200, 2300),
    ]


def test_sweep_and_material_writes_require_explicit_override():
    overlay = Overlay(style=PaintStyle(fill=BLUE))
    with pytest.raises(OutputCapabilityError, match="conflicts with Sweep"):
        build(track_for(Animate(fill=RED), overlay=overlay))
    plan = build(track_for(Animate(fill=RED, compose="override"), overlay=overlay))
    assert value_at(plan, 1500).fill == RED
    # An inherited property can animate while another property is swept.
    assert (
        value_at(
            build(track_for(Animate(blur_radius=(2, 10)), overlay=overlay)), 1500
        ).glow_blur
        == 6
    )


def test_material_conflicts_do_not_depend_on_silent_last_writer():
    track = track_for(Animate(fill=RED))
    track.animations += (On(Syllable.Singing, Animate(fill=BLUE)),)
    with pytest.raises(OutputCapabilityError, match="material animation conflict"):
        build(track)
    track.animations = (
        track.animations[0],
        On(Syllable.Singing, Animate(fill=BLUE, compose="override")),
    )
    assert value_at(build(track), 1500).fill == BLUE


def test_geometry_callbacks_need_a_bound_and_are_checked_during_sampling():
    with pytest.raises(ValueError, match="PaintBounds"):
        build(track_for(Animate(blur_radius=lambda p: 2 + 8 * p)))
    plan = build(
        track_for(
            Animate(blur_radius=lambda p: 2 + 8 * p, bounds=PaintBounds(blur_radius=10))
        )
    )
    assert value_at(plan, 1500).glow_blur == 6
    with pytest.raises(ValueError, match="base style"):
        build(
            track_for(
                Animate(blur_radius=lambda p: p, bounds=PaintBounds(blur_radius=1))
            )
        )
    bad = build(
        track_for(Animate(blur_width=lambda p: 100, bounds=PaintBounds(blur_width=10)))
    )
    assert bad.dynamic is not None
    with pytest.raises(OutputCapabilityError, match="paint bound"):
        prepare_sampling(bad.layers, bad.dynamic).evaluate()
    with pytest.raises(ValueError, match="known animation"):
        build(
            track_for(
                Animate(stroke_width=(2, 20), bounds=PaintBounds(stroke_width=10))
            )
        )


def test_builtin_rates_allow_automatic_geometry_bounds():
    plan = build(track_for(Animate(blur_radius=(2, 10), rate=there_and_back())))
    assert value_at(plan, 1250).glow_blur == 6
    assert value_at(plan, 1500).glow_blur == 10
    assert plan.dynamic is not None and plan.dynamic.max_glow_blur == 10


def test_geometry_bounds_expand_sweep_domains_without_retiming():
    overlay = Overlay(style=PaintStyle(fill=BLUE))
    plain = build(track_for(Animate(opacity=1), overlay=overlay))
    wide = build(
        track_for(
            Animate(blur_radius=(2, 30), blur_width=(3, 20), stroke_width=(2, 60)),
            overlay=overlay,
        )
    )
    plain_left = min(
        span.start.left for layer in plain.layers for span in (layer.clips or ())
    )
    wide_left = min(
        span.start.left for layer in wide.layers for span in (layer.clips or ())
    )
    assert wide_left < plain_left - 100
    assert {
        (span.start_ms, span.end_ms)
        for layer in wide.layers
        for span in (layer.clips or ())
    } == {
        (span.start_ms, span.end_ms)
        for layer in plain.layers
        for span in (layer.clips or ())
    }


def test_color_keyframes_keep_source_clock_when_output_extends():
    source = item(window=(0, 2000))
    track = track_for(Animate(fill=WHITE))
    track.animations = (
        On(
            Display.Start,
            Animate(
                fill=ColorKeyframes(
                    ColorKeyframe(display.start, RED),
                    ColorKeyframe(0.5, WHITE),
                    ColorKeyframe(display.end, BLUE),
                ),
                duration=2000,
                keep=True,
            ),
        ),
        SingingPulseAnimation(extend_display=True),
    )
    plan = build(track, source)
    assert value_at(plan, 1000).fill == WHITE
    assert value_at(plan, 2100).fill == BLUE


def test_numeric_keyframes_and_contextual_material_values():
    plan = build(
        track_for(
            Animate(
                blur_radius=Keyframes(
                    Keyframe(0, 2), Keyframe(0.5, 10), Keyframe(1, 2)
                ),
                stroke_width=Contextual(lambda context: 2 + context.progress * 4),
                bounds=PaintBounds(stroke_width=6),
            )
        )
    )
    assert value_at(plan, 1500).glow_blur == 10
    assert value_at(plan, 1500).stroke_width == 4


def test_material_callbacks_are_not_evaluated_before_render_preflight():
    calls = []

    def color_at(progress):
        calls.append(progress)
        return RED

    def cancel(estimate):
        assert estimate.target_samples > 0
        assert not calls
        raise RuntimeError("cancel")

    with pytest.raises(RuntimeError, match="cancel"):
        compile_tracks(
            document(fontname="DejaVu Sans", text="AB"),
            tracks=(track_for(Animate(fill=color_at)),),
            on_estimate=cancel,
        )
    assert calls == []


def test_color_callback_type_and_rate_domain_are_checked():
    bad = build(track_for(Animate(fill=lambda p: 3)))  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="return Color"):
        value_at(bad, 1500)
    with pytest.raises(ValueError, match="0..1"):
        ColorTransition(RED, BLUE, rate=lambda p: 2)(0.5)


def test_blur_animation_cannot_silently_target_disabled_blur():
    track = Track(
        source=LineMatch(),
        animations=(On(Syllable.Singing, Animate(blur_radius=(0, 10))),),
    )
    with pytest.raises(ValueError, match="enabled Blur"):
        build(track)


def test_material_event_handler_retains_regular_animation_composition():
    class Accent(Animation):
        @on(Syllable.Singing)
        def accent(self, event: Syllable.Singing) -> Animate:
            return Animate(
                event.target, fill=ColorTransition(RED, BLUE), scale=Envelope(peak=1.1)
            )

    track = track_for(Animate(fill=WHITE))
    track.animations = (Accent(),)
    plan = build(track)
    assert value_at(plan, 1500).fill == Color(128, 0, 128)


def test_numeric_material_keyframe_anchors_remain_original_after_extension():
    source = item(window=(0, 2000))
    track = track_for(Animate(fill=WHITE))
    track.animations = (
        On(
            Display.Start,
            Animate(
                stroke_width=Keyframes(
                    Keyframe(display.start, 2), Keyframe(display.end, 6)
                ),
                duration=2000,
            ),
        ),
        SingingPulseAnimation(extend_display=True),
    )
    plan = build(track, source)
    assert value_at(plan, 1000).stroke_width == 4
