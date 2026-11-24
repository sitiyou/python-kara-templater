"""Custom relative motion and built-ins share capture, pivots and source clocks."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    DriftOut,
    FadeOut,
    Lifetime,
    Line,
    LyricLine,
    LyricRule,
    ScalePulse,
    Scene,
    Style,
    Transform,
    Vec2,
    VisualState,
    layout_document_lyrics,
    smooth_rate,
)


def test_relative_transform_preserves_pivot_and_incoming_paint():
    base = VisualState(
        position=Vec2(40, 60), scale=Vec2(2, 3), rotation=30,
        skew=Vec2(0.2, 0.1), opacity=0.4, blur=8,
    )
    pivot = Vec2(12, 18)
    motion = Transform(
        offset=lambda p: Vec2(20 * p, -30 * p),
        scale=lambda p: Vec2(1 + p, 1 - p / 2),
        rotation=lambda p: 45 * p,
        opacity=lambda p: 1 - p,
        pivot=pivot,
    )
    for p in (1, 0.2, 0, 0.8, 0.2):
        state = motion.sample(base, p)
        fixed = base.transform.apply(pivot) + Vec2(20 * p, -30 * p)
        actual = state.transform.apply(pivot)
        assert actual.x == pytest.approx(fixed.x)
        assert actual.y == pytest.approx(fixed.y)
        assert state.scale == Vec2(2 * (1 + p), 3 * (1 - p / 2))
        assert state.opacity == pytest.approx(0.4 * (1 - p))
        assert state.blur == 8
        assert state.fill == base.fill


def test_custom_fade_matches_builtin_without_writing_geometry():
    custom = Transform(opacity=lambda p: 1 - smooth_rate(p))
    builtin = FadeOut(smooth_rate)
    assert custom.channels == builtin.channels == frozenset(("opacity",))
    assert Transform().channels == frozenset()
    for opacity in (0, 0.35, 1):
        base = VisualState(opacity=opacity, position=Vec2(12, 34))
        for p in (1, 0.1, 0.8, 0):
            assert custom.sample(base, p) == builtin.sample(base, p)


def test_builtin_drift_matches_custom_composition_with_transparent_scaled_input():
    base = VisualState(scale=Vec2(1.5, 2), opacity=0.35, rotation=20)
    pivot = Vec2(20, 10)
    custom = Transform(
        offset=lambda p: Vec2(12, -36) * smooth_rate(p),
        scale=lambda p: 1 + (0.96 - 1) * smooth_rate(p),
        opacity=lambda p: 1 - smooth_rate(p),
        pivot=pivot,
    )
    builtin = DriftOut(offset=Vec2(12, -36), pivot=pivot)
    assert custom.channels == builtin.channels
    for p in (1, 0.37, 0, 0.8):
        assert custom.sample(base, p) == builtin.sample(base, p)


def test_pulse_has_eased_asymmetric_phases_and_exact_endpoints():
    pulse = ScalePulse(peak=1.2, peak_at=0.4)
    base = VisualState(scale=Vec2(2, 3))
    assert pulse.sample(base, 0) == pulse.sample(base, 1) == base
    peak = pulse.sample(base, 0.4).scale
    assert (peak.x, peak.y) == pytest.approx((2.4, 3.6))
    # Quarter of attack: smoothstep is 0.15625, not linear 0.25.
    assert pulse.sample(base, 0.1).scale.x == pytest.approx(2.0625)
    assert pulse.sample(base, 0.85).scale.x == pytest.approx(2.0625)
    assert pulse.sample(base, 0.0001).scale.x - 2 < 1e-6


@pytest.mark.parametrize("peak_at", (0, 1, -0.5, float("nan")))
def test_pulse_rejects_missing_attack_or_release(peak_at):
    with pytest.raises(ValueError):
        ScalePulse(peak_at=peak_at)


def lyric(text=r"{\k25}A{\kt50\k25}#"):
    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    doc.records.append(Line(text=text, start_time=1000, end_time=2000))
    layout = layout_document_lyrics(
        doc, len(doc.records) - 1, id="line", display=Lifetime(0, 3)
    )
    return doc, LyricLine.from_layout(layout)


def test_after_timing_waits_for_last_repeat_and_respects_copy_delay():
    doc, line = lyric()
    line = line.copy(id="delayed", delay=0.2)
    animation = Transform(opacity=lambda p: 1 - p)
    bound = line.bind(LyricRule(
        "character", "after_timing", animation, offset=0.1, duration=0.5,
    ))
    evaluator = Scene(doc).add(bound).evaluator()
    target = bound.query("character")[0].node_id
    # Last source end 1.75 + copy delay .2 + hold .1 = 2.05.
    for time, alpha in ((2.3, 0.5), (1.4, 1), (2.55, 0), (2.05, 1)):
        assert evaluator.at(target, time).opacity == pytest.approx(alpha)
    assert line.query("character")[0].timing[-1].end == 1.75


def test_after_timing_segment_selection_can_trigger_each_repeat():
    _, line = lyric()
    bound = line.bind(LyricRule(
        "segment", "after_timing", ScalePulse(), duration=0.1,
    ))
    assert [clip.start for clip in bound.children[0].animations] == [1.25, 1.75]


def test_after_timing_handles_zero_length_and_missing_intervals():
    _, line = lyric(r"{\k0}A")
    rule = LyricRule("character", "after_timing", FadeOut(), duration=0.2)
    assert line._resolve((rule,))[0].at == 1
    absent = replace(line, targets=tuple(replace(t, timing=()) for t in line.targets))
    assert absent._resolve((rule,)) == ()
    with pytest.raises(ValueError, match="explicit duration"):
        LyricRule("character", "after_timing", FadeOut())
    factory = LyricRule("character", "after_timing", lambda timing: FadeOut())
    with pytest.raises(ValueError, match="explicit duration"):
        line.bind(factory)
