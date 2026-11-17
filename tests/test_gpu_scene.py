"""GPU draw preparation shares source animation evaluation and owner identity."""

from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    Document,
    FadeOut,
    Lifetime,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)
from kara_templater._gpu_scene import SceneFrames


def node(**changes):
    return TextObject(
        id="word",
        text="gj",
        italic=True,
        font_size=48,
        lifetime=Lifetime(1, 4),
        state=VisualState(position=Vec2(40, 24), border=2, blur=0.3),
        **changes,
    )


def test_gpu_scene_keeps_clocks_and_reuses_coverage_after_seek():
    text = node(
        clip=RectangleClip(
            -10,
            -10,
            100,
            100,
            space="local",
            deform=RectangleKeyframes(
                ((0, (-10, -10, -10, 100)), (2, (-10, -10, 100, 100)))
            ),
        )
    ).animate(FadeOut(), duration=1, at=2)
    scene = Scene(Document.create(width=160, height=100)).add(text)
    frames = SceneFrames(scene)
    assert frames.at(0.5) == frames.at(1) == frames.at(4) == ()
    middle = frames.at(2)
    assert len(middle) == 1
    assert middle[0].object_id == text.id
    assert middle[0].transform == scene.evaluator().at(text.id, 2).transform
    assert middle[0].clip is not None and middle[0].clip.bounds == (-10, -10, 45, 100)
    size = frames.cached_bytes
    assert 0 < size < 100_000
    later = frames.at(3.5)
    assert later[0].opacity == scene.evaluator().at(text.id, 3.5).opacity
    assert frames.cached_bytes == size
    assert frames.at(2) == middle


def test_gpu_scene_coverage_retains_native_roles_and_negative_ink():
    text = node()
    second = replace(
        text,
        id="copy",
        state=replace(text.state, fill=Color(255, 0, 0), position=Vec2(90, 24)),
    )
    frames = SceneFrames(Scene(Document.create()).add(text, second))
    first, copy = frames.at(2)
    assert first.images and copy.images
    assert any(image[0] < 0 for image in first.images)
    assert {image[4] for image in first.images} == {0, 1}
    for a, b in zip(first.images, copy.images, strict=True):
        assert a[6] is b[6]
        assert (a[5] != b[5]) == (a[4] == 0)
    assert frames.cached_bytes == sum(len(image[6]) for image in first.images)


def test_gpu_scene_rejects_unsupported_inverse_clip():
    text = node(clip=RectangleClip(0, 0, 1, 1, inverse=True))
    with pytest.raises(ValueError, match="inverse clips"):
        SceneFrames(Scene(Document.create()).add(text))


@pytest.mark.parametrize("alignment", (1, 5, 7))
def test_gpu_cached_local_coverage_matches_untransformed_native_text(alignment):
    from kara_templater._raster import RasterCanvas, rasterize

    text = TextObject(
        id="glyph",
        text="gj",
        font_size=48,
        italic=True,
        alignment=alignment,
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(80, 60), border=2, blur=0.3),
    )
    scene = Scene(Document.create(width=200, height=120)).add(text)
    expected = rasterize(scene.compile().document.dumps(), 500, (200, 120))
    (draw,) = SceneFrames(scene).at(0.5)
    canvas = RasterCanvas(200, 120)
    for x, y, width, height, kind, color, data in draw.images:
        canvas.over((x + 80, y + 60, width, height, kind, color, data))
    actual = canvas.finish()
    assert actual.rgba == expected.rgba
