"""Native rectangle fades use absolute visibility, not the preserved local origin."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    FadeIn,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


@pytest.mark.parametrize("offset", [0, -0.08])
def test_trimmed_parent_fade_keeps_native_alpha_and_absolute_clock(offset):
    doc = Document.create(width=80, height=60)
    child = PathObject(
        id="glyph", lifetime=Lifetime(105.32, 107),
        path=VectorPath.rectangle(20, 16), state=VisualState(position=Vec2(20, 20)),
        clip=RectangleClip(0, 0, 20, 16, space="local",
                           deform=RectangleKeyframes(((0, (0, 0, 20, 16)),))),
    )
    parent = ObjectGroup(
        id="row", lifetime=Lifetime(105.73000000000002, 107), clock_start=105.32,
        children=(child,),
    ).animate(FadeIn(), at=0.41 + offset, duration=0.16)
    result = Scene(doc).add(parent).compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip"
    for ms in (105730, 105770, 105810, 105850, 105890, 106000):
        opacity = min(1, max(0, round((ms / 1000 - (105.73 + offset)) / 0.16, 10)))
        reference = Scene(doc).add(replace(
            child, state=replace(child.state, opacity=opacity),
        )).compile(native_tweens=True)
        actual = rasterize(result.document.dumps(), ms, (80, 60)).rgba[3::4]
        expected = rasterize(reference.document.dumps(), ms, (80, 60)).rgba[3::4]
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1


def test_fade_beginning_after_visibility_still_falls_back():
    node = PathObject(
        id="glyph", lifetime=Lifetime(1, 2), path=VectorPath.rectangle(20, 16),
        clip=RectangleClip(0, 0, 20, 16, space="local",
                           deform=RectangleKeyframes(((0, (0, 0, 20, 16)),))),
    ).animate(FadeIn(), at=0.2, duration=0.3)
    result = Scene(Document.create(width=80, height=60)).add(node).compile(native_tweens=True)
    assert result.objects[0].strategy == "sampled"
    assert node.at(1.1).opacity == 1  # Visible before the authored fade resets it.
