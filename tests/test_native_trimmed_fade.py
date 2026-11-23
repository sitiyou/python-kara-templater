"""Native rectangle fades use absolute visibility, not the preserved local origin."""

from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    FadeIn,
    FadeOut,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneCompileError,
    Vec2,
    VectorPath,
    VisualState,
    ease_out,
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
    result = Scene(doc).add(parent).ass.compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip"
    for ms in (105730, 105770, 105810, 105850, 105890, 106000):
        opacity = min(1, max(0, round((ms / 1000 - (105.73 + offset)) / 0.16, 10)))
        reference = Scene(doc).add(replace(
            child, state=replace(child.state, opacity=opacity),
        )).ass.compile(native_tweens=True)
        actual = rasterize(result.document.dumps(), ms, (80, 60)).rgba[3::4]
        expected = rasterize(reference.document.dumps(), ms, (80, 60)).rgba[3::4]
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1


def test_fade_beginning_after_visibility_still_falls_back():
    node = PathObject(
        id="glyph", lifetime=Lifetime(1, 2), path=VectorPath.rectangle(20, 16),
        clip=RectangleClip(0, 0, 20, 16, space="local",
                           deform=RectangleKeyframes(((0, (0, 0, 20, 16)),))),
    ).animate(FadeIn(), at=0.2, duration=0.3)
    with pytest.raises(SceneCompileError, match="frame sampling"):
        Scene(Document.create(width=80, height=60)).add(node).ass.compile(native_tweens=True)
    assert node.at(1.1).opacity == 1  # Visible before the authored fade resets it.

@pytest.mark.parametrize("clipped", [False, True])
def test_quadratic_line_fade_tracks_playback_time_in_one_ass_event(clipped):
    doc = Document.create(width=80, height=60)
    glyph = PathObject(
        id="glyph", lifetime=Lifetime(0, 2), path=VectorPath.rectangle(20, 16),
        state=VisualState(position=Vec2(20, 20)),
        clip=RectangleClip(0, 0, 20, 16, space="local",
                           deform=RectangleKeyframes(((0, (0, 0, 20, 16)),))) if clipped else None,
    )
    row = ObjectGroup(id="row", lifetime=glyph.lifetime, children=(glyph,)).animate(
        FadeIn(rate=ease_out), at=0, duration=0.6,
    ).animate(FadeOut(rate=ease_out), at=1.4, duration=0.6)
    compiled = Scene(doc).add(row).ass.compile(native_tweens=True)
    assert compiled.objects[0].strategy == ("native-clip" if clipped else "native-tween")
    for ms in (0, 60, 180, 300, 590, 1000, 1450, 1700, 1900):
        expected = 255 * row.at(ms / 1000).opacity
        actual = rasterize(compiled.document.dumps(), ms, (80, 60)).rgba[(25 * 80 + 25) * 4 + 3]
        assert abs(actual - expected) <= 2
