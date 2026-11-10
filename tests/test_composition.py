from dataclasses import replace

import pytest

from kara_templater.composition import (
    Color,
    Glow,
    Paint,
    TrackPaint,
    compose_highlights,
)
from kara_templater.timeline import HighlightTrack, Region, SingingPass

RED = Paint(Color.hex("#ff0000"))
BLUE = Paint(Color.hex("#0000ff"))
A = HighlightTrack("a", 0, (SingingPass(100, 200, Region(0, 100)),))
B = HighlightTrack("b", 0, (SingingPass(100, 200, Region(50, 150)),))


def test_union_paints_overlap_once_and_does_not_fill_gaps():
    layers = (TrackPaint(A, RED), TrackPaint(B, RED))
    result = compose_highlights(layers, 200, overlap="union")
    assert [(r.region, r.paints) for r in result] == [(Region(0, 150), (RED,))]
    result = compose_highlights(layers, 125, overlap="union")
    assert [r.region for r in result] == [Region(0, 25), Region(50, 75)]
    with pytest.raises(ValueError, match="identical"):
        compose_highlights((layers[0], TrackPaint(B, BLUE)), 200, overlap="union")


def test_priority_hides_then_reveals_lower_track():
    layers = (TrackPaint(A, RED), TrackPaint(replace(B, end_behavior="hide"), BLUE, 10))
    result = compose_highlights(layers, 175, overlap="priority")
    assert [(r.region, r.paints) for r in result] == [
        (Region(0, 50), (RED,)),
        (Region(50, 125), (BLUE,)),
    ]
    result = compose_highlights(layers, 200, overlap="priority")
    assert [(r.region, r.paints) for r in result] == [(Region(0, 100), (RED,))]
    assert compose_highlights(
        layers[::-1], 175, overlap="priority"
    ) == compose_highlights(layers, 175, overlap="priority")


def test_layered_opacity_is_intentional_and_order_is_explicit():
    translucent = replace(RED, opacity=0.5)
    layers = (TrackPaint(A, translucent, 10), TrackPaint(B, BLUE, 20))
    result = compose_highlights(layers, 200, overlap="layer")
    assert [(r.region, r.paints) for r in result] == [
        (Region(0, 50), (translucent,)),
        (Region(50, 100), (translucent, BLUE)),
        (Region(100, 150), (BLUE,)),
    ]
    with pytest.raises(ValueError, match="distinct priorities"):
        compose_highlights(
            (TrackPaint(A, RED), TrackPaint(B, RED)), 200, overlap="layer"
        )


def test_conflicting_ties_fail_but_different_units_do_not_conflict():
    with pytest.raises(ValueError, match="equal-priority"):
        compose_highlights(
            (TrackPaint(A, RED), TrackPaint(B, BLUE)), 200, overlap="priority"
        )
    result = compose_highlights(
        (TrackPaint(A, RED), TrackPaint(replace(B, unit_index=1), BLUE)),
        200,
        overlap="priority",
    )
    assert [r.unit_index for r in result] == [0, 1]


def test_rgb_and_appearance_validation():
    assert Color.hex("#0123ff") == Color(1, 35, 255)
    for value in ("112233", "#zz2233", "#123", "# 12345"):
        with pytest.raises(ValueError):
            Color.hex(value)
    with pytest.raises(ValueError):
        Paint(opacity=2)
    with pytest.raises(ValueError):
        Glow(blur=-1)
