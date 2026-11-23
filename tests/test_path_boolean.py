from math import cos, sin, tau
from random import Random

import pytest

from kara_templater import (
    Contour,
    Document,
    GeometryError,
    Lifetime,
    LineSegment,
    PathObject,
    Scene,
    Vec2,
    VectorPath,
    VisualState,
    flatten,
    path_boolean,
)
from kara_templater._raster import rasterize


def polygon(*coordinates):
    return VectorPath.polygon(*(Vec2(x, y) for x, y in coordinates))


def edges(path):
    if path is None:
        return ()
    result = []
    for contour in path.contours:
        points = [contour.start, *(segment.end for segment in contour.segments)]
        result.extend(zip(points, (*points[1:], points[0]), strict=True))
    return result


def contains(segments, point):
    winding = 0
    for a, b in segments:
        cross = (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x)
        if a.y <= point.y < b.y and cross > 0:
            winding += 1
        elif b.y <= point.y < a.y and cross < 0:
            winding -= 1
    return winding != 0


def check_membership(a, b):
    first, second = edges(a), edges(b)
    for operation in ("intersection", "union", "difference", "xor"):
        result = path_boolean(a, b, operation)
        actual = edges(result)
        for x in range(-20, 140, 9):
            for y in range(-20, 140, 11):
                point = Vec2(x + 0.317, y + 0.219)
                ia, ib = contains(first, point), contains(second, point)
                expected = {
                    "intersection": ia and ib,
                    "union": ia or ib,
                    "difference": ia and not ib,
                    "xor": ia != ib,
                }[operation]
                assert contains(actual, point) == expected, (operation, point, result)
        assert result == path_boolean(a, b, operation)


@pytest.mark.parametrize(
    "a,b",
    [
        (
            polygon((0, 0), (100, 0), (30, 30), (100, 100), (0, 100)),
            polygon((20, 10), (120, 10), (80, 50), (120, 90), (20, 90)),
        ),
        (polygon((0, 0), (100, 100), (0, 100), (100, 0)), VectorPath.rectangle(80, 80)),
        (
            VectorPath.rectangle(40, 40),
            VectorPath.rectangle(40, 40).map(lambda p: p + Vec2(40, 40)),
        ),
        (
            VectorPath.rectangle(40, 40),
            VectorPath.rectangle(40, 40).map(lambda p: p + Vec2(40, 0)),
        ),
        (
            VectorPath.rectangle(100, 100),
            polygon((0, 0), (50, 0), (100, 0), (100, 50), (100, 100), (0, 100)),
        ),
    ],
)
def test_nonconvex_self_crossing_shared_edges_and_point_contacts(a, b):
    check_membership(a, b)


def test_nonzero_winding_keeps_holes_cancels_opposite_contours_and_fills_same_winding():
    outer = VectorPath.rectangle(100, 100)
    hole = polygon((20, 20), (20, 80), (80, 80), (80, 20))
    check_membership(
        VectorPath(outer.contours + hole.contours), VectorPath.rectangle(70, 70)
    )
    duplicate = polygon((0, 0), (0, 100), (100, 100), (100, 0))
    assert path_boolean(VectorPath(outer.contours + duplicate.contours), outer) is None
    inner = VectorPath.rectangle(60, 60).map(lambda p: p + Vec2(20, 20))
    combined = path_boolean(VectorPath(outer.contours + inner.contours), outer)
    assert combined is not None and combined.point_count == 4


def test_seeded_polygons_preserve_membership_under_all_four_operations():
    random = Random(23031)
    for _ in range(20):
        shapes = []
        for center in (Vec2(45, 50), Vec2(65, 50)):
            points = [
                center
                + Vec2(cos(index * tau / 9), sin(index * tau / 9))
                * random.uniform(15, 65)
                for index in range(9)
            ]
            if random.random() < 0.5:
                random.shuffle(points)
            shapes.append(VectorPath.polygon(*points))
        check_membership(*shapes)


def raster(path, *, border=0):
    scene = Scene(Document.create(width=240, height=180))
    if path is not None:
        scene.add(
            PathObject(
                id="shape",
                lifetime=Lifetime(0, 1),
                path=path,
                state=VisualState(position=Vec2(30, 30), border=border),
            )
        )
    return rasterize(scene.ass.compile().document.dumps(), 0, (240, 180)).rgba


def test_stitched_contours_have_no_internal_stroke_edges_or_fill_seams():
    first = VectorPath.rectangle(100, 80)
    second = VectorPath.rectangle(100, 80).map(lambda p: p + Vec2(50, 0))
    result = path_boolean(first, second, "union")
    assert raster(result, border=3) == raster(VectorPath.rectangle(150, 80), border=3)
    hole = VectorPath.rectangle(40, 40).map(lambda p: p + Vec2(30, 20))
    result = path_boolean(first, hole, "difference")
    reference = VectorPath(
        first.contours + polygon((30, 20), (30, 60), (70, 60), (70, 20)).contours
    )
    assert raster(result, border=3) == raster(reference, border=3)


def test_curve_flattening_is_explicit_and_closed_output_matches_flat_reference():
    circle = VectorPath.circle(40).map(lambda p: p + Vec2(60, 60))
    result = path_boolean(circle, VectorPath.rectangle(120, 120))
    points = flatten(circle.contours[0], tolerance=0.25).points[:-1]
    assert raster(result, border=2) == raster(VectorPath.polygon(*points), border=2)


def test_work_input_result_and_open_contour_limits_are_explicit():
    rectangle = VectorPath.rectangle(100, 100)
    with pytest.raises(GeometryError, match="input point budget"):
        path_boolean(rectangle, rectangle, max_points=7)
    with pytest.raises(GeometryError, match="work budget"):
        path_boolean(rectangle, rectangle, max_work=1)
    a = polygon((0, 0), (100, 0), (50, 100))
    b = polygon((0, 70), (50, -30), (100, 70))
    with pytest.raises(GeometryError, match="result point budget"):
        path_boolean(a, b, "union", max_points=6)
    opened = VectorPath((Contour(Vec2(), (LineSegment(Vec2(10, 20)),), False),))
    with pytest.raises(GeometryError, match="closed contours"):
        path_boolean(opened, rectangle)
