from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize
from kara_templater.geometry import Contour, CubicSegment, LineSegment
from kara_templater.path_animation import (
    MorphPath,
    PathFunction,
    WritePath,
    WritingStroke,
)
from kara_templater.path_geometry import (
    GeometryError,
    Polyline,
    flatten,
    morph,
    resample_path,
    stroke,
)
from kara_templater.scene_output import SceneBudget, SceneCompileError
from kara_templater.text_geometry import outline_text, text_to_path


def document() -> Document:
    return Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 360\nScaledBorderAndShadow: yes\n"
    )


def test_polyline_length_queries_and_prefix_with_repeated_points():
    line = Polyline((Vec2(), Vec2(), Vec2(3, 0), Vec2(3, 4)))
    assert line.length == 7
    assert line.point(3 / 7) == Vec2(3, 0)
    assert line.point(5 / 7) == Vec2(3, 2)
    assert line.prefix(5 / 7).points == (Vec2(), Vec2(3, 0), Vec2(3, 2))
    assert line.prefix(0).length == 0
    assert Polyline((Vec2(2, 3),)).point(0.7) == Vec2(2, 3)


def test_adaptive_curve_flattening_and_hard_budget():
    curve = Contour(
        Vec2(), (CubicSegment(Vec2(0, 100), Vec2(100, 100), Vec2(100, 0)),), False
    )
    line = flatten(curve, tolerance=0.05)
    assert line.point(0.5).x == pytest.approx(50)
    assert line.point(0.5).y == pytest.approx(75)
    assert line.length == pytest.approx(200, abs=0.1)
    with pytest.raises(GeometryError, match="point budget"):
        flatten(curve, tolerance=0.001, max_points=4)
    # Collinear overshooting control points must not collapse to a short chord.
    reverse = Contour(
        Vec2(), (CubicSegment(Vec2(100, 0), Vec2(-100, 0), Vec2(1, 0)),), False
    )
    assert flatten(reverse).length > 100


def test_stroke_and_resampling_are_bounded():
    assert stroke(Polyline((Vec2(),)), 4) is None
    path = stroke(Polyline((Vec2(), Vec2(10, 0))), 4)
    assert path == VectorPath.polygon(
        Vec2(0, 2), Vec2(10, 2), Vec2(10, -2), Vec2(0, -2)
    )
    assert resample_path(VectorPath.rectangle(20, 20), 8).point_count == 8
    with pytest.raises(GeometryError):
        resample_path(VectorPath.rectangle(20, 20), 8, max_points=4)


def test_morph_matching_holes_and_failure_diagnostics():
    a = VectorPath.rectangle(20, 20)
    b = a.map(lambda p: p * 2)
    assert morph(a, b, 0.5) == a.map(lambda p: p * 1.5)
    hole = VectorPath.polygon(Vec2(5, 5), Vec2(5, 15), Vec2(15, 15), Vec2(15, 5))
    ring = VectorPath((*a.contours, *hole.contours))
    assert len(morph(ring, ring.map(lambda p: p * 2), 0.5).contours) == 2
    with pytest.raises(GeometryError, match="contour count"):
        morph(a, ring, 0.5)
    with pytest.raises(GeometryError, match="winding"):
        morph(a, hole, 0.5)
    with pytest.raises(GeometryError, match="segment count"):
        morph(a, resample_path(b, 8), 0.5)


@pytest.mark.parametrize("alignment", [7, 5, 2])
def test_text_outline_matches_nominal_ink_and_preserves_source(alignment: int):
    node = TextObject(
        id="text",
        lifetime=Lifetime(0, 1),
        text="B O ffi",
        font_size=64,
        alignment=alignment,
        state=VisualState(position=Vec2(300, 170)),
    )
    from kara_templater import EventOrigin, SourceRef

    node = replace(
        node, origin=EventOrigin((SourceRef("test-glyph", 0),), "outline test")
    )
    outline = outline_text(node)
    assert outline.path is not None and len(outline.path.contours) >= 6
    assert outline.fonts[0].family == "DejaVu Sans"
    path = text_to_path(node)
    assert path.state is node.state and path.lifetime is node.lifetime
    assert path.origin is node.origin
    actual = rasterize(
        Scene(document()).add(path).compile().document.dumps(), 0, (640, 360)
    )
    expected = rasterize(
        Scene(document()).add(node).compile().document.dumps(), 0, (640, 360)
    )
    aa, ea = actual.rgba[3::4], expected.rgba[3::4]
    # Curves converted from native outlines use different raster hinting than text.
    assert sum(abs(a - b) for a, b in zip(aa, ea, strict=True)) / max(1, sum(ea)) < 0.05


def test_vector_replacement_retains_clip_clock_and_hollow_center():
    from kara_templater import RectangleClip, RectangleKeyframes

    clip = RectangleClip(0, 0, 32, 32, space="local", deform=RectangleKeyframes((
        (0, (0, -4, 0, 36)), (1, (0, -4, 36, 36)),
    )))
    node = TextObject(id="slot", text=" ", lifetime=Lifetime(0, 3), clock_start=1,
                      clip=clip, filled=False, state=VisualState(position=Vec2(20, 20), border=2))
    guide = text_to_path(node, path=VectorPath.rectangle(32, 32))
    script = Scene(document()).add(guide).compile(native_tweens=True).document.dumps()
    for ms, visible in ((2200, True), (500, False), (1500, True)):
        alpha = rasterize(script, ms, (640, 360)).rgba[3::4]
        assert bool(alpha[19 * 640 + 24]) == visible
        assert alpha[36 * 640 + 36] == 0


def test_whitespace_and_complex_outline_limits():
    node = TextObject(id="blank", lifetime=Lifetime(0, 1), text="   ")
    assert outline_text(node).path is None
    with pytest.raises(GeometryError, match="no visible outline"):
        text_to_path(node)
    with pytest.raises(GeometryError, match="point budget"):
        outline_text(replace(node, text="WAVE"), max_points=3)


def test_writing_and_tip_share_arc_length_and_are_seekable():
    spec = WritingStroke(
        Contour(
            Vec2(), (LineSegment(Vec2(100, 0)), LineSegment(Vec2(100, 100))), False
        ),
        0,
        2,
    )
    other = WritingStroke(
        Contour(Vec2(200, 0), (LineSegment(Vec2(200, 100)),), False), 3, 1
    )
    writer = WritePath((spec, other), width=4)
    assert writer.tip(1) == Vec2(100, 0)
    assert writer.tip(2.5) == Vec2(100, 100)
    assert writer.tip(3.5) == Vec2(200, 50)
    base = VectorPath.rectangle(1, 1)
    assert writer.sample(base, 0) is None
    middle = writer.sample(base, 1.5)
    assert writer.sample(base, 4) is not None
    assert writer.sample(base, 1.5) == middle
    assert writer.tip(1) == Vec2(100, 0)


def test_geometry_budget_preflight_actual_checks_and_empty_frames():
    base = VectorPath.rectangle(20, 20)

    def fail(path: VectorPath, time: float) -> VectorPath:
        raise AssertionError("must not call before budget checks")

    node = PathObject(
        id="path",
        lifetime=Lifetime(0, 1),
        path=base,
        deform=PathFunction(fail, max_points=5000),
    )
    with pytest.raises(SceneCompileError, match="declared geometry"):
        Scene(document()).add(node).compile()
    invalid = replace(node, deform=PathFunction(lambda p, t: p, max_points=3))
    with pytest.raises(SceneCompileError, match="declared point bound") as error:
        Scene(document()).add(invalid).compile()
    assert error.value.object_id == "path"
    hidden = replace(
        node,
        deform=PathFunction(
            lambda p, t: None if 0.25 <= t < 0.75 else p,
            max_points=4,
            breakpoints=(0.25, 0.75),
        ),
    )
    result = Scene(document()).add(hidden).compile()
    assert result.event_count == 2
    assert [
        (l.start_time, l.end_time) for l in result.document.lines if not l.comment
    ] == [(0, 250), (750, 1000)]
    with pytest.raises(SceneCompileError, match="estimated event"):
        Scene(document()).add(hidden).compile(budget=SceneBudget(max_events=2))


def test_geometry_sampler_morph_and_timing():
    base = VectorPath.rectangle(20, 20)
    node = PathObject(
        id="path",
        lifetime=Lifetime(2, 4),
        path=base,
        deform=MorphPath(base.map(lambda p: p * 2), duration=1),
    )
    assert node.path_at(2.5) == base.map(lambda p: p * 1.5)
    result = Scene(document()).add(node).compile()
    assert result.objects[0].strategy == "sampled"
    assert result.event_count == 51
    assert result.objects[0].peak_path_points == 4


def test_convex_intersection_retains_hole_winding_and_handles_empty_results():
    from kara_templater import intersect_convex

    outer = VectorPath.rectangle(20, 20)
    hole = VectorPath.polygon(Vec2(5, 5), Vec2(5, 15), Vec2(15, 15), Vec2(15, 5))
    ring = VectorPath((*outer.contours, *hole.contours))
    result = intersect_convex(
        ring, (Vec2(0, 0), Vec2(10, 0), Vec2(10, 20), Vec2(0, 20))
    )
    assert result is not None
    assert sum(flatten(c).signed_area for c in result.contours) == pytest.approx(150)
    assert (
        intersect_convex(ring, (Vec2(40, 0), Vec2(50, 0), Vec2(50, 20), Vec2(40, 20)))
        is None
    )
    with pytest.raises(GeometryError, match="convex"):
        intersect_convex(
            ring, (Vec2(), Vec2(20, 0), Vec2(5, 5), Vec2(20, 20), Vec2(0, 20))
        )


def test_circle_and_writing_geometry_limits():
    circle = VectorPath.circle(20)
    assert flatten(circle.contours[0], tolerance=0.01).length == pytest.approx(
        40 * 3.14159265, abs=0.1
    )
    spec = WritingStroke(Contour(Vec2(), (LineSegment(Vec2()),), False), 0, 1)
    with pytest.raises(GeometryError, match="zero length"):
        WritePath((spec,))
    with pytest.raises(ValueError, match="three samples"):
        resample_path(circle, 2)


@pytest.mark.parametrize("initial_opacity", (0, 0.25))
def test_clip_discontinuity_splits_event_even_off_regular_sample_grid(initial_opacity):
    from kara_templater import AnimationClip, StateFunction

    node = TextObject(
        id="step",
        lifetime=Lifetime(0, 1),
        text="A",
        animations=(
            AnimationClip(
                0,
                1,
                StateFunction(
                    lambda s, p: replace(s, opacity=initial_opacity if p < 0.23 else 1),
                    frozenset(("opacity",)),
                ),
                breakpoints=(0.23,),
            ),
        ),
    )
    result = Scene(document()).add(node).compile()
    times = [(l.start_time, l.end_time) for l in result.document.lines if not l.comment]
    assert times == ([(0, 230)] if initial_opacity else []) + [(230, 1000)]
    with pytest.raises(ValueError, match="breakpoint"):
        AnimationClip(0, 1, StateFunction(lambda s, p: s), breakpoints=(2,))


def test_document_create_has_equivalent_metadata_and_roundtrips():
    doc = Document.create(width=640, height=360)
    assert (doc.meta.res_x, doc.meta.res_y) == (640, 360)
    assert doc.meta["wrapstyle"] == "2"
    assert Document.parse(doc.dumps()).dumps() == doc.dumps()
