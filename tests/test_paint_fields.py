from dataclasses import replace

import pytest

from kara_templater import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    Color,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    PaintBand,
    PathObject,
    Scene,
    SoftSweep,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize
from kara_templater.scene import ObjectGroup, RectangleClip, VectorClip
from kara_templater.scene_animation import AnimationClip, StatePatch, Tween
from kara_templater.scene_output import SceneBudget, SceneCompileError


def ramp(a=BLACK, b=WHITE):
    return ColorRamp((ColorStop(0, a), ColorStop(64, b)))


def node(**kwargs):
    return PathObject(
        id="field", lifetime=Lifetime(0, 2), path=VectorPath.rectangle(64, 32), **kwargs
    )


def test_ramp_clamps_and_interpolates_encoded_rgb():
    value = ColorRamp((ColorStop(0, BLACK), ColorStop(10, RED), ColorStop(20, WHITE)))
    assert value.at(-1) == BLACK
    assert value.at(5) == Color(128, 0, 0)
    assert value.at(15) == Color(255, 128, 128)
    assert value.at(30) == WHITE
    with pytest.raises(ValueError):
        ColorRamp((ColorStop(0, BLACK), ColorStop(0, WHITE)))


def test_sweep_channels_have_independent_widths_and_seek_is_pure():
    field = SoftSweep(
        left=0,
        right=64,
        start=0.5,
        duration=1,
        fill=(BLACK, WHITE),
        outline=(RED, BLUE),
        width=8,
        outline_width=16,
    )

    def at(time):
        bands = field.bands(0, 64, time, VisualState())
        assert len(bands) <= field.max_bands
        assert [x for b in bands for x in range(b.start, b.end)] == list(range(64))
        return {x: (b.fill, b.outline) for b in bands for x in range(b.start, b.end)}

    middle = at(1)
    assert middle[27][0] == WHITE
    assert middle[27][1] != BLUE
    assert at(0)[32] == (BLACK, RED)
    assert at(2)[32] == (WHITE, BLUE)
    assert at(1) == middle


def test_gradient_pixel_centers_and_no_alpha_seams():
    field = LinearGradient(fill=ramp())
    doc = Document.create(width=64, height=32)
    result = Scene(doc).add(node(material=field)).compile()
    image = rasterize(result.document.dumps(), 0, (64, 32))
    reference = rasterize(
        Scene(doc).add(node()).compile().document.dumps(), 0, (64, 32)
    )
    for x in range(64):
        pixel = image.rgba[(16 * 64 + x) * 4 : (16 * 64 + x + 1) * 4]
        expected = round(255 * (x + 0.5) / 64)
        assert tuple(pixel[:3]) == (expected, expected, expected)
        assert pixel[3] == reference.rgba[(16 * 64 + x) * 4 + 3]
    assert result.objects[0].strategy == "native-static-bands"
    assert result.objects[0].peak_bands == 64


def test_slicing_blurred_rotated_text_preserves_coverage():
    doc = Document.create(width=320, height=160)
    text = TextObject(
        id="text",
        text="AV ffi",
        font_size=64,
        lifetime=Lifetime(0, 2),
        state=VisualState(
            position=Vec2(30, 30),
            fill=WHITE,
            outline=RED,
            border=3,
            blur=2,
            rotation=8,
            opacity=0.7,
        ),
    )

    # A custom field keeps equal colors as separate bands to exercise every seam.
    class Slices:
        axis = "x"
        max_bands = 320
        breakpoints = ()

        def bands(self, start, end, time, base):
            return tuple(
                PaintBand(x, x + 1, base.fill, base.outline) for x in range(start, end)
            )

    original = rasterize(Scene(doc).add(text).compile().document.dumps(), 0, (320, 160))
    sliced = rasterize(
        Scene(doc).add(replace(text, material=Slices())).compile().document.dumps(),
        0,
        (320, 160),
    )
    assert original.rgba == sliced.rgba


def test_static_field_keeps_native_move_and_rectangle_intersection():
    source = node(
        material=LinearGradient(fill=ramp()),
        clip=RectangleClip(10, 5, 30, 20),
        animations=(AnimationClip(0, 2, Tween(StatePatch(position=Vec2(10, 0)))),),
    )
    result = Scene(Document.create(width=64, height=32)).add(source).compile()
    assert result.objects[0].strategy == "native-move-bands"
    assert result.event_count == 20
    assert all(r"\move(" in line.text for line in result.document.lines)


def test_material_constraints_and_preflight():
    field = LinearGradient(fill=ramp())
    with pytest.raises(ValueError, match="group paint"):
        ObjectGroup(id="group", children=(), lifetime=Lifetime(0, 2), material=field)
    inverse = (
        Scene(Document.create())
        .add(
            node(
                material=field,
                clip=VectorClip(VectorPath.rectangle(10, 10), inverse=True),
            )
        )
        .compile()
    )
    assert inverse.objects[0].strategy == "native-static-bands"
    assert inverse.event_count > 0
    with pytest.raises(SceneCompileError, match="band budget"):
        Scene(Document.create()).add(node(material=field)).compile(
            budget=SceneBudget(max_bands=3)
        )

    class BadField:
        axis = "x"
        max_bands = 2
        breakpoints = ()

        def bands(self, start, end, time, base):
            return (PaintBand(1, end, base.fill, base.outline),)

    with pytest.raises(SceneCompileError, match="partition"):
        Scene(Document.create()).add(node(material=BadField())).compile()


def test_sweep_compilation_merges_static_intervals_and_is_repeatable():
    field = SoftSweep(
        left=0, right=64, start=0.5, duration=1, fill=(RED, BLUE), width=8
    )
    scene = Scene(Document.create(width=64, height=32)).add(node(material=field))
    result = scene.compile()
    assert result.document.dumps() == scene.compile().document.dumps()
    assert result.objects[0].strategy == "sampled-bands"
    assert result.peak_active <= field.max_bands
    assert any(
        line.start_time == 0 and line.end_time == 500 for line in result.document.lines
    )
    assert any(
        line.start_time == 1500 and line.end_time == 2000
        for line in result.document.lines
    )
    assert result.event_count <= result.estimated_events


def test_material_survives_geometry_conversion_and_copy():
    from kara_templater import text_to_path

    field = LinearGradient(fill=ramp())
    text = TextObject(id="text", text="W", lifetime=Lifetime(0, 2), material=field)
    assert text_to_path(text).material is field
    assert text.copy(id="copy", delay=1).material is field


def test_preflight_rejects_before_evaluating_custom_field():
    class ExpensiveField:
        axis = "x"
        max_bands = 500
        breakpoints = (0, 2)

        def bands(self, start, end, time, base):
            pytest.fail("preflight must precede paint evaluation")

    with pytest.raises(SceneCompileError, match="estimated event budget"):
        Scene(Document.create()).add(node(material=ExpensiveField())).compile()


def test_soft_sweep_exposes_eased_transition_center_including_padding():
    field = SoftSweep(
        left=100,
        right=200,
        start=1,
        duration=2,
        fill=(WHITE, RED),
        width=20,
        outline=(WHITE, BLUE),
        outline_width=40,
        rate=lambda p: p * p,
    )
    assert [field.front_at(t) for t in (0, 1, 2, 3, 4)] == [80, 80, 115, 220, 220]
    # The half-mixed band is centered on the same position, for either width.
    bands = field.bands(114, 116, 2, VisualState())
    assert len(bands) == 2
    assert bands[0].fill.green < bands[1].fill.green  # unsung lies to the right


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_soft_sweep_front_rejects_nonfinite_time(value: float):
    field = SoftSweep(left=0, right=100, start=0, duration=1, fill=(WHITE, RED))
    with pytest.raises(ValueError):
        field.front_at(value)
