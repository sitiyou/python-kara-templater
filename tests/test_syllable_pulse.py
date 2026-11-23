"""Migrated composition behavior: source context, next-unit timing and release."""

from dataclasses import replace

import pytest

from examples.syllable_pulse import SyllablePulse
from kara_templater import (
    Document,
    Line,
    LyricAnimationContext,
    LyricRule,
    Style,
    Track,
    prepare_tracks,
)


def prepare(text=r"{\k40}A{\kt60\k80}B", *, end=2400):
    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    doc.records.append(Line(start_time=1000, end_time=end, text=text))
    track = Track(
        id="lyrics",
        preview=0.2,
        tail=0,
        effects=(LyricRule("syllable", "singing", SyllablePulse(peak=1.2)),),
    )
    return doc, track


def test_next_syllable_supplies_clock_without_changing_target_or_singing():
    doc, track = prepare()
    scene = prepare_tracks(doc, tracks=(track,))
    first, second = scene.lines[0].children
    assert scene.plans[0].placement.display.end == pytest.approx(2.6)
    expected = {1: 1, 1.2: 1.1, 1.4: 1.2, 1.5: 1.2, 1.6: 1.2, 2: 1.1, 2.4: 1, 3: 1}
    for time in (2.4, 1.2, 3, 1, 2, 1.4, 1.6, 1.5, 1.2):
        assert first.at(time).scale.x == pytest.approx(expected[time])
    assert second.at(2.5).scale.x == pytest.approx(1.1)
    source = scene.plans[0].source.lyrics.units
    for unit, expected_span in zip(source, ((1, 1.4), (1.6, 2.4)), strict=True):
        span = unit.segments[0].singing
        assert (span.start, span.end) == pytest.approx(expected_span)


def test_untimed_next_unit_uses_release_instead_of_skipping_ahead():
    doc, track = prepare(r"{\k40}A{\kt80} {\k40}B")
    scene = prepare_tracks(doc, tracks=(track,))
    targets = scene.lines[0].query("syllable")
    assert not targets[1].singing
    clip = scene.lines[0].children[0].animations[0]
    assert clip.duration == pytest.approx(0.6)


def test_zero_duration_uses_authored_release_and_factory_runs_once_per_target():
    doc, track = prepare(r"{\k0}A", end=1010)
    calls = []
    pulse = SyllablePulse()

    def factory(timing: LyricAnimationContext):
        calls.append(timing.target.id)
        return pulse(timing)

    track = replace(track, effects=(LyricRule("syllable", "singing", factory),))
    scene = prepare_tracks(doc, tracks=(track,))
    assert scene.plans[0].placement.display.end == pytest.approx(1.2)
    assert len(calls) == 1
    node = scene.lines[0].children[0]
    assert node.animations[0].duration == 0.2
    assert node.at(1.1).scale.x == 1
