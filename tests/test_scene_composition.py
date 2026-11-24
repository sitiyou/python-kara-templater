"""Coverage is an explicit strategy inside the same Scene as ordinary drawings."""

from dataclasses import replace

from kara_templater import (
    BLUE,
    RED,
    AssBudget,
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    Scene,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize

BUDGET = AssBudget(max_events=20_000, max_active=5_000)


_POSITION = Vec2(5, 5)


def drawing(identity: str, color=RED, position=_POSITION) -> PathObject:
    return PathObject(
        id=identity,
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(20, 20),
        state=VisualState(position=position, fill=color),
    )


def group() -> ObjectGroup:
    return ObjectGroup(
        id="word",
        lifetime=Lifetime(0, 1),
        state=VisualState(opacity=0.5),
        children=(drawing("first"), drawing("second")),
    )


def pixel(result, x=10, y=10):
    frame = rasterize(result.document.dumps(), 500, (64, 48))
    offset = (y * 64 + x) * 4
    return tuple(frame.rgba[offset : offset + 4])


def test_scene_order_is_independent_of_identity_and_exposure_start():

    earlier = replace(drawing("z", BLUE), lifetime=Lifetime(0, 1))
    later = replace(drawing("a", RED), lifetime=Lifetime(0.4, 0.8))
    doc = Document.create(width=64, height=48)
    scene = Scene(doc).add(earlier, later)
    result = scene.ass.compile(budget=BUDGET)
    assert [report.id for report in result.objects] == ["z", "a"]
    assert pixel(result) == (255, 0, 0, 255)
    for time in (100, 900):
        frame = rasterize(result.document.dumps(), time, (64, 48)).rgba
        offset = (10 * 64 + 10) * 4
        assert tuple(frame[offset : offset + 4]) == (0, 0, 255, 255)
    reversed_result = Scene(doc).add(later, earlier).ass.compile(budget=BUDGET)
    assert pixel(reversed_result) == (0, 0, 255, 255)
