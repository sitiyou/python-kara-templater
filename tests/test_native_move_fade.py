"""One native move plus paint transforms matches independently placed frames."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    Scene,
    SceneCompileError,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def test_native_move_and_fade_keep_clock_and_static_parent_transform():
    doc = Document.create(width=160, height=100)
    node = PathObject(
        id="spark", lifetime=Lifetime(0, 2), path=VectorPath.rectangle(6, 6),
        state=VisualState(position=Vec2(10, 10), opacity=0.8),
    ).animate(Tween(StatePatch(position=Vec2(70, 30), opacity=0)), at=0.5, duration=1)
    parent = ObjectGroup(id="line", lifetime=Lifetime(0, 2), children=(node,),
                         state=VisualState(position=Vec2(20, 20), opacity=0.5))
    result = Scene(doc).add(parent).ass.compile(native_tweens=True)
    assert result.event_count == 1
    assert r"\move(30,30,90,50,500,1500)" in result.document.lines[0].text
    for ms, p in ((0, 0), (500, 0), (750, 0.25), (1000, 0.5), (1250, 0.75), (1500, 1)):
        reference = Scene(doc).add(replace(
            node, animations=(),
            state=VisualState(position=Vec2(30 + 60 * p, 30 + 20 * p), opacity=0.4 * (1 - p)),
        )).ass.compile()
        actual = rasterize(result.document.dumps(), ms, (160, 100)).rgba[3::4]
        expected = rasterize(reference.document.dumps(), ms, (160, 100)).rgba[3::4]
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1


def test_multiple_movement_phases_do_not_claim_one_move_native_output():
    node = PathObject(id="spark", lifetime=Lifetime(0, 2), path=VectorPath.rectangle(6, 6))
    node = node.animate(Tween(StatePatch(position=Vec2(30, 0))), duration=1)
    node = node.animate(Tween(StatePatch(position=Vec2(0, 30))), at=1, duration=1)
    with pytest.raises(SceneCompileError, match="frame sampling"):
        Scene(Document.create(width=160, height=100)).add(node).ass.compile(native_tweens=True)
