from itertools import pairwise

import pytest

from kara_templater.ass_output import ClipSpan, OutputCapabilityError
from kara_templater.composition import Color, Paint
from kara_templater.masks import PaintedMask, compose_masks, track_spans
from kara_templater.timeline import (
    DisplayWindow,
    EdgeSweep,
    HighlightTrack,
    ProgressCurve,
    Region,
    SingingPass,
)

RED, BLUE, BASE = (
    Paint(Color(*c)) for c in ((255, 0, 0), (0, 0, 255), (255, 255, 255))
)
WINDOW = DisplayWindow(0, 1000)


def test_incompatible_clocks_share_identical_quantized_edges_at_every_exposure():
    from math import floor

    from kara_templater.ass_output import quantize

    masks = (
        PaintedMask(
            "main", RED, 0, (ClipSpan(0, 1000, Region(0, 0.3), Region(0, 100.7)),)
        ),
        PaintedMask(
            "cover", BLUE, 1, (ClipSpan(230, 810, Region(0, 10.2), Region(0, 90.6)),)
        ),
    )
    regions = compose_masks(
        masks, domain=Region(0, 120), window=WINDOW, before=BASE, overlap="priority"
    )
    assert any(r.shared_local_clock for r in regions)

    def emitted_edge(region, time, side):
        span = region.interpolation_span or region.span
        a, b = quantize(span.start_ms), quantize(span.end_ms)
        first = floor(getattr(span.start, side) + 0.5)
        last = floor(getattr(span.end, side) + 0.5)
        return first + (last - first) * (time - a) / (b - a)

    for time in range(0, 1000, 10):
        active = sorted(
            (
                r
                for r in regions
                if quantize(r.span.start_ms) <= time < quantize(r.span.end_ms)
            ),
            key=lambda r: r.span.at(time).left,
        )
        assert active
        assert emitted_edge(active[0], time, "left") == 0
        assert emitted_edge(active[-1], time, "right") == 120
        for left, right in pairwise(active):
            assert emitted_edge(left, time, "right") == pytest.approx(
                emitted_edge(right, time, "left"), abs=1e-10
            )


@pytest.mark.parametrize("kind", ["glow", "outline", "opacity", "plain", "same"])
def test_spatial_decoration_boundary_is_distinct_from_plain_color(kind):
    from dataclasses import replace

    from kara_templater.composition import Glow

    before = BASE
    after = RED
    if kind == "glow":
        after = replace(after, glow=Glow(blur=20))
    elif kind == "outline":
        after = replace(after, border=3)
    elif kind in ("opacity", "same"):
        before = replace(before, glow=Glow(blur=20))
        after = replace(
            after, glow=before.glow, opacity=0.5 if kind == "opacity" else 1
        )
    masks = (
        PaintedMask(
            "half", after, 0, (ClipSpan(0, 1000, Region(0, 50), Region(0, 50)),)
        ),
    )
    result = compose_masks(
        masks, domain=Region(0, 100), window=WINDOW, before=before, overlap="union"
    )
    assert len(result) == 2
    assert all(
        r.hard_decoration_boundary == (kind in {"glow", "outline", "opacity"})
        for r in result
    )


def test_temporal_decoration_change_and_identical_union_have_no_hard_boundary():
    from dataclasses import replace

    from kara_templater.composition import Glow

    painted = replace(RED, glow=Glow(blur=20))
    span = ClipSpan(500, 1000, Region(0, 100), Region(0, 100))
    result = compose_masks(
        (
            PaintedMask("one", painted, 0, (span,)),
            PaintedMask("two", painted, 0, (span,)),
        ),
        domain=Region(0, 100),
        window=WINDOW,
        before=BASE,
        overlap="union",
    )
    assert len(result) == 2
    assert not any(r.hard_decoration_boundary for r in result)


def test_priority_exit_keeps_original_front_interpolation_clock():
    moving = ClipSpan(100, 900, Region(0, 0), Region(0, 100))
    masks = (
        PaintedMask("base", RED, 0, (moving,)),
        PaintedMask(
            "cover", BLUE, 10, (ClipSpan(0, 500, Region(0, 100), Region(0, 100)),)
        ),
    )
    result = compose_masks(
        masks, domain=Region(0, 100), window=WINDOW, before=BASE, overlap="priority"
    )
    revealed = [r for r in result if r.paints == (RED,) and r.span.start_ms == 500]
    assert len(revealed) == 1
    assert revealed[0].span.start == Region(0, 50)
    assert revealed[0].interpolation_span == moving
    for region in result:
        if region.interpolation_span is not None:
            for fraction in (0, 0.25, 0.5, 0.75, 1):
                time = (
                    region.span.start_ms
                    + (region.span.end_ms - region.span.start_ms) * fraction
                )
                assert region.interpolation_span.at(time) == region.span.at(time)


@pytest.mark.parametrize("window", [WINDOW, DisplayWindow(200, 400)])
@pytest.mark.parametrize("separate_tracks", [False, True])
def test_adjacent_partition_transitions_preserve_internal_front(
    window, separate_tracks
):
    body, paint = Region(0, 100), Region(-200, 300)
    edges = EdgeSweep(padding_px=20, lead_ms=300, tail_ms=400)
    passes = (
        SingingPass(100, 300, Region(0, 50)),
        SingingPass(300, 500, Region(50, 100)),
    )
    tracks = (
        tuple(HighlightTrack(str(i), 0, (p,)) for i, p in enumerate(passes))
        if separate_tracks
        else (HighlightTrack("both", 0, passes),)
    )

    def compose(selected):
        return compose_masks(
            tuple(
                PaintedMask(
                    t.id,
                    RED,
                    0,
                    track_spans(
                        t,
                        body=body,
                        paint=paint,
                        window=window,
                        edges=edges,
                    ),
                )
                for t in selected
            ),
            domain=Region(-220, 320),
            window=window,
            before=BASE,
            overlap="union",
        )

    partitioned = compose(tracks)
    reference = compose((HighlightTrack("whole", 0, (SingingPass(100, 500, body),)),))
    # Nominal lead/tail windows overlap around 300 ms. Interior boundaries
    # must stay at 50 rather than expose the next partition's unsung body.
    for time in (
        0,
        99,
        100,
        199,
        200,
        299,
        300,
        301,
        399,
        400,
        499,
        500,
        899,
        900,
        999,
    ):
        if not window.start_ms <= time < window.end_ms:
            continue
        for x in (-219, -100, -1, 0.1, 25, 49.9, 50.1, 75, 99.9, 101, 200, 319):
            assert at(partitioned, time, x) == at(reference, time, x)
            if 100 <= time < 500 and 0 < x < 100:
                assert at(partitioned, time, x) == (
                    (RED,) if x < (time - 100) / 4 else (BASE,)
                )


def at(result, time, x):
    active = [
        r.paints
        for r in result
        if r.span.start_ms <= time < r.span.end_ms
        and r.span.at(time).left <= x < r.span.at(time).right
    ]
    assert len(active) == 1
    return active[0]


def test_crossing_fronts_are_partitioned_without_frame_sampling():
    a = PaintedMask("a", RED, 0, (ClipSpan(0, 1000, Region(0, 0), Region(0, 100)),))
    b = PaintedMask("b", RED, 0, (ClipSpan(0, 1000, Region(0, 50), Region(0, 75)),))
    result = compose_masks(
        (a, b), domain=Region(0, 100), window=WINDOW, before=BASE, overlap="union"
    )
    assert len(result) == 4
    assert result[0].span.end_ms == pytest.approx(2000 / 3)
    for time in (100, 333, 600, 700, 900):
        front = max(time / 10, 50 + time / 40)
        for x in (5, 49, 61, 78, 95):
            assert at(result, time, x) == ((RED,) if x < front else (BASE,))


def test_priority_exit_and_explicit_layer_stack():
    a = PaintedMask("a", RED, 0, (ClipSpan(0, 1000, Region(0, 100), Region(0, 100)),))
    b = PaintedMask("b", BLUE, 1, (ClipSpan(0, 500, Region(50, 100), Region(50, 100)),))
    result = compose_masks(
        (a, b), domain=Region(0, 100), window=WINDOW, before=BASE, overlap="priority"
    )
    assert at(result, 200, 75) == (BLUE,)
    assert at(result, 600, 75) == (RED,)
    layered = compose_masks(
        (a, b), domain=Region(0, 100), window=WINDOW, before=BASE, overlap="layer"
    )
    assert at(layered, 200, 75) == (BASE, RED, BLUE)
    assert at(layered, 600, 75) == (BASE, RED)
    with pytest.raises(OutputCapabilityError, match="identical"):
        compose_masks(
            (a, b), domain=Region(0, 100), window=WINDOW, before=BASE, overlap="union"
        )


def test_reset_and_hide_use_track_lifecycle():
    track = HighlightTrack(
        "a",
        0,
        (
            SingingPass(100, 200, Region(0, 100)),
            SingingPass(600, 800, Region(0, 100), round_id=1),
        ),
        repeat="reset",
        end_behavior="hide",
    )
    spans = track_spans(
        track,
        body=Region(0, 100),
        paint=Region(-10, 110),
        window=WINDOW,
        edges=EdgeSweep(lead_ms=50, tail_ms=100),
    )
    masks = (PaintedMask("a", RED, 0, spans),)
    result = compose_masks(
        masks, domain=Region(0, 100), window=WINDOW, before=BASE, overlap="union"
    )
    assert at(result, 400, 75) == (RED,)
    assert at(result, 650, 75) == (BASE,)
    assert at(result, 799, 75) == (RED,)
    assert at(result, 800, 75) == (BASE,)


def test_same_track_overlapping_masks_do_not_double_opacity():
    span = ClipSpan(0, 1000, Region(0, 100), Region(0, 100))
    result = compose_masks(
        (PaintedMask("a", RED, 0, (span, span)),),
        domain=Region(0, 100),
        window=WINDOW,
        before=BASE,
        overlap="layer",
    )
    assert at(result, 500, 50) == (BASE, RED)


def test_unchanged_appearance_does_not_fragment_at_singing_boundaries():
    mask = PaintedMask(
        "a",
        BASE,
        0,
        (
            ClipSpan(100, 500, Region(0, 0), Region(0, 100)),
            ClipSpan(500, 1000, Region(0, 100), Region(0, 100)),
        ),
    )
    result = compose_masks(
        (mask,), domain=Region(0, 100), window=WINDOW, before=BASE, overlap="union"
    )
    assert len(result) == 1
    assert result[0].span.start_ms == 0 and result[0].span.end_ms == 1000
    assert at(result, 250, 75) == (BASE,)


@pytest.mark.parametrize(
    "window", [DisplayWindow(0, 1000), DisplayWindow(50, 250), DisplayWindow(105, 205)]
)
@pytest.mark.parametrize(
    "edges", [EdgeSweep(), EdgeSweep(20, 300, 400), EdgeSweep(0, 5, 5)]
)
def test_decoration_lead_tail_and_window_do_not_consume_body_time(window, edges):
    track = HighlightTrack(
        "a",
        0,
        (
            SingingPass(100, 110, Region(0, 40)),
            SingingPass(200, 200, Region(40, 100)),
        ),
    )
    spans = track_spans(
        track, body=Region(0, 100), paint=Region(-200, 300), window=window, edges=edges
    )
    result = compose_masks(
        (PaintedMask("a", RED, 0, spans),),
        domain=Region(-250, 350),
        window=window,
        before=BASE,
        overlap="union",
    )
    for time in (0, 50, 99, 100, 105, 109, 110, 150, 199, 200, 204, 249, 600):
        if not window.start_ms <= time < window.end_ms:
            continue
        for x in (1, 19, 21, 39, 40, 41, 75, 99):
            sung = any(r.left <= x < r.right for r in track.regions_at(time))
            assert at(result, time, x) == ((RED,) if sung else (BASE,))


def test_independent_tracks_pause_exit_and_preserve_disjoint_regions():
    a = HighlightTrack(
        "a",
        0,
        (
            SingingPass(
                100,
                300,
                Region(0, 40),
                ProgressCurve(((0, 0), (0.25, 0.5), (0.75, 0.5), (1, 1))),
            ),
            SingingPass(500, 600, Region(60, 100)),
        ),
    )
    b = HighlightTrack(
        "b", 0, (SingingPass(200, 450, Region(20, 80)),), end_behavior="hide"
    )
    masks = tuple(
        PaintedMask(
            t.id,
            paint,
            priority,
            track_spans(
                t,
                body=Region(0, 100),
                paint=Region(0, 100),
                window=WINDOW,
                edges=EdgeSweep(),
            ),
        )
        for t, paint, priority in ((a, RED, 0), (b, BLUE, 1))
    )
    result = compose_masks(
        masks, domain=Region(0, 100), window=WINDOW, before=BASE, overlap="priority"
    )
    expected = {
        150: (RED, BASE, BASE, BASE, BASE),
        250: (RED, BLUE, BASE, BASE, BASE),
        350: (RED, BLUE, BLUE, BASE, BASE),
        450: (RED, RED, BASE, BASE, BASE),
        550: (RED, RED, BASE, RED, BASE),
        650: (RED, RED, BASE, RED, RED),
    }
    for time, paints in expected.items():
        assert tuple(at(result, time, x)[0] for x in (10, 30, 50, 70, 90)) == paints
