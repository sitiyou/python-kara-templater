"""Shared path intervals drive growing/retracting trails and matching head motion."""

import pytest

from kara_templater import (
    Contour,
    CubicSegment,
    Document,
    GeometryError,
    Lifetime,
    MoveAlong,
    PathObject,
    Polyline,
    Scene,
    SceneBudget,
    TrailPath,
    Vec2,
    VisualState,
    smooth_rate,
)
from kara_templater._raster import rasterize
from kara_templater.path_geometry import path_bounds


def test_polyline_slice_uses_distance_and_preserves_turns():
    line = Polyline((Vec2(), Vec2(30, 0), Vec2(30, 70)))
    assert line.slice(0.2, 0.6).points == (Vec2(20, 0), Vec2(30, 0), Vec2(30, 30))
    assert line.slice(-1, 2).points == line.points
    assert line.slice(0.3, 0.3).points == (Vec2(30, 0),)
    assert Polyline((Vec2(), Vec2())).slice(0, 1).points == (Vec2(),)
    with pytest.raises(ValueError, match="reversed"):
        line.slice(0.8, 0.2)


def test_trail_grows_advances_then_retracts_without_holding_completed_path():
    trail = TrailPath(Polyline((Vec2(), Vec2(100, 0))), duration=1, lag=0.25, width=4)
    expected = ((0.1, 0, 10), (0.5, 25, 50), (1.1, 85, 100))
    for time, left, right in expected:
        path = trail.sample(trail.full_path, time)
        assert path is not None
        box = path_bounds(path)
        assert (box.left, box.right, box.top, box.height) == pytest.approx((left, right, -2, 4))
    assert trail.sample(trail.full_path, 0) is None
    assert trail.sample(trail.full_path, 1.25) is None
    assert trail.sample(trail.full_path, -1) is None
    assert trail.breakpoints == (0, 0.25, 1, 1.25)


def test_curved_trail_and_head_share_seekable_arc_length_and_custom_rate():
    trail = TrailPath(Contour(Vec2(), (
        CubicSegment(Vec2(0, -80), Vec2(60, -80), Vec2(60, 0)),
    ), closed=False), start=0.3, duration=2, lag=0.4, rate=smooth_rate)
    head = MoveAlong(trail.line, rate=smooth_rate)
    base = VisualState(position=Vec2(30, 40))
    for progress in (0.6, 0.1, 0.8, 0.6):
        time = 0.3 + 2 * progress
        assert head.sample(base, progress).position == base.position + trail.tip(time)
        path = trail.sample(trail.full_path, time)
        assert path is not None and path.point_count <= trail.max_points
    assert trail.tip(-10) == Vec2()
    assert trail.tip(10) == Vec2(60, 0)
    assert trail.sample(trail.full_path, 2.7) is None


def test_trail_rejects_geometry_budget_and_invalid_parameters_before_sampling():
    path = Polyline((Vec2(), Vec2(10, 0), Vec2(10, 10)))
    with pytest.raises(GeometryError, match="point bound"):
        TrailPath(path, max_points=4)
    with pytest.raises(GeometryError, match="zero length"):
        TrailPath(Polyline((Vec2(),)))
    for invalid in (
        lambda: TrailPath(path, lag=0), lambda: TrailPath(path, duration=0),
        lambda: TrailPath(path, width=-1), lambda: TrailPath(path, start=-1),
    ):
        with pytest.raises(ValueError):
            invalid()
    trail = TrailPath(path, rate=lambda p: float("nan"))
    with pytest.raises(ValueError):
        trail.sample(trail.full_path, 0.5)


def test_ass_trail_clock_and_visible_interval_match_independent_geometry():
    trail = TrailPath(Polyline((Vec2(), Vec2(100, 0))), duration=1, lag=0.25, width=4)
    node = PathObject(
        id="trail", lifetime=Lifetime(2, 3.25), path=trail.full_path, deform=trail,
        state=VisualState(position=Vec2(20, 30)),
    )
    doc = Document.create(width=160, height=80)
    result = Scene(doc).add(node).compile(budget=SceneBudget(fps=100))
    for ms, interval in ((2100, (20, 30)), (2500, (45, 70)), (3100, (105, 120))):
        pixels = rasterize(result.document.dumps(), ms, (160, 80)).rgba
        xs = [i % 160 for i, alpha in enumerate(pixels[3::4]) if alpha > 128]
        assert xs
        assert abs(min(xs) - interval[0]) <= 1
        assert abs(max(xs) + 1 - interval[1]) <= 1
    for ms in (1900, 3300):
        assert not any(rasterize(result.document.dumps(), ms, (160, 80)).rgba[3::4])


def test_fractional_birth_accepts_exact_tail_end_but_rejects_actual_overrun():
    trail = TrailPath(Polyline((Vec2(), Vec2(40, 0))), duration=0.55, lag=0.18)
    assert trail.sample(trail.full_path, 0.73) is None
    PathObject(id="trail", lifetime=Lifetime(3.33, 4.06),
               path=trail.full_path, deform=trail)
    with pytest.raises(ValueError, match="breakpoint outside"):
        PathObject(id="trail", lifetime=Lifetime(3.33, 4.059),
                   path=trail.full_path, deform=trail)
