from dataclasses import replace

import pytest

from kara_templater.animation import (
    CharacterTarget,
    HighlightEnter,
    Pulse,
    SegmentStart,
    plan_pulses,
)
from kara_templater.model import Box, LaidOutLine, LaidOutUnit, TextUnit
from kara_templater.timeline import (
    DisplayWindow,
    HighlightTrack,
    ProgressCurve,
    Region,
    SingingPass,
)

LAYOUT = LaidOutLine(
    Box(0, 10, 100, 20), (LaidOutUnit(TextUnit("ab"), Box(0, 10, 100, 20), ()),)
)
CHARS = (
    CharacterTarget("a", 0, Region(0, 20), 20),
    CharacterTarget("b", 0, Region(20, 100), 20),
)
TRACK = HighlightTrack("main", 0, (SingingPass(1000, 2000, Region(0, 100)),))
WINDOW = DisplayWindow(0, 4000)


def plan(pulse, *, tracks=(TRACK,), characters=CHARS, window=WINDOW, **kwargs):
    return plan_pulses(
        (pulse,),
        layout=LAYOUT,
        characters=characters,
        tracks=tracks,
        window=window,
        **kwargs,
    )


def test_unequal_character_widths_determine_trigger_times_and_durations():
    a, b = plan(Pulse.each_char()).animations
    assert (a.start_ms, a.end_ms) == (1000, 1200)
    assert (b.start_ms, b.end_ms) == (1200, 2000)


def test_three_modes_have_distinct_geometry():
    individual = plan(Pulse.simultaneous_chars(scale=2, duration_ms=1000)).animations
    group = plan(Pulse.whole_syllable(scale=2, duration_ms=1000)).animations
    assert [a.start_ms for a in individual] == [1000, 1000]
    assert individual[0].point_at(10, 20, 1500) == (10, 20)
    assert individual[1].point_at(60, 20, 1500) == (60, 20)
    assert group[0].point_at(10, 20, 1500) == (-30, 20)
    assert group[1].point_at(60, 20, 1500) == (70, 20)
    assert group[1].point_at(60, 20, 2000) == (60, 20)


def test_pauses_and_thresholds_follow_curve_not_equal_character_counts():
    curve = ProgressCurve(((0, 0), (0.2, 0.2), (0.6, 0.2), (1, 1)))
    track = replace(TRACK, passes=(replace(TRACK.passes[0], curve=curve),))
    assert plan(Pulse.each_char(), tracks=(track,)).animations[1].start_ms == 1200
    assert (
        plan(Pulse(trigger=HighlightEnter("center")), tracks=(track,))
        .animations[1]
        .start_ms
        == 1800
    )
    assert (
        plan(Pulse(trigger=HighlightEnter("complete")), tracks=(track,))
        .animations[0]
        .start_ms
        == 1200
    )


def test_syllable_and_segment_anchors_differ():
    track = replace(
        TRACK,
        passes=(
            SingingPass(1000, 1100, Region(0, 20)),
            SingingPass(1400, 1800, Region(20, 100)),
        ),
    )
    syllable = plan(
        Pulse.simultaneous_chars(duration_ms=100), tracks=(track,)
    ).animations
    segments = plan(
        Pulse(
            trigger=SegmentStart(), target="chars", pivot="each_center", duration_ms=100
        ),
        tracks=(track,),
    ).animations
    assert len(syllable) == 2
    assert [a.start_ms for a in segments] == [1000, 1400, 1000, 1400]
    # Arriving at the previous segment's right boundary must not trigger the
    # following character during the pause.
    chars = plan(Pulse.each_char(), tracks=(track,)).animations
    assert [(a.start_ms, a.end_ms) for a in chars] == [(1000, 1100), (1400, 1800)]


def test_multi_track_first_arrival_named_and_conflict():
    late = HighlightTrack("later", 0, (SingingPass(1100, 2100, Region(0, 100)),))
    assert {a.track_id for a in plan(Pulse(), tracks=(late, TRACK)).animations} == {
        "main"
    }
    assert {
        a.track_id
        for a in plan(
            Pulse(tracks="named", track_id="later"), tracks=(late, TRACK)
        ).animations
    } == {"later"}
    with pytest.raises(ValueError, match="scale conflict"):
        plan(Pulse(tracks="each"), tracks=(late, TRACK))
    # Simultaneous arrivals are deduplicated independent of input order.
    other = replace(TRACK, id="a-first")
    assert plan(Pulse(), tracks=(other, TRACK)) == plan(Pulse(), tracks=(TRACK, other))
    assert len(plan(Pulse(), tracks=(other, TRACK)).animations) == 2


def test_repeat_round_dedup_and_retrigger():
    track = replace(
        TRACK,
        passes=(*TRACK.passes, SingingPass(2500, 3500, Region(0, 100), round_id=1)),
    )
    assert len(plan(Pulse(), tracks=(track,)).animations) == 4
    assert len(plan(Pulse(retrigger=False), tracks=(track,)).animations) == 2
    with pytest.raises(ValueError, match="scale conflict"):
        plan(Pulse(duration_ms=2000), tracks=(track,))


def test_zero_duration_and_blank_targets():
    track = replace(TRACK, passes=(SingingPass(1000, 1000, Region(0, 100)),))
    result = plan(
        Pulse(),
        tracks=(track,),
        characters=(*CHARS, CharacterTarget("space", 0, Region(100, 110), 20, False)),
    )
    assert len(result.animations) == 2
    assert all(a.start_ms == a.end_ms == 1000 for a in result.animations)
    assert all(a.scale_at(1000) == 1 for a in result.animations)


def test_window_truncation_does_not_retime_animation():
    pulse = Pulse.whole_syllable(duration_ms=2000)
    result = plan(pulse, window=DisplayWindow(1500, 2200))
    assert len(result.diagnostics) == 2
    assert result.animations[0].start_ms == 1000
    assert result.animations[0].end_ms == 3000
    assert result.animations[0].scale_at(2000) == pytest.approx(1.1)
    assert plan(
        pulse, window=DisplayWindow(1500, 2200), overflow="extend"
    ).window == DisplayWindow(1000, 3000)


def test_multiple_effects_conflict_in_visible_window():
    with pytest.raises(ValueError, match="scale conflict"):
        plan_pulses(
            (Pulse(), Pulse.whole_syllable()),
            layout=LAYOUT,
            characters=CHARS,
            tracks=(TRACK,),
            window=DisplayWindow(0, 4000),
        )


def test_invalid_track_reference():
    with pytest.raises(ValueError, match="unknown track"):
        plan(Pulse(tracks="named", track_id="missing"))
