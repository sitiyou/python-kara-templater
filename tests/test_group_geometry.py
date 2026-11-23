from dataclasses import replace

import pytest

from kara_templater import (
    AnimationClip,
    Document,
    GeometryError,
    Lifetime,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    SceneBudget,
    SceneCompileError,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    merge_geometry,
)


def box(id, x=0, lifetime=None):
    return PathObject(
        id=id,
        lifetime=Lifetime(0, 2) if lifetime is None else lifetime,
        path=VectorPath.rectangle(40, 40),
        state=VisualState(position=Vec2(x, 0)),
    )


def group(*children):
    return ObjectGroup(id="word", lifetime=Lifetime(0, 2), children=children)


def bounds(path):
    assert path is not None
    points = [p for c in path.contours for p in (c.start, *(s.end for s in c.segments))]
    return min(p.x for p in points), max(p.x for p in points)


def test_union_removes_internal_edges_and_retains_root_properties():
    root = replace(
        group(box("a"), box("b", 20)),
        state=VisualState(position=Vec2(100, 50), opacity=0.4),
        clip=RectangleClip(0, 0, 60, 40, space="local"),
    )
    merged = merge_geometry(root)
    assert merged.deform is None
    assert merged.state == root.state
    assert merged.clip == root.clip
    assert bounds(merged.path) == (0, 60)
    assert merged.path.point_count == VectorPath.rectangle(60, 40).point_count
    assert len(merged.path.contours) == 1


def test_animated_child_lifetimes_seek_and_delayed_copy():
    moving = replace(
        box("b", 20, Lifetime(0.5, 1.5)),
        animations=(AnimationClip(0, 1, Tween(StatePatch(position=Vec2(60, 0)))),),
    )
    merged = merge_geometry(group(box("a"), moving))
    delayed = merged.copy(id="later", delay=3)
    for time, expected in ((1, (0, 80)), (0, (0, 40)), (1.5, (0, 40)), (0.5, (0, 60))):
        assert bounds(merged.path_at(time)) == expected
        assert delayed.path_at(time + 3) == merged.path_at(time)


def test_preflight_rejects_before_geometry_callback():
    calls = []

    def sample(path, time):
        calls.append(time)
        return path

    child = replace(box("a"), deform=PathFunction(sample, max_points=50))
    merged = merge_geometry(group(child), max_points=50)
    assert not calls
    with pytest.raises(SceneCompileError):
        Scene(Document.create()).add(merged).ass.compile(
            budget=SceneBudget(max_path_points=10)
        )
    assert not calls


def test_empty_geometry_and_descendant_clip_diagnostics():
    merged = merge_geometry(group())
    assert merged.path_at(0) is None
    child = replace(box("a"), clip=RectangleClip(0, 0, 10, 10))
    with pytest.raises(GeometryError, match="a: merge_geometry"):
        merge_geometry(group(child))


def test_work_and_source_point_budgets():
    with pytest.raises(GeometryError):
        merge_geometry(group(box("a")), max_work=1)
    with pytest.raises(GeometryError):
        merge_geometry(group(box("a")), max_points=3)


def test_shared_border_and_blur_match_one_independent_rectangle():
    from kara_templater._raster import rasterize

    merged = merge_geometry(group(box("a"), box("b", 20)))
    state = VisualState(position=Vec2(60, 60), border=8, blur=5, opacity=0.6)
    merged = replace(merged, state=state)
    reference = replace(merged, path=VectorPath.rectangle(60, 40))

    def pixels(node):
        result = Scene(Document.create(width=180, height=160)).add(node).ass.compile()
        return rasterize(result.document.dumps(), 0, (180, 160)).rgba

    assert pixels(merged) == pixels(reference)
