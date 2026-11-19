"""Local gradient strips follow scale and drift without sliding through glyphs."""

from dataclasses import replace
from math import floor

import pytest

from kara_templater import (
    Color,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneBudget,
    SceneCompileError,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def node():
    return PathObject(
        id="glyph",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(24, 24),
        state=VisualState(position=Vec2(8, 8)),
        material=LinearGradient(
            axis="y",
            space="local",
            fill=ColorRamp(
                (
                    ColorStop(0, Color.hex("#FFFF00")),
                    ColorStop(24, Color.hex("#FF0088")),
                )
            ),
        ),
        clip=RectangleClip(
            0,
            0,
            24,
            24,
            space="local",
            deform=RectangleKeyframes(
                ((0, (0, 0, 0, 24)), (0.5, (0, 0, 24, 24)), (1, (0, 0, 24, 24)))
            ),
        ),
    ).animate(Tween(StatePatch(scale=Vec2(2, 2), position=Vec2(12, 4))), duration=1)


@pytest.mark.parametrize("native", (False, True))
def test_local_gradient_moves_with_scaled_shape(native):
    original = node()
    doc = Document.create(width=80, height=80)
    result = (
        Scene(doc)
        .add(original)
        .compile(native_tweens=native, budget=SceneBudget(fps=50))
    )
    assert result.objects[0].strategy == (
        "native-clip-bands" if native else "sampled-bands"
    )
    # Exact raster reference: independent solid paths, one transformed local strip each.
    for ms in (250, 750):
        time = ms / 1000
        state = original.at(time)
        front = min(24, 48 * time)
        reference = Scene(doc)
        assert isinstance(original.material, LinearGradient)
        for band in original.material.bands(0, 24, 0, state):
            a = state.transform.apply(Vec2(0, band.start))
            b = state.transform.apply(Vec2(front, band.end))
            # Native clips retain integer-coordinate rounding. The curve proof
            # allows subpixel edge error; choose width checks away from its edge.
            reference.add(
                replace(
                    original,
                    id=f"band{band.start}",
                    animations=(),
                    material=None,
                    state=replace(state, fill=band.fill, outline=band.outline),
                    clip=RectangleClip(*(floor(v + 0.5) for v in (a.x, a.y, b.x, b.y))),
                )
            )
        actual = rasterize(result.document.dumps(), ms, (80, 80)).rgba
        expected = rasterize(reference.compile().document.dumps(), ms, (80, 80)).rgba
        # Compare the interior gradient; edge rounding is covered by native clip tests.
        for y in range(8, 30):
            for x in range(14, 20):
                offset = (y * 80 + x) * 4
                assert actual[offset + 3] == expected[offset + 3]
                # Animated integer clip edges can choose a neighboring 1px band.
                # One ramp step is <= 11 encoded RGB levels in this small fixture.
                assert max(
                    abs(a - b)
                    for a, b in zip(
                        actual[offset : offset + 3],
                        expected[offset : offset + 3],
                        strict=True,
                    )
                ) <= (12 if native else 0)


@pytest.mark.parametrize("angle", (0, 90))
def test_unmasked_vector_gradient_rotates_with_its_hole(angle):
    outer = VectorPath.rectangle(24, 24)
    inner = VectorPath.rectangle(8, 8).map(lambda p: Vec2(16 - p.x, 8 + p.y))
    gradient = LinearGradient(space="local", axis="y", step=8, fill=ColorRamp((
        ColorStop(0, Color(255, 0, 0)), ColorStop(24, Color(0, 0, 255)),
    )))
    state = VisualState(position=Vec2(32, 20), rotation=angle)
    obj = PathObject(id="sprite", lifetime=Lifetime(0, 1), state=state, material=gradient,
                     path=VectorPath((*outer.contours, *inner.contours)))
    doc = Scene(Document.create(width=80, height=80)).add(obj).compile().document
    frame = rasterize(doc.dumps(), 500, (80, 80)).rgba

    def pixel(x, y):
        point = state.transform.apply(Vec2(x, y))
        index = (round(point.y) * 80 + round(point.x)) * 4
        return tuple(frame[index:index + 4])

    assert pixel(12, 4) == (212, 0, 42, 255)
    assert pixel(12, 20) == (42, 0, 212, 255)
    assert pixel(12, 12)[3] == 0


@pytest.mark.parametrize("filled", (True, False))
@pytest.mark.parametrize("ms", (200, 800))
def test_rotated_outline_gradient_follows_a_moving_path(filled, ms):
    red, blue = Color(255, 0, 0), Color(0, 0, 255)
    gradient = LinearGradient(space="local", axis="y", step=8,
                              outline=ColorRamp((ColorStop(0, red), ColorStop(24, blue))))
    state = VisualState(position=Vec2(45, 16), fill=Color(0, 255, 0), border=5, rotation=90)
    obj = PathObject(id="pen", lifetime=Lifetime(0, 1), state=state, material=gradient,
                     path=VectorPath.rectangle(24, 24), filled=filled)
    obj = obj.animate(Tween(StatePatch(position=Vec2(65, 16))), duration=1)
    scene = Scene(Document.create(width=96, height=64)).add(obj)
    result = scene.compile(native_tweens=True, budget=SceneBudget(fps=50))
    assert result.objects[0].peak_clip_points == 4
    frame = rasterize(result.document.dumps(), ms, (96, 64)).rgba

    def pixel(x, y):
        position = obj.at(ms / 1000).transform.apply(Vec2(x, y))
        index = (round(position.y) * 96 + round(position.x)) * 4
        return tuple(frame[index:index + 4])

    assert pixel(-2, 4) == (212, 0, 42, 255)
    assert pixel(-2, 20) == (42, 0, 212, 255)
    assert pixel(12, -3) == (255, 0, 0, 255)
    assert pixel(12, 27) == (0, 0, 255, 255)
    assert pixel(12, 8) == ((0, 255, 0, 255) if filled else (0, 0, 0, 0))


def test_local_fill_and_pen_ramps_share_the_reflected_drawing_coordinates():
    fill = ColorRamp((ColorStop(0, Color(0, 255, 0)), ColorStop(24, Color(0, 0, 0))))
    outline = ColorRamp((ColorStop(0, Color(255, 0, 0)), ColorStop(24, Color(0, 0, 255))))
    material = LinearGradient(space="local", axis="x", step=8, fill=fill, outline=outline)
    state = VisualState(position=Vec2(55, 22), scale=Vec2(-1.2, 1.4), border=5)
    obj = PathObject(id="pen", lifetime=Lifetime(0, 1), state=state, material=material,
                     path=VectorPath.rectangle(24, 24), scale_border=True)
    result = Scene(Document.create(width=80, height=80)).add(obj).compile()
    frame = rasterize(result.document.dumps(), 500, (80, 80)).rgba

    def pixel(x, y):
        point = state.transform.apply(Vec2(x, y))
        index = (round(point.y) * 80 + round(point.x)) * 4
        return tuple(frame[index:index + 4])

    assert pixel(4, -2) == (212, 0, 42, 255)
    assert pixel(20, -2) == (42, 0, 212, 255)
    assert pixel(4, 12) == (0, 212, 0, 255)
    assert pixel(20, 12) == (0, 42, 0, 255)


def test_unmasked_gradient_reports_unsplit_shadow():
    original = node()
    sprite = replace(original, clip=None, state=replace(original.state, shadow=Vec2(2, 2)))
    with pytest.raises(SceneCompileError, match="separate blur or shadow"):
        Scene(Document.create()).add(sprite).compile()


@pytest.mark.parametrize("bad", ("screen", "inverse"))
def test_local_gradient_rejects_unsupported_mask_contracts(bad):
    original = node()
    assert isinstance(original.clip, RectangleClip)
    if bad == "screen":
        mask = replace(original.clip, space="screen")
    else:
        mask = replace(original.clip, inverse=True)
    with pytest.raises(SceneCompileError, match="local gradient"):
        Scene(Document.create()).add(replace(original, clip=mask)).compile(
            native_tweens=True
        )


def test_local_gradient_combines_centered_scale_curves_and_one_drift():
    original = replace(node(), animations=())
    original = original.animate(
        Tween(StatePatch(scale=Vec2(1.1, 1.1))), at=0.1, duration=0.1
    )
    original = original.animate(
        Tween(StatePatch(scale=Vec2(1, 1))), at=0.2, duration=0.2
    )
    original = original.animate(
        Tween(StatePatch(position=Vec2(12, 4))), at=0.5, duration=0.5
    )
    original = original.animate(Tween(StatePatch(opacity=0)), at=0.6, duration=0.4)
    result = (
        Scene(Document.create(width=80, height=80))
        .add(original)
        .compile(native_tweens=True)
    )
    assert result.event_count == 24
    events = [line for line in result.document.lines if not line.comment]
    assert all(r"\move(8,8,12,4,500,1000)" in line.text for line in events)
    # At the return/hold boundary native geometry and the gradient must both be
    # back at their original location; later alpha reaches zero continuously.
    reference = (
        Scene(Document.create(width=80, height=80))
        .add(
            replace(
                original,
                animations=(),
                state=original.at(0.5),
                clip=RectangleClip(
                    0,
                    0,
                    24,
                    24,
                    space="local",
                    deform=RectangleKeyframes(((0, (0, 0, 24, 24)),)),
                ),
            )
        )
        .compile(native_tweens=True)
    )
    assert (
        rasterize(result.document.dumps(), 500, (80, 80)).rgba
        == rasterize(reference.document.dumps(), 500, (80, 80)).rgba
    )
    earlier = rasterize(result.document.dumps(), 750, (80, 80)).rgba[3::4]
    later = rasterize(result.document.dumps(), 990, (80, 80)).rgba[3::4]
    assert sum(later) < sum(earlier) / 10


def test_local_gradient_does_not_silently_become_screen_space_in_coverage():
    from kara_templater import Coverage, ObjectGroup

    original = replace(node(), animations=())
    group = ObjectGroup(
        id="covered",
        lifetime=original.lifetime,
        children=(original,),
        coverage=Coverage(),
    )
    with pytest.raises(SceneCompileError, match="local gradients"):
        Scene(Document.create(width=80, height=80)).add(group).compile()


@pytest.mark.parametrize("origin", (8, 8.5))
def test_horizontal_gradient_reveals_each_strip_at_its_own_crossing(origin):
    original = node()
    assert isinstance(original.material, LinearGradient)
    static = replace(
        original, animations=(), state=VisualState(position=Vec2(origin, 8)),
        material=replace(original.material, axis="x", step=1),
    )
    scene = Scene(Document.create(width=80, height=80)).add(static)
    native = scene.compile(native_tweens=True)
    sampled = scene.compile(budget=SceneBudget(fps=100))
    assert native.event_count == 24
    for ms in (0, 100, 250, 400, 500, 750):
        actual = rasterize(native.document.dumps(), ms, (80, 80)).rgba
        expected = rasterize(sampled.document.dumps(), ms, (80, 80)).rgba
        # ASS truncates an interpolated clip coordinate; sampled masks round it.
        # Only the pixel intersected by the moving edge may differ.
        front = origin + min(24.0, 48 * ms / 1000)
        for x in range(80):
            if abs(x - front) < 1:
                continue
            offset = (16 * 80 + x) * 4
            assert actual[offset:offset + 4] == expected[offset:offset + 4]


def test_parallel_sweep_with_scale_keeps_the_gradient_attached_to_the_glyph():
    original = node()
    assert isinstance(original.material, LinearGradient)
    moving = replace(original, material=replace(original.material, axis="x", step=4))
    scene = Scene(Document.create(width=80, height=80)).add(moving)
    result = scene.compile(native_tweens=True, budget=SceneBudget(fps=100))
    assert result.objects[0].strategy == "sampled-bands"
    time = 0.25
    state = moving.at(time)
    rgba = rasterize(result.document.dumps(), 250, (80, 80)).rgba
    for local_x in (2, 6, 10, 14):
        point = state.transform.apply(Vec2(local_x, 12))
        offset = (int(point.y) * 80 + int(point.x)) * 4
        if local_x > 12:  # The sweep has advanced halfway at this time.
            assert rgba[offset + 3] == 0
        else:
            assert moving.material.fill is not None
            color = moving.material.fill.at(local_x)
            assert tuple(rgba[offset:offset + 4]) == (color.red, color.green, color.blue, 255)


def test_narrow_moving_band_reserves_only_visible_gradient_strips():
    original = node()
    assert isinstance(original.material, LinearGradient)
    # Empty outside the sweep. Inside, two clip edges traverse the color axis.
    empty = (0, 0, 0, 24)
    motion = RectangleKeyframes(((0.1, empty), (0.1, (0, 0, 3, 24)),
                                 (0.9, (21, 0, 24, 24)), (0.9, empty)))
    shape = replace(original, material=replace(original.material, axis="x"), animations=(),
                    clip=RectangleClip(0, 0, 24, 24, space="local", deform=motion))
    scene = Scene(Document.create(width=80, height=80)).add(shape)
    compiled = scene.compile(native_tweens=True, budget=SceneBudget(max_active=5))
    assert compiled.event_count == 24
    assert compiled.peak_active <= 5
    for ms in (0, 100, 500, 899, 900, 999):
        rgba = rasterize(compiled.document.dumps(), ms, (80, 80)).rgba
        pixels = [x for x in range(80) if rgba[4 * (16 * 80 + x) + 3]]
        if 100 <= ms < 900:
            left = 8 + 21 * (ms - 100) / 800
            assert abs(pixels[0] - left) <= 1
            assert 2 <= len(pixels) <= 4
        else:
            assert not pixels
