"""Independent native-ASS references for animated Track material frames.

References use public layout and direct ASS glyph rendering, never Track's
private geometry, material partition, blur or pixel compositor implementations.
"""

from dataclasses import replace
from math import floor

import pytest
from PIL import Image, ImageChops
from test_track_raster import frame, render, scene

from kara_templater import (
    RED,
    WHITE,
    Animate,
    Blur,
    Body,
    Display,
    Document,
    Line,
    LineMatch,
    On,
    Ruby,
    TextStyle,
    Track,
    layout_line,
)
from kara_templater._raster import rasterize


def attenuate(image, opacity):
    result = image.copy()
    result.putalpha(
        image.getchannel("A").point(lambda value: floor(value * opacity + 0.5))
    )
    return result


@pytest.mark.parametrize("time", (40, 120, 160, 200, 280))
def test_dynamic_blur_scale_and_group_alpha_match_native_glyph_reference(time):
    source, item = scene(text="A", ruby="a")
    source.records.insert(1, "YCbCr Matrix: None")
    base = source.styles["Default"]
    ruby_style = replace(base, fontsize=12)
    layout = layout_line(
        item.source, style=base, ruby_style=ruby_style, resolution=(640, 480)
    )
    unit = layout.units[0]
    reading = unit.segments[0].ruby
    assert reading is not None
    config = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(
                fill=WHITE,
                stroke_width=0,
                opacity=0.8,
                blur=Blur(color=RED, radius=2, width=0),
            )
        ),
        ruby=Ruby(
            style=TextStyle(
                font_size=12,
                fill=WHITE,
                stroke_width=0,
                opacity=0.6,
                blur=Blur(color=RED, radius=2, width=0),
            ),
            offset_y=-4,
        ),
        animations=(
            On(
                Display.Start,
                Animate(
                    scale=(1, 1.2),
                    offset_x=(0, 20),
                    blur_radius=(2, 8),
                    opacity=0.65,
                    duration=320,
                ),
            ),
        ),
    )
    actual = Image.frombytes(
        "RGBA", (640, 480), frame(render(config, source, item), time).rgba
    )
    progress = time / 320
    scale = 1 + 0.2 * progress
    radius = (2 + 6 * progress) * scale
    expected = Image.new("RGBA", (640, 480))
    for text, box, style, offset_y, opacity in (
        ("A", unit.box, base, 0, 0.8),
        ("a", reading, ruby_style, -4, 0.6),
    ):
        x = layout.box.center + (box.center - layout.box.center) * scale + 20 * progress
        y = layout.box.middle + (box.middle + offset_y - layout.box.middle) * scale
        reference = Document.parse(source.dumps())
        reference.styles["Default"].fontsize = style.fontsize
        for layer, color, blur in ((0, "0000FF", radius), (1, "FFFFFF", 0)):
            reference.records.append(
                Line(
                    text=rf"{{\an5\pos({x:.6f},{y:.6f})\fscx{100 * scale:.6f}\fscy{100 * scale:.6f}\bord0\shad0\blur{blur:.6f}\1c&H{color}&\alpha&H00&}}"
                    + text,
                    start_time=0,
                    end_time=320,
                    layer=layer,
                )
            )
        pixels = rasterize(reference.dumps(), time, (640, 480))
        component = attenuate(Image.frombytes("RGBA", (640, 480), pixels.rgba), opacity)
        expected = Image.alpha_composite(expected, component)
    expected = attenuate(expected, 0.65)
    for background in ("black", "white"):
        backdrop = Image.new("RGBA", (640, 480), background)
        a = Image.alpha_composite(backdrop, actual).convert("RGB")
        b = Image.alpha_composite(backdrop, expected).convert("RGB")
        assert max(ImageChops.difference(a, b).tobytes()) <= 2


@pytest.mark.parametrize("time", (120, 160, 200))
@pytest.mark.parametrize("after_opacity", (0, 0.25, 0.75, 1))
def test_sweep_materials_match_independent_gaussian_reference(time, after_opacity):
    # Pillow uses a separate Gaussian approximation from libass. Compare the
    # displayed composite with a fixed 4/255 tolerance, including the front.
    from math import log, sqrt

    from PIL import ImageFilter

    from kara_templater import BLUE, Overlay, PaintStyle

    source, item = scene(text="A", ruby="")
    source.records.insert(1, "YCbCr Matrix: None")
    base = source.styles["Default"]
    layout = layout_line(item.source, style=base, resolution=(640, 480))
    box = layout.units[0].box
    config = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(
                fill=WHITE,
                stroke_width=0,
                opacity=0.75,
                blur=Blur(color=RED, radius=2, width=0, opacity=0.8),
            )
        ),
        overlay=Overlay(
            style=PaintStyle(
                fill=BLUE, opacity=after_opacity, blur=Blur(color=BLUE, radius=6)
            )
        ),
        animations=(
            On(
                Display.Start,
                Animate(scale=(1, 1.2), offset_x=(0, 20), opacity=0.6, duration=320),
            ),
        ),
    )
    actual = Image.frombytes(
        "RGBA", (640, 480), frame(render(config, source, item), time).rgba
    )
    scale, dx = 1 + 0.2 * time / 320, 20 * time / 320
    reference = Document.parse(source.dumps())
    reference.records.append(
        Line(
            text=rf"{{\an5\pos({box.center + dx:.6f},{box.middle:.6f})\fscx{scale * 100:.6f}\fscy{scale * 100:.6f}\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}A",
            start_time=0,
            end_time=320,
        )
    )
    mask = Image.frombytes(
        "RGBA", (640, 480), rasterize(reference.dumps(), time, (640, 480)).rgba
    ).getchannel("A")
    front = (
        box.center
        + ((box.left + box.width * (time - 100) / 100) - box.center) * scale
        + dx
    )
    selection = Image.frombytes(
        "L",
        (640, 480),
        bytes(
            floor(255 * (1 if time >= 200 else max(0, min(1, front - x))) + 0.5)
            for x in range(640)
        )
        * 480,
    )
    sung = ImageChops.multiply(mask, selection)
    unsung = ImageChops.subtract(mask, sung)
    # Red and blue planes are premultiplied; disjoint material coverage is
    # filtered before the two contributions are added, then alpha is applied
    # after filling the letter and composing its glow.
    red = unsung.point(lambda v: floor(v * 0.8 + 0.5)).filter(
        ImageFilter.GaussianBlur(2 * scale * 2 / sqrt(log(256)))
    )
    blue = sung.point(lambda v: floor(v * 0.8 + 0.5)).filter(
        ImageFilter.GaussianBlur(6 * scale * 2 / sqrt(log(256)))
    )
    pixels = []
    for r, b, a, u in zip(
        red.tobytes(), blue.tobytes(), mask.tobytes(), unsung.tobytes(), strict=True
    ):
        # The unweighted fill occludes its own glow before component opacity.
        # Different material weights travel with their pre-blur contributions.
        normalize = max(1, (r + b) / 255)
        glow_r = r * 0.75 / normalize * (1 - a / 255)
        glow_b = b * after_opacity / normalize * (1 - a / 255)
        fill_u, fill_s = u * 0.75, (a - u) * after_opacity
        alpha = glow_r + glow_b + fill_u + fill_s
        pixels.extend(
            (
                min(255, round(255 * (glow_r + fill_u) / alpha)),
                min(255, round(255 * fill_u / alpha)),
                min(255, round(255 * (glow_b + fill_u + fill_s) / alpha)),
                min(255, round(alpha)),
            )
            if alpha
            else (0, 0, 0, 0)
        )
    expected = attenuate(Image.frombytes("RGBA", (640, 480), bytes(pixels)), 0.6)
    for background in ("black", "white"):
        backdrop = Image.new("RGBA", (640, 480), background)
        a = Image.alpha_composite(backdrop, actual).convert("RGB")
        b = Image.alpha_composite(backdrop, expected).convert("RGB")
        assert max(ImageChops.difference(a, b).tobytes()) <= 4


@pytest.mark.parametrize("radius", (0.1, 1, 10, 50))
def test_native_blur_bounds_preserve_independent_whole_glyph(radius):
    from kara_templater import render_karaoke

    source, item = scene(text="A", ruby="")
    layout = layout_line(
        item.source, style=source.styles["Default"], resolution=(640, 480)
    )
    config = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(
                fill=WHITE, stroke_width=0, blur=Blur(color=RED, radius=radius, width=2)
            )
        ),
    )
    actual = frame(render_karaoke(source, items=(item,), tracks=(config,)), 160)
    reference = Document.parse(source.dumps())
    for layer, color, width, blur in ((0, "0000FF", 2, radius), (1, "FFFFFF", 0, 0)):
        reference.records.append(
            Line(
                text=rf"{{\an5\pos({layout.box.center},{layout.box.middle})\bord{width}\shad0\blur{blur}\1c&H{color}&\3c&H{color}&\alpha&H00&}}A",
                start_time=0,
                end_time=320,
                layer=layer,
            )
        )
    expected = rasterize(reference.dumps(), 160, (640, 480))
    assert actual == expected


def test_text_range_opacity_preserves_unweighted_glyph_coverage():
    from kara_templater import PaintStyle, TextSpan

    source, item = scene(text="WW", ruby="")
    base = TextStyle(fill=WHITE, stroke_width=0, blur=None)
    plain = frame(
        render(Track(source=LineMatch(), body=Body(style=base)), source, item), 160
    )
    styled = Track(
        source=LineMatch(),
        body=Body(
            style=base,
            spans=(
                TextSpan(0, 1, style=PaintStyle(opacity=0.25)),
                TextSpan(1, 2, style=PaintStyle(opacity=0.75)),
            ),
        ),
    )
    actual = frame(render(styled, source, item), 160)
    center = layout_line(
        item.source, style=source.styles["Default"], resolution=(640, 480)
    ).box.center
    for index, (alpha, original) in enumerate(
        zip(actual.rgba[3::4], plain.rgba[3::4], strict=True)
    ):
        x = index % 640
        if abs(x - center) > 1:
            expected = floor(original * (0.25 if x < center else 0.75) + 0.5)
            assert abs(alpha - expected) <= 1
    assert any(actual.rgba[3::4])


@pytest.mark.parametrize("kind", ("group", "syllable"))
def test_selected_scope_opacity_matches_independent_native_letters(kind):
    from kara_templater import AnimationTarget, KaraokeLine, Segment, TextUnit

    source, item = scene(text="AB", ruby="")
    item = replace(
        item,
        source=KaraokeLine(
            (
                TextUnit("A", (Segment(100, 200),)),
                TextUnit("B", (Segment(100, 200),)),
            )
        ),
    )
    config = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=WHITE, stroke_width=0, blur=None)),
        animations=tuple(
            On(
                Display.Start,
                Animate(
                    AnimationTarget(item.id, (index,), kind),
                    opacity=opacity,
                    duration=320,
                ),
            )
            for index, opacity in enumerate((0.25, 0.75))
        ),
    )
    actual = Image.frombytes(
        "RGBA", (640, 480), frame(render(config, source, item), 160).rgba
    )
    layout = layout_line(
        item.source, style=source.styles["Default"], resolution=(640, 480)
    )
    expected = Image.new("RGBA", (640, 480))
    for unit, opacity in zip(layout.units, (0.25, 0.75), strict=True):
        reference = Document.parse(source.dumps())
        reference.records.append(
            Line(
                text=rf"{{\an5\pos({unit.box.center},{unit.box.middle})\bord0\shad0\blur0\1c&HFFFFFF&\alpha&H00&}}"
                + unit.source.text,
                start_time=0,
                end_time=320,
            )
        )
        image = Image.frombytes(
            "RGBA", (640, 480), rasterize(reference.dumps(), 160, (640, 480)).rgba
        )
        expected = Image.alpha_composite(expected, attenuate(image, opacity))
    for background in ("black", "white"):
        backdrop = Image.new("RGBA", (640, 480), background)
        a = Image.alpha_composite(backdrop, actual).convert("RGB")
        b = Image.alpha_composite(backdrop, expected).convert("RGB")
        assert max(ImageChops.difference(a, b).tobytes()) <= 1


def test_ruby_can_opt_out_of_unit_opacity_without_splitting_source_groups():
    from kara_templater import Follow, Syllable

    source, item = scene(text="A", ruby="a")
    config = Track(
        source=LineMatch(),
        body=Body(style=TextStyle(fill=WHITE, stroke_width=0)),
        ruby=Ruby(
            style=TextStyle(fill=WHITE, stroke_width=0), follow=Follow(opacity=False)
        ),
        animations=(On(Syllable.Singing, Animate(opacity=0.25)),),
    )
    actual = frame(render(config, source, item), 160)
    config.animations = ()
    plain = frame(render(config, source, item), 160)
    layout = layout_line(
        item.source, style=source.styles["Default"], resolution=(640, 480)
    )
    cut = layout.units[0].box.top
    ruby_pixels = body_pixels = 0
    for index, (alpha, original) in enumerate(
        zip(actual.rgba[3::4], plain.rgba[3::4], strict=True)
    ):
        if index // 640 < cut:
            assert alpha == original
            ruby_pixels += bool(alpha)
        else:
            assert abs(alpha - floor(original * 0.25 + 0.5)) <= 1
            body_pixels += bool(alpha)
    assert ruby_pixels and body_pixels
