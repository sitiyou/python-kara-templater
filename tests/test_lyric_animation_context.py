"""Factories see each resolved interval without rewriting semantic source clocks."""

from dataclasses import replace

import pytest

from examples.lyric_pulse_drift import pulse
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    Line,
    LyricAnimationContext,
    LyricHighlights,
    LyricRule,
    ScalePulse,
    StatePatch,
    Timeline,
    TimeSpan,
    Track,
    build_lyric_scene,
    smooth_rate,
)


def test_unequal_repeats_choose_independent_peaks_and_preserve_aliases():
    doc = Document.create(width=640, height=360)
    doc.records.append(Line(start_time=1000, end_time=3000,
                            text=r"{\k25}A{\kt50\k100}#{\k0}B"))
    original = doc.dumps()
    calls = []

    def adaptive(timing: LyricAnimationContext):
        calls.append(timing)
        return pulse(timing)

    scene = build_lyric_scene(doc, tracks=(Track(id="main", effects=(
        lambda line: line.schedule(LyricRule("character", "timing", adaptive)),
        LyricHighlights.from_timing(StatePatch(fill=CYAN)),
    )),))
    a, b = scene.lines[0].query("character")
    assert [call.duration for call in calls] == [0.25, 1, 0]
    assert calls[0].target.timing == calls[1].target.timing == a.timing
    assert [call.interval for call in calls] == [
        TimeSpan(1, 1.25), TimeSpan(1.5, 2.5), TimeSpan(2.5, 2.5),
    ]
    evaluator = scene.evaluator()
    for start, duration in ((1, 0.25), (1.5, 1)):
        expected = 1 + 0.06 * smooth_rate(min(1, duration / 0.6))
        for name in (a.node_id, *a.aliases):
            assert evaluator.at(name, start + duration * 0.42).scale.x == pytest.approx(expected)
            assert evaluator.at(name, start + duration).scale.x == 1
    assert evaluator.at(b.node_id, 2.5).scale.x == 1
    assert len(calls) == 3  # Seeking never reruns author factories.
    assert doc.dumps() == original


def test_override_and_custom_intervals_are_the_factory_clock():
    doc = Document.create(width=640, height=360)
    doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    calls = []

    def choose(timing: LyricAnimationContext):
        calls.append((timing.interval, timing.duration, timing.target.timing))
        return ScalePulse(peak=1.1)

    def anchors(line, target):
        return (TimeSpan(0.5, 0.6), TimeSpan(2.5, 3))

    scene = build_lyric_scene(doc, tracks=(Track(id="main", effects=(
        LyricRule("character", anchors, choose, duration=0.2, offset=0.1),
    )),))
    target = scene.lines[0].query("character")[0]
    assert [(span, duration) for span, duration, _ in calls] == [
        (TimeSpan(0.5, 0.6), 0.2), (TimeSpan(2.5, 3), 0.2),
    ]
    assert all(source == target.timing for _, _, source in calls)
    for peak in (0.7, 2.7):
        assert scene.evaluator().at(target.node_id, peak).scale.x == pytest.approx(1.1)


def test_display_factory_can_return_sequence_without_invented_interval():
    doc = Document.create(width=640, height=360)
    doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    calls = []

    def entrance(timing: LyricAnimationContext):
        calls.append(timing)
        assert timing.interval is None
        with pytest.raises(ValueError, match="no requested duration"):
            _ = timing.duration
        return Timeline().play(FadeIn(), duration=0.3).animation

    scene = build_lyric_scene(doc, tracks=(Track(id="main", preview=0, effects=(
        LyricRule("line", "enter", entrance),
    )),))
    assert len(calls) == 1
    assert scene.lines[0].lifetime.start == pytest.approx(0.7)
    assert scene.evaluator().at(scene.lines[0].id, 0.85).opacity == pytest.approx(0.5)
    assert replace(calls[0], requested_duration=0.4).duration == 0.4


def test_delayed_copy_context_and_missing_intervals():
    from kara_templater import Scene

    doc = Document.create(width=640, height=360)
    doc.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}A"))
    line = build_lyric_scene(doc, tracks=(Track(id="main"),)).lines[0]
    calls = []

    def choose(timing: LyricAnimationContext):
        calls.append(timing)
        return ScalePulse(peak=1.1)

    copied = line.copy(id="copy", delay=0.3)
    bound = copied.bind(LyricRule("character", "timing", choose))
    target = bound.query("character")[0]
    assert calls[0].interval == TimeSpan(1.3, 2.3)
    assert calls[0].duration == pytest.approx(1)
    assert calls[0].target.timing == line.query("character")[0].timing
    assert Scene(doc).add(bound).evaluator().at(target.node_id, 1.8).scale.x == pytest.approx(1.1)
    empty = replace(line, targets=tuple(replace(item, timing=()) for item in line.targets))
    empty.bind(LyricRule("character", "timing", choose))
    assert len(calls) == 1
