"""Actual libass round trips for the bounded material backend foundation."""

import pytest

from kara_templater import Document, OutputCapabilityError, Style, _metrics
from kara_templater._raster import (
    RasterBudget,
    RasterCanvas,
    RasterFrame,
    encode_frame,
    quantize_frame,
    rasterize,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT
from kara_templater.timeline import DisplayWindow


def script(lines=(), width=32, height=24):
    doc = Document.parse(
        f"[Script Info]\nPlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style(fontname="DejaVu Sans", outline=0, shadow=0).serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    doc.records.extend(lines)
    return doc.dumps()


def roundtrip(frame):
    lines = encode_frame(frame, DisplayWindow(0, 1000))
    return rasterize(
        script(lines, frame.width, frame.height), 500, (frame.width, frame.height)
    )


def test_pixel_geometry_has_exact_position_and_no_adjacent_seams():
    data = bytearray(32 * 24 * 4)
    for y in range(3, 5):
        for x in range(4, 7):
            start = (y * 32 + x) * 4
            data[start : start + 4] = bytes((255, 40, 90, 255))
    frame = RasterFrame(32, 24, bytes(data))
    assert roundtrip(frame) == frame


def test_many_colors_and_alphas_roundtrip_without_palette_reduction():
    data = bytes(
        channel
        for y in range(24)
        for x in range(32)
        for channel in (x * 7, y * 10, (x + y) * 4, 1 + (x * 19 + y * 7) % 255)
    )
    frame = RasterFrame(32, 24, data)
    assert roundtrip(frame) == frame


def test_transparent_pixels_emit_no_geometry():
    frame = RasterFrame(4, 4, bytes((255, 0, 0, 0)) * 16)
    assert encode_frame(frame, DisplayWindow(0, 1000)) == ()
    assert roundtrip(frame).rgba == bytes(64)


def test_group_opacity_is_applied_after_overlapping_paints():
    canvas = RasterCanvas(1, 1)
    # red then blue, each with 128/255 coverage. ASS color alpha is inverted.
    canvas.over((0, 0, 1, 1, 0, 0xFF000000, bytes((128,))))
    canvas.over((0, 0, 1, 1, 0, 0x0000FF00, bytes((128,))))
    full = canvas.finish()
    group = canvas.finish(opacity=0.5)
    assert full.rgba == bytes((85, 0, 170, 192))
    assert group.rgba == bytes((85, 0, 170, 96))
    assert roundtrip(group) == group
    # Applying .5 separately to both layers would yield alpha 112, not 96.
    assert group.rgba[3] != 112


def test_native_bitmaps_are_owned_and_raster_resolution_does_not_change_metrics():
    before = _metrics.text_shape("DejaVu Sans", 32, 0, 0, 100, 100, 0, 1, "office")
    frame = RasterFrame(32, 24, bytes((12, 23, 34, 255)) * 768)
    text = script(encode_frame(frame, DisplayWindow(0, 1000)))
    images = _metrics.rasterize(text, 500, 32, 24, 10000, 1000)
    snapshot = tuple(images)
    assert images
    _metrics.rasterize(script(width=640, height=480), 0, 640, 480, 1_000_000, 1000)
    assert tuple(images) == snapshot
    assert (
        _metrics.text_shape("DejaVu Sans", 32, 0, 0, 100, 100, 0, 1, "office") == before
    )


def test_native_image_copy_has_explicit_frame_and_overdraw_budgets():
    with pytest.raises(ValueError, match="budget"):
        _metrics.rasterize(script(), 0, 640, 480, 100, 1)
    frame = RasterFrame(32, 24, bytes((255, 255, 255, 255)) * 768)
    lines = encode_frame(frame, DisplayWindow(0, 1000))
    with pytest.raises(ValueError, match="coverage"):
        _metrics.rasterize(script((*lines, *lines)), 500, 32, 24, 768, 10)
    with pytest.raises(ValueError, match="coverage"):
        _metrics.rasterize(script((*lines, *lines)), 500, 32, 24, 10000, 1)


def test_encoding_rejects_work_exceeding_each_budget():
    frame = RasterFrame(2, 2, bytes((255, 0, 0, 255, 0, 255, 0, 255)) * 2)
    for budget, message in (
        (RasterBudget(max_pixels=1), "pixel"),
        (RasterBudget(max_events=1), "event"),
        (RasterBudget(max_rectangles=1), "rectangle"),
        (RasterBudget(max_path_chars=1), "path"),
    ):
        with pytest.raises(OutputCapabilityError, match=message):
            encode_frame(frame, DisplayWindow(0, 1000), budget=budget)
    with pytest.raises(ValueError, match="positive"):
        RasterBudget(max_events=0)
    with pytest.raises(ValueError, match="buffer size"):
        RasterFrame(2, 2, b"tiny")


def test_compositor_clips_input_coordinates_and_rejects_invalid_coverage():
    canvas = RasterCanvas(1, 1)
    canvas.over((-1, -1, 2, 2, 0, 0xFF000000, bytes((255, 255, 255, 255))))
    assert canvas.finish().rgba == bytes((255, 0, 0, 255))
    with pytest.raises(ValueError, match="coverage"):
        canvas.over((0, 0, 2, 2, 0, 0, b"x"))
    with pytest.raises(ValueError, match="opacity"):
        canvas.finish(opacity=2)
    canvas = RasterCanvas(1, 1, budget=RasterBudget(max_images=1))
    canvas.over((0, 0, 1, 1, 0, 0, b"\xff"))
    with pytest.raises(OutputCapabilityError, match="budget"):
        canvas.over((0, 0, 1, 1, 0, 0, b"\xff"))


@pytest.mark.parametrize("radius", (0, 0.1, 1, 3, 10, 50, 100))
def test_coverage_blur_matches_native_ass_kernel_and_working_bounds(radius):
    from kara_templater import Line

    text = (
        r"{\an7\pos(220,220)\p1\bord0\shad0\1c&HFFFFFF&\blur0}m 0 0 l 30 0 30 30 0 30"
    )
    event = Line(text=text, start_time=0, end_time=1000)
    images = _metrics.rasterize(
        script((event,), 512, 512), 500, 512, 512, 4_000_000, 100
    )
    canvas = RasterCanvas(512, 512)
    for x, y, width, height, kind, color, data in images:
        dx, dy, bw, bh, blurred = _metrics.blur_mask(
            data, width, height, radius, 4_000_000
        )
        canvas.over((x + dx, y + dy, bw, bh, kind, color, blurred))
    event.text = text.replace("blur0", f"blur{radius}")
    expected = rasterize(script((event,), 512, 512), 500, (512, 512))
    assert canvas.finish() == expected


def test_blur_workspace_budget_and_radius_are_checked_before_filtering():
    for radius in (-1, 101, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="radius"):
            _metrics.blur_mask(b"\xff", 1, 1, radius, 1000)
    with pytest.raises(ValueError, match="budget"):
        _metrics.blur_mask(b"\xff", 1, 1, 100, 1000)
    with pytest.raises(ValueError, match="dimensions"):
        _metrics.blur_mask(b"\xff", 2, 2, 1, 1000)
    assert _metrics.blur_mask(b"\x00\x80\xff", 3, 1, 0, 1000) == (
        0,
        0,
        3,
        1,
        b"\x00\x80\xff",
    )


def test_material_is_selected_before_blur_and_preserves_single_alpha():
    from kara_templater import BLUE, RED, WHITE, Region
    from kara_templater._material_raster import (
        CoverageMask,
        MaterialBand,
        paint_coverage,
    )

    mask = CoverageMask(20, 30, 16, 8, b"\xff" * 128)
    x, y, mixed = paint_coverage(
        mask,
        (
            MaterialBand(Region(20, 28), BLUE),
            MaterialBand(Region(28, 36), RED),
        ),
        blur_radius=3,
    )
    ux, uy, uniform = paint_coverage(
        mask, (MaterialBand(Region(20, 36), WHITE),), blur_radius=3
    )
    assert (x, y, mixed.width, mixed.height) == (ux, uy, uniform.width, uniform.height)
    assert mixed.rgba[3::4] == uniform.rgba[3::4]
    # Both colors spread past the material boundary; no post-blur hard clip.
    for column in (27, 28):
        offset = ((34 - y) * mixed.width + column - x) * 4
        red, green, blue, alpha = mixed.rgba[offset : offset + 4]
        assert 0 < red < 255 and green == 0 and 0 < blue < 255 and alpha > 0
    assert roundtrip(mixed) == mixed


def test_fractional_material_partition_and_opacity_are_premultiplied():
    from kara_templater import BLUE, RED, Region
    from kara_templater._material_raster import (
        CoverageMask,
        MaterialBand,
        paint_coverage,
    )

    mask = CoverageMask(0, 0, 1, 1, b"\xff")
    _, _, frame = paint_coverage(
        mask,
        (
            MaterialBand(Region(0, 0.5), RED, 0.5),
            MaterialBand(Region(0.5, 1), BLUE, 1),
        ),
    )
    assert frame.rgba[3] == 191
    # Check premultiplied energy: 8-bit planes quantize before unpremultiplication.
    assert frame.rgba[0] * frame.rgba[3] / 255 == pytest.approx(63.75, abs=1)
    assert frame.rgba[2] * frame.rgba[3] / 255 == pytest.approx(127.5, abs=1)
    with pytest.raises(ValueError, match="partition"):
        paint_coverage(mask, (MaterialBand(Region(0, 0.5), RED),))
    with pytest.raises(ValueError, match="partition"):
        paint_coverage(
            mask,
            (MaterialBand(Region(0, 0.8), RED), MaterialBand(Region(0.5, 1), BLUE)),
        )


def test_colored_frames_share_the_same_group_alpha_and_translation():
    canvas = RasterCanvas(2, 2)
    frame = RasterFrame(1, 1, bytes((255, 0, 0, 128)))
    canvas.over_frame(frame, 1, 1)
    canvas.over_frame(RasterFrame(1, 1, bytes((0, 0, 255, 128))), 1, 1)
    result = canvas.finish(opacity=0.5)
    assert result.rgba[:12] == bytes(12)
    assert result.rgba[12:] == bytes((85, 0, 170, 96))
    assert roundtrip(result) == result


@pytest.mark.parametrize("radius", (0, 0.01, 0.1, 1, 3, 10, 50, 100))
def test_native_blur_padding_bounds_every_alignment(radius):
    padding = _metrics.blur_padding(radius)
    expansions = []
    # Exercise every possible downsample alignment for supported radii.
    for width in range(1, 65):
        height = 65 - width
        left, top, w, h, _ = _metrics.blur_mask(
            bytes([255]) * width * height, width, height, radius, 4_000_000
        )
        sides = (-left, -top, left + w - width, top + h - height)
        assert all(0 <= side <= padding for side in sides)
        expansions.extend(sides)
    assert max(expansions) == padding


@pytest.mark.parametrize("radius", (-1, 100.01, float("inf"), float("nan")))
def test_native_blur_padding_rejects_invalid_radius(radius):
    with pytest.raises(ValueError, match="radius"):
        _metrics.blur_padding(radius)


def test_neutral_style_encoding_removes_redundant_tags_without_pixel_changes():
    pixels = bytes(
        channel
        for y in range(8)
        for x in range(8)
        for channel in (x * 31, y * 31, (x + y) * 15, (x * 8 + y) * 4)
    )
    source = RasterFrame(8, 8, pixels)
    standard = encode_frame(source, DisplayWindow(0, 1000))
    compact = encode_frame(source, DisplayWindow(0, 1000), neutral_style=True)
    assert len(compact) == len(standard)
    assert sum(len(line.text) for line in compact) < 0.7 * sum(
        len(line.text) for line in standard
    )
    a = rasterize(script(standard, 8, 8), 500, (8, 8))
    b = rasterize(script(compact, 8, 8), 500, (8, 8))
    assert a == b
    assert b.rgba[4:] == source.rgba[4:]


@pytest.mark.parametrize("error", (0, 1, 2, 4, 8, 255))
def test_spatial_quantization_bound_for_all_color_and_alpha_values(error):
    source = RasterFrame(
        256,
        256,
        bytes(
            value
            for alpha in range(256)
            for color in range(256)
            for value in (color, 255 - color, (color * 37) % 256, alpha)
        ),
    )
    result = quantize_frame(source, error)
    for offset in range(0, len(source.rgba), 4):
        before = source.rgba[offset : offset + 4]
        after = result.rgba[offset : offset + 4]
        for background in (0, 73, 255):
            for channel in range(3):
                a = before[channel] * before[3] + background * (255 - before[3])
                b = after[channel] * after[3] + background * (255 - after[3])
                assert abs(a - b) <= error * 255
    if error == 0:
        assert result is source


@pytest.mark.parametrize("error", (-1, 256, 1.5, True))
def test_spatial_quantization_rejects_invalid_error(error):
    with pytest.raises(ValueError, match="max_channel_error"):
        quantize_frame(RasterFrame(1, 1, bytes(4)), error)


@pytest.mark.parametrize("start", (0, 40, 80, 120, 200, 240))
def test_local_pixel_alpha_preserves_global_curve_at_and_after_fade_end(start):
    from dataclasses import replace

    from kara_templater._raster_alpha import apply_opacity

    original = encode_frame(
        RasterFrame(1, 1, bytes((255, 255, 255, 200))), DisplayWindow(0, 320)
    )[0]
    reference = replace(
        original,
        text=original.text.replace(
            r"\alpha&H37&",
            r"\alpha&HFF&\t(0,80,1,\alpha&H37&)\t(200,320,1,\alpha&HFF&)",
        ),
    )
    local = replace(
        original,
        start_time=start,
        text=apply_opacity(original.text, start, ((0, 0), (80, 1), (200, 1), (320, 0))),
    )
    for time in range(start, 320, 10):
        assert rasterize(script((local,), 1, 1), time, (1, 1)) == rasterize(
            script((reference,), 1, 1), time, (1, 1)
        )
    if start >= 80:
        assert r"\t(-80,0," not in local.text
        assert len(local.text) < len(reference.text)


def test_native_raster_type_is_available_to_runtime_annotation_evaluation():
    from typing import get_type_hints

    from kara_templater._native_types import RasterImage
    from kara_templater._raster import RasterCanvas

    assert get_type_hints(RasterCanvas.over)["image"] is RasterImage


def test_additive_material_energy_is_clamped_before_group_opacity():
    canvas = RasterCanvas(1, 1)
    frame = RasterFrame(1, 1, bytes((255, 0, 0, 255)))
    canvas.add_frame(frame)
    canvas.add_frame(frame)
    assert canvas.finish(opacity=0.5).rgba == bytes((255, 0, 0, 128))
