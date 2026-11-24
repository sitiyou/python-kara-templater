from dataclasses import replace

import pytest

from kara_templater import Highlight, HighlightPass, StatePatch, TimeSpan
from kara_templater.model import (
    Box,
    LaidOutLine,
    LaidOutSegment,
    LaidOutUnit,
    Segment,
    TextUnit,
)
from kara_templater.timeline import (
    DisplayWindow,
    ProgressCurve,
    Region,
    union_regions,
)


@pytest.mark.parametrize(
    "start,end", [(-1, 10), (1, 1), (2, 1), (0.5, 10), (False, 10)]
)
def test_invalid_display_window(start, end):
    with pytest.raises(ValueError):
        DisplayWindow(start, end)


def test_piecewise_speed_pause_and_earliest_arrival():
    curve = ProgressCurve(((0, 0), (0.2, 0.4), (0.6, 0.4), (1, 1)))
    singing = HighlightPass(
        TimeSpan(1, 2), Region(20, 120), rate=curve.at, inverse_rate=curve.arrival
    )
    assert singing.front(1.1) == pytest.approx(40)
    assert singing.front(1.4) == pytest.approx(60)
    assert singing.arrival(60) == pytest.approx(1.2)
    assert singing.arrival(90) == pytest.approx(1.8)
    assert singing.arrival(10) is None
    assert (
        ProgressCurve.two_stage(time_fraction=0.25, progress_fraction=0.5).at(0.25)
        == 0.5
    )

@pytest.mark.parametrize("controls", [
    (.17, .17, 0, 1), (0, 1, 0, 1), (1, 0, 1, 0),
    (1, 0, 0, 1), (0, 1, 1, 0), (.2, .2, .8, .8),
])
def test_cubic_bezier_progress_matches_parametric_reference(controls):
    x1, y1, x2, y2 = controls
    curve = ProgressCurve.cubic_bezier(*controls)
    for index in range(1001):
        s = index / 1000
        b, c, d = 3 * (1 - s)**2 * s, 3 * (1 - s) * s**2, s**3
        time = b*x1 + c*x2 + d
        progress = b*y1 + c*y2 + d
        assert curve.at(time) == pytest.approx(progress, abs=.000100001)


@pytest.mark.parametrize("control", [float("nan"), float("inf"), -.1, 1.1, True])
def test_cubic_bezier_rejects_unbounded_controls(control):
    with pytest.raises(ValueError, match="Bézier control"):
        ProgressCurve.cubic_bezier(.17, control, 0, 1)


@pytest.mark.parametrize(
    "knots",
    [
        ((0, 0), (1, 0.9)),
        ((0, 0), (0, 0.5), (1, 1)),
        ((0, 0), (0.5, 0.8), (0.7, 0.2), (1, 1)),
        ((0, 0), (0.5, float("nan")), (1, 1)),
    ],
)
def test_invalid_curves(knots):
    with pytest.raises(ValueError):
        ProgressCurve(knots)


def test_zero_duration_and_empty_region():
    singing = HighlightPass(TimeSpan(0.1, 0.1), Region(20, 120))
    assert singing.front(0.099) == 20
    assert singing.front(0.1) == 120
    assert singing.arrival(70) == 0.1
    assert HighlightPass(TimeSpan(0.1, 0.2), Region(20, 20)).arrival(20) is None
    track = Highlight("instant", 0, (singing,), StatePatch())
    assert track.regions(0.1) == (Region(20, 120),)


def test_disjoint_regions_pause_repetition_and_exit():
    passes = (
        HighlightPass(TimeSpan(0.1, 0.2), Region(0, 20)),
        HighlightPass(TimeSpan(0.3, 0.4), Region(40, 60)),
        HighlightPass(TimeSpan(0.6, 0.8), Region(0, 20), round=1),
    )
    track = Highlight("a", 0, passes, StatePatch())
    assert track.regions(0.05) == ()
    assert track.regions(0.25) == (Region(0, 20),)
    assert [r.left for r in track.regions(0.35)] == [0, 40]
    assert [r.right for r in track.regions(0.35)] == pytest.approx([20, 50])
    assert track.regions(0.7) == (Region(0, 20), Region(40, 60))
    assert replace(track, repeat="reset").regions(0.7)[0].right == pytest.approx(10)
    assert replace(track, end="hide").regions(0.8) == ()
    assert union_regions((Region(0, 10), Region(5, 20), Region(40, 60))) == (
        Region(0, 20),
        Region(40, 60),
    )


def test_overlapping_passes_require_separate_highlights():
    with pytest.raises(ValueError, match="nonoverlapping"):
        Highlight(
            "a",
            0,
            (
                HighlightPass(TimeSpan(0, 0.1), Region(0, 20)),
                HighlightPass(TimeSpan(0.05, 0.2), Region(30, 50)),
            ),
            StatePatch(),
        )


def test_layout_mapping_preserves_ruby_partition_and_static_units():
    segments = (Segment(100, 200, "ab"), Segment(300, 400, "c"))
    layout = LaidOutLine(
        Box(0, 0, 90, 20),
        (
            LaidOutUnit(
                TextUnit("word", segments),
                Box(0, 0, 90, 20),
                (
                    LaidOutSegment(segments[0], 0, 60, None),
                    LaidOutSegment(segments[1], 60, 90, None),
                ),
            ),
            LaidOutUnit(TextUnit(" "), Box(90, 0, 10, 20), ()),
        ),
    )
    tracks = tuple(
        Highlight(
            str(index),
            index,
            tuple(
                HighlightPass(
                    TimeSpan(part.source.start_ms / 1000, part.source.end_ms / 1000),
                    Region(part.left, part.right),
                )
                for part in unit.segments
            ),
            StatePatch(),
        )
        for index, unit in enumerate(layout.units)
        if unit.segments
    )
    assert len(tracks) == 1
    assert tracks[0].regions(0.25) == (Region(0, 60),)
    assert len(tracks[0].regions(0.35)) == 1
    assert tracks[0].regions(0.35)[0].left == 0
    assert tracks[0].regions(0.35)[0].right == pytest.approx(75)


def test_unit_order_is_spatial_not_temporal_with_adjacent_and_instant_segments():
    schedules = (
        (Segment(1000, 1100), Segment(1100, 1300)),
        (Segment(700, 1200),),
        (Segment(900, 900),),
    )
    units = tuple(
        LaidOutUnit(
            TextUnit(str(i), segments),
            Box(i * 100, 0, 100, 20),
            tuple(
                LaidOutSegment(
                    s,
                    i * 100 + j * 100 / len(segments),
                    i * 100 + (j + 1) * 100 / len(segments),
                    None,
                )
                for j, s in enumerate(segments)
            ),
        )
        for i, segments in enumerate(schedules)
    )
    tracks = tuple(
        Highlight(
            str(index),
            index,
            tuple(
                HighlightPass(
                    TimeSpan(part.source.start_ms / 1000, part.source.end_ms / 1000),
                    Region(part.left, part.right),
                )
                for part in unit.segments
            ),
            StatePatch(),
        )
        for index, unit in enumerate(units)
    )
    assert [t.unit for t in tracks] == [0, 1, 2]
    # The later written unit sings first; both are active at 1050 ms.
    assert tracks[0].regions(1.05) == (Region(0, 25),)
    assert tracks[1].regions(1.05) == (Region(100, 170),)
    assert tracks[0].regions(1.1) == (Region(0, 50),)
    assert len(tracks[0].regions(1.2)) == 1
    assert tracks[0].regions(1.2)[0].left == 0
    assert tracks[0].regions(1.2)[0].right == pytest.approx(75)
    assert tracks[2].regions(0.899) == ()
    assert tracks[2].regions(0.9) == (Region(200, 300),)
