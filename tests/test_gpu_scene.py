"""GPU draw preparation shares source animation evaluation and owner identity."""

from dataclasses import replace

import pytest

from kara_templater import (
    Color,
    Document,
    FadeOut,
    Lifetime,
    ObjectGroup,
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
    translucent_size = frames.cached_bytes
    assert translucent_size > size
    assert frames.at(3.75)[0].opacity < later[0].opacity
    assert frames.cached_bytes == translucent_size
    assert frames.at(2) == middle


def test_gpu_scene_keeps_group_and_child_clip_coordinates_separate_after_seek():
    text = node(clip=RectangleClip(-10, -10, 40, 40, space="local"))
    group = ObjectGroup(
        id="viewport",
        children=(text,),
        lifetime=Lifetime(0.5, 4),
        clock_start=1.5,
        clip=RectangleClip(
            0,
            0,
            60,
            50,
            deform=RectangleKeyframes(((0, (0, 0, 0, 50)), (1, (0, 0, 60, 50)))),
        ),
    )
    frames = SceneFrames(Scene(Document.create()).add(group))
    (draw,) = frames.at(2)
    assert draw.clip is not None
    assert draw.clip.local and draw.clip.bounds == (-10, -10, 40, 40)
    (inherited,) = draw.inherited_clips
    assert not inherited.local and inherited.bounds == (0, 0, 30, 50)
    assert frames.at(1.5) == ()
    assert frames.at(2) == (draw,)


def test_gpu_scene_coverage_retains_native_roles_and_negative_ink():
    text = replace(node(), text="jg")
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


@pytest.mark.parametrize("alignment,opacity", [(1, 1), (5, 1), (7, 1), (7, 0.5)])
def test_gpu_cached_local_coverage_matches_untransformed_native_text(alignment, opacity):
    from kara_templater._raster import RasterCanvas, rasterize

    text = TextObject(
        id="glyph",
        text="gj",
        font_size=48,
        italic=True,
        alignment=alignment,
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(80, 60), border=2, blur=0.3, opacity=opacity),
    )
    scene = Scene(Document.create(width=200, height=120)).add(text)
    expected = rasterize(scene.ass.compile().document.dumps(), 500, (200, 120))
    (draw,) = SceneFrames(scene).at(0.5)
    canvas = RasterCanvas(200, 120)
    for x, y, width, height, kind, color, data in draw.images:
        assert color & 255 == 0
        color |= round(255 * (1 - draw.opacity))
        canvas.over((x + 80, y + 60, width, height, kind, color, data))
    actual = canvas.finish()
    # Compare coverage on the ink itself, so blank canvas cannot hide a shift.
    actual_alpha = actual.rgba[3::4]
    reference_alpha = expected.rgba[3::4]
    difference = sum(abs(a - b) for a, b in zip(actual_alpha, reference_alpha, strict=True))
    assert difference <= 0.1 * sum(reference_alpha)


def test_outline_only_drawing_keeps_its_center_clear_during_native_fade():
    from kara_templater import PathObject, VectorPath
    from kara_templater._raster import rasterize

    full = PathObject(id="filled", path=VectorPath.rectangle(24, 24), lifetime=Lifetime(0, 2),
                      state=VisualState(position=Vec2(12, 12), border=3))
    ring = replace(full, id="ring", filled=False).animate(FadeOut(), duration=2)
    doc = Document.create(width=64, height=64)
    # Cache both versions of exactly the same path at the same radius.
    filled_draw, ring_draw = SceneFrames(Scene(doc).add(full, ring)).at(1)
    assert any(i[4] == 0 and i[5] & 255 == 0 for i in filled_draw.images)
    assert all(i[4] != 0 or i[5] & 255 == 255 for i in ring_draw.images)
    assert any(i[4] == 1 and i[5] & 255 == 0 for i in ring_draw.images)
    compiled = Scene(doc).add(ring).ass.compile(native_tweens=True)
    assert compiled.event_count == 1
    rgba = rasterize(compiled.document.dumps(), 1000, (64, 64)).rgba
    assert rgba[4 * (24 * 64 + 24) + 3] == 0
    assert 120 <= rgba[4 * (24 * 64 + 10) + 3] <= 135


def test_hook_rasterizes_paths_and_text_without_an_ass_event(monkeypatch):
    from kara_templater import PathObject, VectorPath, _ass_preview

    def unexpected(*args):
        pytest.fail("hook coverage attempted ASS event rendering")

    monkeypatch.setattr(_ass_preview, "rasterize", unexpected)
    path = PathObject(id="box", path=VectorPath.rectangle(20, 12), lifetime=Lifetime(0, 3),
                      state=VisualState(border=2, shadow=Vec2(-4, 3)))
    draws = SceneFrames(Scene(Document.create()).add(path, node())).at(2)
    assert len(draws) == 2 and draws[1].images
    shadow, border, fill = draws[0].images
    assert [shadow[4], border[4], fill[4]] == [2, 1, 0]
    assert shadow[:2] == (border[0] - 4, border[1] + 3)
    assert fill[6][(6 - fill[1]) * fill[2] + 10 - fill[0]] == 255


def test_static_border_rounds_an_acute_glyph_tip():
    from kara_templater import VectorPath
    from kara_templater._path_raster import path_coverage

    # A narrow V in the middle of the mask leaves room for a miter spike.
    path = VectorPath.polygon(Vec2(2, 2), Vec2(18, 2), Vec2(10, 22))
    border, _fill = path_coverage(path, VisualState(border=4), True, 10000, "tip")
    left, top, width, height, _, _, alpha = border

    def coverage(x: int, y: int) -> int:
        if left <= x < left + width and top <= y < top + height:
            return alpha[(y - top) * width + x - left]
        return 0

    assert coverage(10, 24) > 240
    assert coverage(13, 25) < 10
    assert coverage(10, 26) == 0


def test_path_extrusion_has_connected_side_and_preserves_face_clip_and_clock(tmp_path):
    from kara_templater import Extrusion, PathObject, SceneCompileError, VectorPath

    shape = PathObject(
        id="stem", path=VectorPath.rectangle(2, 14), lifetime=Lifetime(0, 2),
        extrusion=Extrusion(Vec2(-8.5, 0), Color(7, 11, 19)),
        clip=RectangleClip(-12, -5, 20, 20, space="local"), state=VisualState(border=0),
    ).animate(FadeOut(), duration=2)
    scene = Scene(Document.create()).add(shape)
    side, front = SceneFrames(scene).at(1)
    assert side.opacity == front.opacity == 0.5
    assert side.clip == front.clip and side.clip is not None
    (x, y, w, _, role, color, alpha), = side.images
    assert role == 3 and color == 0x070b1300
    assert all(alpha[(6 - y) * w + px - x] > 240 for px in range(-7, -1))
    assert 60 < alpha[(6 - y) * w - 9 - x] < 200
    with pytest.raises(SceneCompileError, match="ASS does not support extrusion"):
        scene.ass.compile()
    scene.export(tmp_path / "shape.hook", fps=24)


def test_extrusion_depth_tracks_each_contour_and_preserves_solid_coverage(tmp_path):
    from kara_templater import Extrusion, PathObject, VectorPath

    path = PathObject(
        id="stem", path=VectorPath.rectangle(2, 12), lifetime=Lifetime(0, 1),
        extrusion=Extrusion(Vec2(-8, 0), Color(240, 245, 235)),
    )
    base = Scene(Document.create()).add(path)
    assert path.extrusion is not None
    back = Color(100, 115, 90)
    shaded = Scene(Document.create()).add(replace(path, extrusion=replace(path.extrusion, back_color=back)))
    side, face = SceneFrames(shaded).at(0)
    solid, solid_face = SceneFrames(base).at(0)
    assert face == solid_face and side.images == solid.images
    assert side.side_shading is not None
    depth, back_color = side.side_shading
    assert back_color == back
    (x, y, w, _, _, _, alpha), = side.images
    samples = [depth[(6 - y) * w + px - x] / alpha[(6 - y) * w + px - x] for px in (-1, -4, -8)]
    assert samples == pytest.approx([0.5 / 8, 3.5 / 8, 7.5 / 8], abs=0.04)
    shaded.export(tmp_path / "shaded.hook", fps=24)


def test_lyric_extrusion_follows_body_and_ruby_without_singing_clip():
    from kara_templater import (
        Extrusion,
        KaraokeEffects,
        Line,
        Style,
        Track,
        prepare_tracks,
    )

    doc = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=50),))
    doc.records.append(Line(start_time=1000, end_time=2500, text=r"{\k50}AB|ab{\k100}C"))
    scene = prepare_tracks(doc, tracks=(Track(
        id="lead", extrusion=Extrusion(Vec2(3, 5), Color(12, 34, 56)),
        effects=(KaraokeEffects(singing="zoom_pulse", hook_feather=3),),
    ),))
    frames = SceneFrames(scene)
    targets = {t.node_id for t in scene.lines[0].query("character", "ruby")}
    assert scene.lines[0].query("ruby")
    for time in (1.25, 2.0, 1.25):
        draws = frames.at(time)
        sides = [d for d in draws if any(i[4] == 3 for i in d.images)]
        assert {d.object_id for d in sides} == targets
        assert len(sides) == len(targets)
        for side in sides:
            assert side.clip is None
            assert side.transform == scene.evaluator().at(side.object_id, time).transform


def test_extruded_antialiased_edge_composites_to_the_swept_silhouette():
    from PIL import Image

    from kara_templater._path_raster import _sweep_mask

    face = Image.frombytes("L", (6, 1), bytes([0, 128, 255, 128, 0, 0]))
    side = _sweep_mask(face, Vec2(1, 0))
    assert list(side.tobytes()) == [0, 0, 0, 255, 128, 0]


def test_extrusion_of_an_outline_keeps_the_unswept_part_of_the_counter_open():
    from kara_templater import Extrusion, PathObject, VectorPath

    ring = PathObject(id="ring", path=VectorPath.rectangle(28, 28), filled=False,
                      extrusion=Extrusion(Vec2(4, 3), Color(10, 20, 30)),
                      state=VisualState(border=2), lifetime=Lifetime(0, 1))
    side, front = SceneFrames(Scene(Document.create()).add(ring)).at(0)
    x, y, width, height, _, _, alpha = side.images[0]
    assert x <= 14 < x + width and y <= 14 < y + height
    assert alpha[(14 - y) * width + 14 - x] == 0
    assert alpha[(14 - y) * width + 2 - x] == 255
    assert [image[4] for image in front.images] == [1]
