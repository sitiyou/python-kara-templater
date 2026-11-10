from dataclasses import replace

import pytest

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
    EdgeSweep,
    HighlightTrack,
    ProgressCurve,
    Region,
    SingingPass,
    tracks_from_layout,
    union_regions,
)


@pytest.mark.parametrize(
    "start,end", [(-1, 10), (1, 1), (2, 1), (0.5, 10), (False, 10)]
)
def test_invalid_display_window(start, end):
    with pytest.raises(ValueError):
        DisplayWindow(start, end)


def test_body_timing_and_character_arrivals_ignore_decorations():
    singing = SingingPass(1000, 2000, Region(100, 300))
    baseline = [singing.position_at(t) for t in (900, 1000, 1250, 1500, 2000)]
    for paint, edges in (
        (Region(100, 300), EdgeSweep()),
        (Region(-500, 900), EdgeSweep(120, 250, 400)),
    ):
        assert edges.position_at(singing, paint, 1250) == 150
        assert edges.position_at(singing, paint, 1500) == 200
        assert singing.arrival(150) == 1250
        assert [
            singing.position_at(t) for t in (900, 1000, 1250, 1500, 2000)
        ] == baseline
    edges = EdgeSweep(10, 200, 300)
    assert edges.position_at(singing, Region(80, 320), 800) == 70
    assert edges.position_at(singing, Region(80, 320), 900) == 85
    assert edges.position_at(singing, Region(80, 320), 1000) == 100
    assert edges.position_at(singing, Region(80, 320), 2000) == 300
    assert edges.position_at(singing, Region(80, 320), 2300) == 330


def test_piecewise_speed_pause_and_earliest_arrival():
    curve = ProgressCurve(((0, 0), (0.2, 0.4), (0.6, 0.4), (1, 1)))
    singing = SingingPass(1000, 2000, Region(20, 120), curve)
    assert singing.position_at(1100) == pytest.approx(40)
    assert singing.position_at(1400) == pytest.approx(60)
    assert singing.arrival(60) == pytest.approx(1200)
    assert singing.arrival(90) == pytest.approx(1800)
    assert singing.arrival(10) is None
    assert (
        ProgressCurve.two_stage(time_fraction=0.25, progress_fraction=0.5).at(0.25)
        == 0.5
    )


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
    singing = SingingPass(100, 100, Region(20, 120))
    assert singing.position_at(99) == 20
    assert singing.position_at(100) == 120
    assert singing.arrival(70) == 100
    assert SingingPass(100, 200, Region(20, 20)).arrival(20) is None
    track = HighlightTrack("instant", 0, (singing,))
    assert track.regions_at(100) == (Region(20, 120),)


def test_disjoint_regions_pause_repetition_and_exit():
    passes = (
        SingingPass(100, 200, Region(0, 20)),
        SingingPass(300, 400, Region(40, 60)),
        SingingPass(600, 800, Region(0, 20), round_id=1),
    )
    track = HighlightTrack("a", 0, passes)
    assert track.regions_at(50) == ()
    assert track.regions_at(250) == (Region(0, 20),)
    assert track.regions_at(350) == (Region(0, 20), Region(40, 50))
    assert track.regions_at(700) == (Region(0, 20), Region(40, 60))
    assert replace(track, repeat="reset").regions_at(700) == (Region(0, 10),)
    assert replace(track, end_behavior="hide").regions_at(800) == ()
    assert union_regions((Region(0, 10), Region(5, 20), Region(40, 60))) == (
        Region(0, 20),
        Region(40, 60),
    )


def test_repeated_region_and_overlapping_time_require_explicit_models():
    with pytest.raises(ValueError, match="round_id"):
        HighlightTrack(
            "a",
            0,
            (SingingPass(0, 100, Region(0, 20)), SingingPass(100, 200, Region(0, 20))),
        )
    with pytest.raises(ValueError, match="separate tracks"):
        HighlightTrack(
            "a",
            0,
            (SingingPass(0, 100, Region(0, 20)), SingingPass(50, 200, Region(30, 50))),
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
    tracks = tracks_from_layout(layout)
    assert len(tracks) == 1
    assert tracks[0].regions_at(250) == (Region(0, 60),)
    assert tracks[0].regions_at(350) == (Region(0, 75),)


@pytest.mark.parametrize(
    "kwargs", [{"padding_px": -1}, {"lead_ms": 1.5}, {"tail_ms": -1}]
)
def test_edge_validation(kwargs):
    with pytest.raises(ValueError):
        EdgeSweep(**kwargs)


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
    tracks = tracks_from_layout(LaidOutLine(Box(0, 0, 300, 20), units))
    assert [t.unit_index for t in tracks] == [0, 1, 2]
    # The later written unit sings first; both are active at 1050 ms.
    assert tracks[0].regions_at(1050) == (Region(0, 25),)
    assert tracks[1].regions_at(1050) == (Region(100, 170),)
    assert tracks[0].regions_at(1100) == (Region(0, 50),)
    assert tracks[0].regions_at(1200) == (Region(0, 75),)
    assert tracks[2].regions_at(899) == ()
    assert tracks[2].regions_at(900) == (Region(200, 300),)
