"""Shared material composition from procedural masks, independent of Track/fonts."""

from dataclasses import replace

import pytest

from kara_templater import BLUE, RED, WHITE
from kara_templater._material_composition import MaterialLayer, compose_material_layers
from kara_templater._material_raster import CoverageMask, MaterialBand, paint_coverage
from kara_templater._raster import RasterBudget, RasterCanvas
from kara_templater.timeline import Region

BUDGET = RasterBudget()


def layer(color, weights=(1,), *, data=b"\xff", left=0, blur=0):
    mask = CoverageMask(left, 0, len(data), 1, data)
    return MaterialLayer(
        mask,
        (MaterialBand(Region(left, left + len(data)), color),),
        weights,
        blur,
    )


def test_roles_occlude_before_opacity_at_every_scope():
    glow = layer(RED, (1, 0.8, 0.6))
    stroke = layer(WHITE, (1, 0.4, 0.2))
    fill = layer(BLUE, (1, 0.25, 0.125))
    result = compose_material_layers(
        fills=(fill,), strokes=(stroke,), glows=(glow,), budget=BUDGET
    )
    assert tuple(frame.rgba for _, _, frame in result) == (
        bytes((BLUE.red, BLUE.green, BLUE.blue, 255)),
        bytes((BLUE.red, BLUE.green, BLUE.blue, 64)),
        bytes((BLUE.red, BLUE.green, BLUE.blue, 32)),
    )


def test_shared_shape_respects_stroke_and_fill_geometry():
    result = compose_material_layers(
        strokes=(layer(RED, data=bytes((255, 255, 255))),),
        fills=(layer(BLUE, data=bytes((0, 255, 0))),),
        budget=BUDGET,
    )
    assert result[0][2].rgba == bytes(
        (
            RED.red,
            RED.green,
            RED.blue,
            255,
            BLUE.red,
            BLUE.green,
            BLUE.blue,
            255,
            RED.red,
            RED.green,
            RED.blue,
            255,
        )
    )


def test_color_partition_is_combined_before_blur():
    mask = CoverageMask(0, 0, 6, 1, b"\xff" * 6)
    red = MaterialLayer(
        mask,
        (MaterialBand(Region(0, 3), RED), MaterialBand(Region(3, 6), RED, 0)),
        blur_radius=2,
    )
    blue = MaterialLayer(
        mask,
        (MaterialBand(Region(0, 3), BLUE, 0), MaterialBand(Region(3, 6), BLUE)),
        blur_radius=2,
    )
    actual = compose_material_layers(glows=(red, blue), budget=BUDGET)
    reference = paint_coverage(
        mask,
        (MaterialBand(Region(0, 3), RED), MaterialBand(Region(3, 6), BLUE)),
        blur_radius=2,
    )
    assert actual == (reference,)
    # Blurred colors spread across the partition, unlike clipping after blur.
    x, y, frame = actual[0]
    offset = ((-y) * frame.width + 2 - x) * 4
    assert frame.rgba[offset] > 0 and frame.rgba[offset + 2] > 0


def test_single_plane_and_uniform_scope_paths_agree_on_opaque_backgrounds():
    single = compose_material_layers(
        glows=(layer(RED, data=bytes((64, 255, 64)), blur=2),),
        fills=(layer(BLUE, data=bytes((0, 255, 0))),),
        budget=BUDGET,
    )[0]
    weighted = compose_material_layers(
        glows=(layer(RED, (1, 0.5), data=bytes((64, 255, 64)), blur=2),),
        fills=(layer(BLUE, (1, 0.5), data=bytes((0, 255, 0))),),
        budget=BUDGET,
    )
    assert weighted[0] == single
    canvas = RasterCanvas(single[2].width, single[2].height)
    canvas.over_frame(single[2])
    reference = canvas.finish(opacity=0.5)
    # Scope weights quantize before blur; factoring alpha after blur differs at
    # most by a small integer rounding error on these procedural masks.
    for background in (0, 255):

        def over(pixels, background=background):
            return tuple(
                round(
                    pixels[i + c] * pixels[i + 3] / 255
                    + background * (1 - pixels[i + 3] / 255)
                )
                for i in range(0, len(pixels), 4)
                for c in range(3)
            )

        assert (
            max(
                abs(a - b)
                for a, b in zip(
                    over(reference.rgba), over(weighted[1][2].rgba), strict=True
                )
            )
            <= 1
        )


def test_empty_scopes_and_invalid_layer_contracts():
    assert compose_material_layers(budget=BUDGET) == ()
    with pytest.raises(ValueError, match="matching opacity scopes"):
        compose_material_layers(
            fills=(layer(BLUE), layer(RED, (1, 0.5))), budget=BUDGET
        )
    with pytest.raises(ValueError, match="glow layer"):
        compose_material_layers(fills=(layer(BLUE, blur=2),), budget=BUDGET)
    with pytest.raises(ValueError, match="layer budget"):
        compose_material_layers(
            fills=(layer(BLUE), layer(RED)), budget=RasterBudget(max_images=1)
        )
    for weights in ((), (0.5,), (1, -1), (1, float("nan"))):
        with pytest.raises(ValueError):
            replace(layer(BLUE), weights=weights)
    with pytest.raises(ValueError, match="blur radius"):
        replace(layer(BLUE), blur_radius=101)


def test_procedural_materials_roundtrip_through_standard_ass():
    from kara_templater import DisplayWindow, Document
    from kara_templater._raster import encode_frame, rasterize

    image = compose_material_layers(
        fills=(layer(BLUE, (1, 0.4), data=bytes((0, 128, 255, 128, 0))),),
        glows=(layer(RED, (1, 0.4), data=bytes((0, 128, 255, 128, 0)), blur=2),),
        budget=BUDGET,
    )[-1][2]
    resolution = (image.width, image.height)
    document = Document.create(width=image.width, height=image.height)
    document.records.extend(
        encode_frame(image, DisplayWindow(0, 1000), resolution=resolution)
    )
    assert rasterize(document.dumps(), 500, resolution) == image


def test_vertical_partitions_transpose_back_before_shared_blur():
    mask = CoverageMask(10, 20, 2, 3, bytes((255, 128, 200, 100, 60, 30)))
    vertical = MaterialLayer(
        mask,
        (MaterialBand(Region(20, 21), RED), MaterialBand(Region(21, 23), BLUE)),
        blur_radius=2,
        axis="y",
    )
    result = compose_material_layers(glows=(vertical,), budget=BUDGET)
    # Build the already-colored unblurred reference directly in world order.
    from kara_templater._material_raster import blur_frame
    from kara_templater._raster import RasterFrame

    rgba = bytes(
        channel
        for index, alpha in enumerate(mask.data)
        for channel in (
            (RED if index < 2 else BLUE).red,
            (RED if index < 2 else BLUE).green,
            (RED if index < 2 else BLUE).blue,
            alpha,
        )
    )
    dx, dy, image = blur_frame(RasterFrame(2, 3, rgba), 2)
    assert result == ((10 + dx, 20 + dy, image),)


@pytest.mark.parametrize("axis", ("x", "y"))
@pytest.mark.parametrize("blur", (0, 2))
@pytest.mark.parametrize("color", (WHITE, RED))
def test_fractional_splits_quantize_once_for_each_opacity_plane(axis, blur, color):
    mask = CoverageMask(0, 0, 1, 1, bytes((127,)))
    weights = (1, 0.5, 0.25)
    whole = MaterialLayer(
        mask, (MaterialBand(Region(0, 1), WHITE),), weights, blur, axis
    )
    left = replace(
        whole,
        bands=(
            MaterialBand(Region(0, 0.5), WHITE),
            MaterialBand(Region(0.5, 1), WHITE, 0),
        ),
    )
    right = replace(
        whole,
        bands=(
            MaterialBand(Region(0, 0.5), color, 0),
            MaterialBand(Region(0.5, 1), color),
        ),
    )
    combined = replace(
        whole,
        bands=(
            MaterialBand(Region(0, 0.5), WHITE),
            MaterialBand(Region(0.5, 1), color),
        ),
    )
    actual = compose_material_layers(glows=(left, right), budget=BUDGET)
    reference = compose_material_layers(glows=(combined,), budget=BUDGET)
    assert actual == reference
    if not blur:
        # Independent alpha calculation: 127 coverage, not two rounded 64s.
        assert tuple(frame.rgba[3] for _, _, frame in actual) == (127, 64, 32)


def test_joined_partition_budget_does_not_fall_back_to_separate_quantization():
    mask = CoverageMask(0, 0, 1, 1, bytes((127,)))
    left = MaterialLayer(
        mask,
        (
            MaterialBand(Region(0, 0.25), WHITE),
            MaterialBand(Region(0.25, 1), WHITE, 0),
        ),
    )
    right = MaterialLayer(
        mask,
        (
            MaterialBand(Region(0, 0.75), WHITE, 0),
            MaterialBand(Region(0.75, 1), WHITE),
        ),
    )
    # Each input has two bands, but the exact combined partition needs three.
    with pytest.raises(ValueError, match="material band budget"):
        compose_material_layers(fills=(left, right), budget=RasterBudget(max_images=2))
    assert compose_material_layers(fills=(left, right), budget=BUDGET)
